"""DPO on a small preference set: predict the first loss from chapter 12's
formula, train with TRL's DPOTrainer, then read the implicit reward margin
and the preference accuracy back out of the model, by hand and from TRL.

Lab VM (SmolLM2-135M-Instruct, a few hundred pairs, about 30 minutes on the CPU):
    python dpo_small.py
GPU box (0.5B model, more pairs, bf16 autocast):
    python dpo_small.py --model Qwen/Qwen2.5-0.5B-Instruct --pairs 2000 \
        --steps 120 --batch 4 --accum 4 --max-length 1024
Same, with LoRA adapters instead of full tuning (a 1.5B model fits):
    python dpo_small.py --model Qwen/Qwen2.5-1.5B-Instruct --lora 16 ...
Memory prediction only (reads config.json, downloads no weights):
    python dpo_small.py --model Qwen/Qwen2.5-1.5B-Instruct --predict-only

Needs: torch, transformers, trl, datasets (workbench/requirements.txt)."""
import argparse
import math
import random

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
from transformers.trainer_callback import PrinterCallback
from trl import DPOConfig, DPOTrainer
from trl.trainer import utils as trl_utils

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M-Instruct")
ap.add_argument("--pairs", type=int, default=240)     # training pairs
ap.add_argument("--eval-pairs", type=int, default=100)  # held-out pairs
ap.add_argument("--steps", type=int, default=30)      # optimiser steps
ap.add_argument("--batch", type=int, default=2)       # pairs per micro-batch
ap.add_argument("--accum", type=int, default=4)       # micro-batches per step
ap.add_argument("--lr", type=float, default=2e-5)
ap.add_argument("--beta", type=float, default=0.1)    # the leash
ap.add_argument("--max-length", type=int, default=256)
ap.add_argument("--lora", type=int, default=0)        # LoRA rank (0: full)
ap.add_argument("--predict-only", action="store_true")
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
random.seed(0)
torch.manual_seed(0)


class PlainLogProb:
    """Stand-in for TRL's Triton kernel, which exists on Linux + CUDA only.

    TRL 1.15 computes per-token log-probabilities in a fused kernel. Where
    Triton is missing (CPU only), the import fails and training crashes. This
    does the same sums with ordinary PyTorch: slower and hungrier, same
    numbers. Skipped on a GPU box, where the real kernel is present."""

    @staticmethod
    def apply(hidden, weight, bias, targets, temperature, chunk, softcap,
              scale, outputs):
        z = hidden @ weight.t()
        z = (z if bias is None else z + bias).float() * scale / temperature
        lse = torch.logsumexp(z, -1)
        logp = z.gather(1, targets[:, None])[:, 0] - lse
        p = z.softmax(-1)
        entropy = lse - (p * z).sum(-1) if "entropy" in outputs else None
        sq = torch.log((p ** 2).sum(-1)) if "log_sum_sq_probs" in outputs \
            else None
        mean_logits = z.detach().mean(-1) if "mean_logits" in outputs \
            else None
        top1 = (z.argmax(-1) == targets) if "is_top1" in outputs else None
        return logp, entropy, sq, mean_logits, top1


HAVE_KERNEL = trl_utils._ChunkedLogProbFunction is not None
if not HAVE_KERNEL:                                # no Triton here
    trl_utils._ChunkedLogProbFunction = PlainLogProb


def gib(n):
    return f"{n / 2**30:,.2f} GiB"


# ── 2. Predict: memory from the config, and the first loss ───────────────
cfg = AutoConfig.from_pretrained(args.model)
with torch.device("meta"):                  # shapes only: no memory used
    shell = AutoModelForCausalLM.from_config(cfg)
N = sum(p.numel() for p in shell.parameters())
L, h, a, V = (cfg.num_hidden_layers, cfg.hidden_size,
              cfg.num_attention_heads, cfg.vocab_size)
s, rows = args.max_length, 2 * args.batch   # chosen and rejected together
if args.lora:    # adapters on every linear layer; the base stays frozen
    kv = cfg.num_key_value_heads * (h // a)
    mats = [(h, h), (h, kv), (h, kv), (h, h), (h, cfg.intermediate_size),
            (h, cfg.intermediate_size), (cfg.intermediate_size, h)]
    trainable = L * sum(args.lora * (i + o) for i, o in mats)
    states = 4 * N + 16 * trainable         # frozen fp32 base + adapters
    ref = 0                                 # reference = adapters switched off
else:            # fp32 weights (4), gradients (4), Adam moments (8) ...
    trainable, states = N, 16 * N
    ref = 4 * N                             # ... plus a frozen fp32 copy
acts = L * s * rows * h * 2                 # checkpointing: layer inputs
logits = s * rows * V * 4                   # one fp32 copy of the scores
if HAVE_KERNEL or args.predict_only:       # predict-only means "for a GPU"
    logits = 0                              # TRL's kernel works in chunks
print(f"model {args.model} on {DEVICE}: {N:,} parameters, "
      f"{trainable:,} trained")
print(f"predicted memory: states {gib(states)} + reference {gib(ref)} "
      f"+ activations {gib(acts)} + logits {gib(logits)} "
      f"= {gib(states + ref + acts + logits)}")
print(f"predicted step-0 loss: -log sigma(0) = log 2 = {math.log(2):.4f}")
if args.predict_only:
    raise SystemExit

# ── 3. Data: pairs that fit untruncated, prompt split off the answers ────
tok = AutoTokenizer.from_pretrained(args.model)


def fits(messages):
    """True if the whole conversation fits in max_length tokens."""
    ids = tok.apply_chat_template(messages, return_dict=False)
    return len(ids) <= args.max_length


def short_pairs(split, n):
    """The first n pairs whose prompt and both answers fit untruncated."""
    out = []
    for r in load_dataset("trl-lib/ultrafeedback_binarized", split=split):
        if len(r["chosen"]) != 2 or len(r["rejected"]) != 2:
            continue                           # keep single-turn prompts
        if fits(r["chosen"]) and fits(r["rejected"]):
            out.append({"prompt": r["chosen"][:-1],
                        "chosen": r["chosen"][-1:],
                        "rejected": r["rejected"][-1:]})
        if len(out) == n:
            break
    return out


train = short_pairs("train", args.pairs)
held = short_pairs("test", args.eval_pairs)
print(f"{len(train)} training pairs, {len(held)} held-out pairs")


# ── 4. The implicit reward by hand: beta * (log pi_theta - log pi_ref) ───
def seq_logp(model, prompt, answer):
    """Sum of the answer's token log-probabilities given the prompt."""
    p_ids = tok.apply_chat_template(prompt, add_generation_prompt=True,
                                    return_dict=False)
    ids = tok.apply_chat_template(prompt + answer,
                                  return_dict=False)[:args.max_length]
    x = torch.tensor([ids], device=model.device)
    with torch.no_grad():
        lp = model(x).logits[0, :-1].float().log_softmax(-1)
    tok_lp = lp.gather(1, x[0, 1:, None])[:, 0]
    return tok_lp[len(p_ids) - 1:].sum().item()


def preference_stats(policy, reference, pairs):
    """Mean margin, accuracy, DPO loss, and how far each answer's
    log-probability moved (chosen, rejected), over pairs, by hand."""
    margins, moved = [], {"chosen": [], "rejected": []}
    for r in pairs:
        gap = {}
        for key in ("chosen", "rejected"):
            lp = seq_logp(policy, r["prompt"], r[key])
            if args.lora:                       # reference: adapters off
                with policy.disable_adapter():
                    lp0 = seq_logp(policy, r["prompt"], r[key])
            else:
                lp0 = seq_logp(reference, r["prompt"], r[key])
            moved[key].append(lp - lp0)
            gap[key] = args.beta * (lp - lp0)       # the implicit reward
        margins.append(gap["chosen"] - gap["rejected"])
    n = len(margins)
    loss = sum(-math.log(1 / (1 + math.exp(-m))) for m in margins) / n
    return (sum(margins) / n, sum(m > 0 for m in margins) / n, loss,
            sum(moved["chosen"]) / n, sum(moved["rejected"]) / n)


# ── 5. Train with TRL ────────────────────────────────────────────────────
cfg_dpo = DPOConfig(
    output_dir="dpo-out", beta=args.beta, learning_rate=args.lr,
    loss_type=["sigmoid"],                 # the loss derived in chapter 12
    max_steps=args.steps, per_device_train_batch_size=args.batch,
    gradient_accumulation_steps=args.accum, max_length=args.max_length,
    logging_steps=1, eval_strategy="no", report_to="none", save_strategy="no",
    bf16=(DEVICE == "cuda"), gradient_checkpointing=(DEVICE == "cuda"),
    seed=0, data_seed=0, disable_tqdm=True)
trainer = DPOTrainer(model=args.model, args=cfg_dpo,
                     train_dataset=Dataset.from_list(train),
                     eval_dataset=Dataset.from_list(held),
                     processing_class=tok,
                     peft_config=(LoraConfig(
                         r=args.lora, lora_alpha=2 * args.lora,
                         target_modules="all-linear") if args.lora else None))
trainer.remove_callback(PrinterCallback)       # we print our own table
policy = trainer.model
reference = None if args.lora else AutoModelForCausalLM.from_pretrained(
    args.model, dtype=torch.float32).to(policy.device).eval()

m0, acc0, loss0, _, _ = preference_stats(policy, reference, held)
print(f"\nbefore training, held-out, by hand: margin {m0:+.4f}  "
      f"accuracy {acc0:.2f}  loss {loss0:.4f}")
ev = trainer.evaluate()
print(f"before training, held-out, TRL evaluate(): "
      f"margin {ev['eval_rewards/margins']:+.4f}  "
      f"accuracy {ev['eval_rewards/accuracies']:.2f}  "
      f"loss {ev['eval_loss']:.4f}")
trainer.train()
log = [r for r in trainer.state.log_history if "rewards/margins" in r]

print(f"\n{'steps':>6} {'loss':>7} {'margin':>8} {'acc':>5} "
      f"{'r_chosen':>9} {'r_reject':>9}")
windows = [("1", log[:1])] + [(f"{k + 1}-{k + 5}", log[k:k + 5])
                              for k in range(0, len(log), 5)]
for name, w in windows:          # step 1 alone, then means of 5 steps
    def avg(key):
        return sum(r[key] for r in w) / len(w)
    print(f"{name:>6} {avg('loss'):7.4f} {avg('rewards/margins'):+8.4f} "
          f"{avg('rewards/accuracies'):5.2f} "
          f"{avg('rewards/chosen'):+9.4f} {avg('rewards/rejected'):+9.4f}")

# ── 6. Read the result back out of the trained model ─────────────────────
policy.eval()
m1, acc1, loss1, dw, dl = preference_stats(policy, reference, held)
print(f"\nafter training, held-out, by hand: margin {m1:+.4f}  "
      f"accuracy {acc1:.2f}  loss {loss1:.4f}")
ev = trainer.evaluate()
print(f"after training, held-out, TRL evaluate(): "
      f"margin {ev['eval_rewards/margins']:+.4f}  "
      f"accuracy {ev['eval_rewards/accuracies']:.2f}  "
      f"loss {ev['eval_loss']:.4f}")
m2, acc2, loss2, _, _ = preference_stats(policy, reference, train[:100])
print(f"after training, 100 pairs it trained on: margin {m2:+.4f}  "
      f"accuracy {acc2:.2f}  loss {loss2:.4f}")
print(f"held-out log-probs moved by {dw:+.1f} (chosen) and "
      f"{dl:+.1f} (rejected) nats against the reference")
