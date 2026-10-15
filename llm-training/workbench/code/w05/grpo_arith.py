"""GRPO on a task a program can check: addition. Train with TRL's
GRPOTrainer, compute one group's advantages by hand next to the trainer's
own, then reward the format alone and watch the reward climb while the
accuracy does not.

Lab VM (SmolLM2-135M-Instruct, about 5 minutes per run on the CPU):
    python grpo_arith.py                    # reward = correct answers
    python grpo_arith.py --reward format    # reward = the format only
GPU box (a 0.5B model, bigger groups, 24 GB card):
    python grpo_arith.py --model Qwen/Qwen2.5-0.5B-Instruct --group 16 \
        --prompts 8 --steps 200 --max-digits 3

Memory prediction only (reads config.json, downloads no weights):
    python grpo_arith.py --model Qwen/Qwen2.5-0.5B-Instruct --group 16 \
        --prompts 8 --max-completion 256 --predict-only

Needs: torch, transformers, trl, datasets (workbench/requirements.txt)."""
import argparse
import random
import re
import statistics

import torch
from datasets import Dataset
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
from transformers import TrainerCallback
from transformers.trainer_callback import PrinterCallback
from trl import GRPOConfig, GRPOTrainer
from trl.trainer import utils as trl_utils

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M-Instruct")
ap.add_argument("--reward", default="correct",
                choices=["correct", "format"])     # what is optimised
ap.add_argument("--steps", type=int, default=30)
ap.add_argument("--group", type=int, default=8)    # G: answers per prompt
ap.add_argument("--prompts", type=int, default=4)  # prompts per step
ap.add_argument("--lr", type=float, default=2e-5)
ap.add_argument("--max-digits", type=int, default=2)
ap.add_argument("--max-completion", type=int, default=48)  # tokens
ap.add_argument("--eval-n", type=int, default=100)
ap.add_argument("--predict-only", action="store_true")
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
random.seed(0)
torch.manual_seed(0)


class PlainLogProb:
    """Stand-in for TRL's Triton kernel (Linux + CUDA only). Same sums in
    ordinary PyTorch, for CPU-only machines. Not used where the real kernel exists."""

    @staticmethod
    def apply(hidden, weight, bias, targets, temperature, chunk, softcap,
              scale, outputs):
        z = hidden @ weight.t()
        z = (z if bias is None else z + bias).float() * scale / temperature
        lse = torch.logsumexp(z, -1)
        logp = z.gather(1, targets[:, None])[:, 0] - lse
        p = z.softmax(-1)
        entropy = lse - (p * z).sum(-1) if "entropy" in outputs else None
        return logp, entropy, None, None, None


if trl_utils._ChunkedLogProbFunction is None:      # no Triton here
    trl_utils._ChunkedLogProbFunction = PlainLogProb

# ── 2. The task and its verifier: plain Python, no model involved ────────
HI = 10 ** args.max_digits - 1


def make_problems(n, seed):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        a, b = rng.randint(2, HI), rng.randint(2, HI)
        q = (f"What is {a} + {b}? "
             f"End your reply with 'Answer: <number>'.")
        out.append({"prompt": [{"role": "user", "content": q}],
                    "answer": str(a + b)})
    return out


def text_of(completion):
    return completion[0]["content"] if isinstance(completion, list) \
        else completion


def is_correct(text, answer):
    """The last whole number in the reply equals the true sum."""
    nums = re.findall(r"-?\d+", text)
    return bool(nums) and nums[-1] == answer


def is_formatted(text):
    """The reply ends with 'Answer: <number>', right or wrong."""
    return re.search(r"Answer:\s*-?\d+\s*$", text) is not None


def correct(completions, answer, **kwargs):
    """Reward 1.0 for a correct final number, else 0.0."""
    return [float(is_correct(text_of(c), a))
            for c, a in zip(completions, answer)]


def formatted(completions, **kwargs):
    """Reward 1.0 for the 'Answer: N' shape, whatever N is."""
    return [float(is_formatted(text_of(c))) for c in completions]


train = Dataset.from_list(make_problems(400, seed=1))
held = make_problems(args.eval_n, seed=2)
tok = AutoTokenizer.from_pretrained(args.model)
tok.padding_side = "left"


# ── 3. Predict memory from the config alone (chapters 14, 18) ────────────
def gib(n):
    return f"{n / 2**30:,.2f} GiB"


cfg = AutoConfig.from_pretrained(args.model)
with torch.device("meta"):                  # shapes only: no memory used
    shell = AutoModelForCausalLM.from_config(cfg)
N = sum(p.numel() for p in shell.parameters())
L, h, a = cfg.num_hidden_layers, cfg.hidden_size, cfg.num_attention_heads
d_head = getattr(cfg, "head_dim", None) or h // a
prompt_len = len(tok.apply_chat_template(
    make_problems(1, 0)[0]["prompt"], add_generation_prompt=True,
    return_dict=False))
seqs = args.group * args.prompts            # answers decoded together
tokens = prompt_len + args.max_completion   # longest sequence
states = 16 * N                             # fp32 weights, grads, Adam (no
#                                             reference model: beta = 0)
kv = seqs * tokens * 2 * L * cfg.num_key_value_heads * d_head * 2
acts = seqs * tokens * L * h * 2            # checkpointing: layer inputs
print(f"model {args.model}: {N:,} parameters; {seqs} sequences of up to "
      f"{tokens} tokens ({prompt_len} prompt + {args.max_completion})")
print(f"predicted memory: states {gib(states)} + KV cache {gib(kv)} "
      f"+ activations {gib(acts)} = {gib(states + kv + acts)}")
if args.predict_only:
    raise SystemExit


# ── 4. Held-out check, outside the trainer: greedy and sampled ───────────


def evaluate(model, sample):
    texts = [tok.apply_chat_template(p["prompt"], add_generation_prompt=True,
                                     tokenize=False) for p in held]
    enc = tok(texts, return_tensors="pt", padding=True).to(model.device)
    torch.manual_seed(0)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=args.max_completion,
                             do_sample=sample, temperature=1.0, top_k=0,
                             top_p=1.0, pad_token_id=tok.pad_token_id)
    replies = tok.batch_decode(out[:, enc.input_ids.shape[1]:],
                               skip_special_tokens=True)
    acc = sum(is_correct(r, p["answer"]) for r, p in zip(replies, held))
    fmt = sum(is_formatted(r) for r in replies)
    return acc / len(held), fmt / len(held), replies


class Snapshot(TrainerCallback):
    """After each step, keep the rewards and advantages TRL just used."""
    rows = []

    def on_step_end(self, a, state, control, **kw):
        logs = trainer._logs
        self.rows.append((state.global_step,
                          list(logs["rewards"]["correct"]),
                          list(logs["advantages"]),
                          list(logs["completion"])))


# ── 5. Train with TRL ────────────────────────────────────────────────────
G = args.group
cfg = GRPOConfig(
    output_dir="grpo-out", num_generations=G,
    per_device_train_batch_size=G * args.prompts,   # whole groups only
    max_steps=args.steps, learning_rate=args.lr,
    max_completion_length=args.max_completion, temperature=1.0, beta=0.0,
    reward_weights=[1.0, 0.0] if args.reward == "correct" else [0.0, 1.0],
    logging_steps=1, report_to="none", save_strategy="no",
    bf16=(DEVICE == "cuda"), seed=0, data_seed=0, disable_tqdm=True)
trainer = GRPOTrainer(model=args.model, reward_funcs=[correct, formatted],
                      args=cfg, train_dataset=train, processing_class=tok,
                      callbacks=[Snapshot()])
trainer.remove_callback(PrinterCallback)
policy = trainer.model.eval()
print(f"reward optimised: {args.reward}; G={G}, "
      f"{args.prompts} prompts per step, {args.steps} steps")
g0, f0, _ = evaluate(policy, False)
s0, sf0, _ = evaluate(policy, True)
print(f"before: greedy accuracy {g0:.2f} format {f0:.2f}  |  "
      f"sampled accuracy {s0:.2f} format {sf0:.2f}")
trainer.train()
log = [r for r in trainer.state.log_history if "reward" in r]

print(f"\n{'steps':>7} {'reward':>7} {'correct':>8} {'format':>7} "
      f"{'len':>5} {'dead':>5}")      # mean over windows of 5 steps
for k in range(0, len(log), 5):
    w = log[k:k + 5]

    def avg(key):
        return statistics.fmean(r[key] for r in w)
    print(f"{k + 1:>3}-{k + len(w):<3} {avg('reward'):7.3f} "
          f"{avg('rewards/correct/mean'):8.3f} "
          f"{avg('rewards/formatted/mean'):7.3f} "
          f"{avg('completions/mean_length'):5.1f} "
          f"{avg('frac_reward_zero_std'):5.2f}")

policy.eval()
g1, f1, replies = evaluate(policy, False)
s1, sf1, _ = evaluate(policy, True)
print(f"\nafter:  greedy accuracy {g1:.2f} format {f1:.2f}  |  "
      f"sampled accuracy {s1:.2f} format {sf1:.2f}")
for p, r in list(zip(held, replies))[:3]:        # what it writes now
    print(f"  {p['prompt'][0]['content'][:16]:<16} true {p['answer']:>3}"
          f"  reply {r!r}")

# ── 6. One group's advantages, by hand, beside the trainer's ─────────────
if args.reward == "correct":
    for step, rewards, adv, comps in Snapshot.rows:
        for k in range(0, len(rewards), G):
            grp = rewards[k:k + G]
            if 0 < sum(grp) < G:                     # a group with signal
                break
        else:
            continue
        m = statistics.fmean(grp)
        pop, sample = statistics.pstdev(grp), statistics.stdev(grp)
        print(f"\nstep {step}, one group of {G}: rewards {grp}")
        print(f"mean {m:.3f}  population std {pop:.3f}  "
              f"sample std {sample:.3f}")
        print(f"{'i':>2} {'reward':>6} {'chapter':>8} {'by hand':>8} "
              f"{'TRL':>8}")
        for i, r in enumerate(grp):
            print(f"{i + 1:>2} {r:6.1f} {(r - m) / pop:+8.3f} "
                  f"{(r - m) / (sample + 1e-4):+8.3f} "
                  f"{adv[k + i]:+8.3f}")
        break
