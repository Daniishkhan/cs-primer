"""LoRA, then QLoRA: predict the adapter's size from chapter 11's equation,
check it against PEFT, fine-tune a small model end to end, and predict what
the 4-bit version would need on a GPU.

Lab VM (SmolLM2-135M, LoRA, about ten minutes on the CPU):
    python lora_qlora.py
Prediction only for a bigger model (reads config.json, downloads no weights):
    python lora_qlora.py --model Qwen/Qwen2.5-1.5B --predict-only
GPU box (4-bit base, needs bitsandbytes; not run by the authors):
    python lora_qlora.py --model Qwen/Qwen2.5-1.5B --qlora

Needs: torch, transformers, peft (workbench/requirements.txt);
--qlora also needs bitsandbytes (workbench/requirements-gpu.txt)."""
import argparse
import time

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M")
ap.add_argument("--rank", type=int, default=8)          # r in the equation
ap.add_argument("--alpha", type=int, default=16)        # numerator of alpha/r
ap.add_argument("--targets", default="q_proj,k_proj,v_proj,o_proj,"
                "gate_proj,up_proj,down_proj")
ap.add_argument("--steps", type=int, default=40)
ap.add_argument("--lr", type=float, default=2e-4)
ap.add_argument("--predict-only", action="store_true")
ap.add_argument("--qlora", action="store_true")         # GPU: 4-bit base
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
TARGETS = args.targets.split(",")
r = args.rank


def mib(n):
    return f"{n / 2**20:,.1f} MiB"


# ── 2. Predict the trainable parameters (chapter 11, eq-lora) ────────────
# Each adapted matrix W0 (d_out x d_in) gains B (d_out x r) and A (r x d_in),
# so r * (d_in + d_out) numbers. The shapes come from config.json.
cfg = AutoConfig.from_pretrained(args.model)
L, h = cfg.num_hidden_layers, cfg.hidden_size
heads = cfg.num_attention_heads
kv = getattr(cfg, "num_key_value_heads", None) or heads
d_head = getattr(cfg, "head_dim", None) or h // heads
ffn = cfg.intermediate_size
SHAPES = {                                   # name: (d_in, d_out)
    "q_proj": (h, heads * d_head), "k_proj": (h, kv * d_head),
    "v_proj": (h, kv * d_head), "o_proj": (heads * d_head, h),
    "gate_proj": (h, ffn), "up_proj": (h, ffn), "down_proj": (ffn, h),
}
per_layer = {t: r * sum(SHAPES[t]) for t in TARGETS}
predicted = L * sum(per_layer.values())
with torch.device("meta"):                   # shapes only: no memory used
    shell = AutoModelForCausalLM.from_config(cfg)
N = sum(p.numel() for p in shell.parameters())
print(f"model {args.model}: L={L}, h={h}, heads={heads}, kv heads={kv}, "
      f"d_head={d_head}, ffn={ffn}")
print(f"LoRA r={r}, alpha={args.alpha}, scale alpha/r = {args.alpha / r:g}")
for t in TARGETS:
    d_in, d_out = SHAPES[t]
    print(f"  {t:10} W0 is {d_out:>5} x {d_in:<5} -> r*(d_in+d_out) = "
          f"{per_layer[t]:>7,} per layer")
print(f"predicted trainable: {L} layers x {sum(per_layer.values()):,} = "
      f"{predicted:,} of {N:,} ({100 * predicted / N:.2f}%)")
print(f"full fine-tuning would train all {N:,}: "
      f"{N / predicted:,.0f}x more")

# ── 3. Predict the 4-bit base (chapter 11, QLoRA) ────────────────────────
NF4_BITS = 4 + 8 / 64 + 32 / (64 * 256)      # code + double-quantised scale
blocks = sum(p.numel() for n, p in shell.named_parameters()
             if "layers." in n and p.dim() == 2)        # the linear weights
rest = N - blocks                    # embeddings and norms stay in bf16
GB = 1e9
bf16_base = N * 2
nf4_base = blocks * NF4_BITS / 8 + rest * 2
adapter_state = predicted * 16               # fp32 weight+grad+2 Adam
tokens, bsz = 512, 4                         # one micro-batch of 4 x 512
act = (L * 2 * tokens * bsz * h + 34 * tokens * bsz * h
       + 4 * tokens * bsz * cfg.vocab_size)  # checkpointed (chapter 14)
print(f"\nQLoRA prediction for {args.model} (batch {bsz} x {tokens}):")
print(f"  linear weights in blocks {blocks:,} -> {NF4_BITS:.3f} bits each")
print(f"  base in bf16        {bf16_base / GB:6.2f} GB")
print(f"  base in NF4         {nf4_base / GB:6.2f} GB "
      f"(embeddings and norms {rest * 2 / GB:.2f} GB stay bf16)")
print(f"  adapter + Adam      {adapter_state / GB:6.2f} GB")
print(f"  activations         {act / GB:6.2f} GB (checkpointed)")
print(f"  fixed overhead      {1.5:6.2f} GB (assumption, chapter 2)")
extra = adapter_state + act + 1.5 * GB
print(f"  total, LoRA on bf16 {(bf16_base + extra) / GB:6.2f} GB   "
      f"QLoRA {(nf4_base + extra) / GB:6.2f} GB")
if args.predict_only:
    raise SystemExit

# ── 4. Load, wrap in LoRA and let PEFT count ─────────────────────────────
torch.manual_seed(0)
tok = AutoTokenizer.from_pretrained(args.model)
if args.qlora:
    if DEVICE != "cuda":
        raise SystemExit("--qlora needs an NVIDIA GPU and bitsandbytes")
    from transformers import BitsAndBytesConfig
    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, quantization_config=bnb, device_map={"": 0})
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()      # checkpointing needs this
else:
    model = AutoModelForCausalLM.from_pretrained(args.model,
                                                 dtype=torch.float32)
    model = model.to(DEVICE)
conf = LoraConfig(r=r, lora_alpha=args.alpha, target_modules=TARGETS,
                  lora_dropout=0.0, task_type="CAUSAL_LM")
model = get_peft_model(model, conf)
model.print_trainable_parameters()
real = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"predicted {predicted:,}  PEFT {real:,}  "
      f"-> {'exact match' if real == predicted else 'MISMATCH'}")

# ── 5. A tiny task: answer in a format the base model does not use ───────
CAPITALS = [
    ("France", "Paris"), ("Germany", "Berlin"), ("Italy", "Rome"),
    ("Spain", "Madrid"), ("Portugal", "Lisbon"), ("Norway", "Oslo"),
    ("Sweden", "Stockholm"), ("Finland", "Helsinki"), ("Poland", "Warsaw"),
    ("Austria", "Vienna"), ("Greece", "Athens"), ("Ireland", "Dublin"),
    ("Hungary", "Budapest"), ("Denmark", "Copenhagen"), ("Russia", "Moscow"),
    ("Egypt", "Cairo"), ("Kenya", "Nairobi"), ("Japan", "Tokyo"),
    ("China", "Beijing"), ("India", "New Delhi"), ("Peru", "Lima"),
    ("Chile", "Santiago"), ("Cuba", "Havana"), ("Canada", "Ottawa"),
    ("Turkey", "Ankara"), ("Iran", "Tehran"), ("Iraq", "Baghdad"),
    ("Thailand", "Bangkok"), ("Vietnam", "Hanoi"), ("Ghana", "Accra"),
    ("Morocco", "Rabat"), ("Argentina", "Buenos Aires"),
    ("Belgium", "Brussels"), ("Netherlands", "Amsterdam"),
    ("Switzerland", "Bern"), ("Czechia", "Prague"),
    ("Ukraine", "Kyiv"), ("Colombia", "Bogota"),
    ("Nepal", "Kathmandu"), ("Jordan", "Amman"), ("Libya", "Tripoli"),
    ("Mexico", "Mexico City"), ("Romania", "Bucharest"),
]
train, held = CAPITALS[:32], CAPITALS[32:]
print(f"\ntask: 'Country: X' -> 'Capital: [[Y]]'; {len(train)} train, "
      f"{len(held)} held-out countries")


def encode(country, capital):
    """Tokens of the whole line; the loss counts only the answer tokens."""
    prompt = tok(f"Country: {country}\nCapital:")["input_ids"]
    answer = tok(f" [[{capital}]]")["input_ids"] + [tok.eos_token_id]
    ids = prompt + answer
    labels = [-100] * len(prompt) + answer
    return ids, labels


def batch_of(pairs):
    enc = [encode(c, k) for c, k in pairs]
    n = max(len(i) for i, _ in enc)
    pad = tok.eos_token_id
    ids = torch.tensor([i + [pad] * (n - len(i)) for i, _ in enc])
    lab = torch.tensor([x + [-100] * (n - len(x)) for _, x in enc])
    att = torch.tensor([[1] * len(i) + [0] * (n - len(i)) for i, _ in enc])
    return ids.to(DEVICE), lab.to(DEVICE), att.to(DEVICE)


def held_loss():
    model.eval()
    ids, lab, att = batch_of(held)
    with torch.no_grad():
        return model(input_ids=ids, attention_mask=att, labels=lab).loss.item()


def say(country):
    model.eval()
    ids = tok(f"Country: {country}\nCapital:", return_tensors="pt")
    ids = {k: v.to(DEVICE) for k, v in ids.items()}
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=8, do_sample=False,
                             pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][ids["input_ids"].shape[1]:],
                      skip_special_tokens=True).strip().split("\n")[0]


before = held_loss()
print(f"held-out loss before: {before:.3f}")
print("  ", " | ".join(f"{c} -> {say(c)}" for c, _ in held[:3]))

# ── 6. Train only the adapter, with a hand-written loop ──────────────────
params = [p for p in model.parameters() if p.requires_grad]
opt = torch.optim.AdamW(params, lr=args.lr)
t0 = time.perf_counter()
for step in range(args.steps):
    model.train()
    start = (step * 8) % len(train)
    pairs = (train + train)[start:start + 8]
    ids, lab, att = batch_of(pairs)
    loss = model(input_ids=ids, attention_mask=att, labels=lab).loss
    loss.backward()
    opt.step()
    opt.zero_grad()
    if step % 10 == 0 or step == args.steps - 1:
        print(f"  step {step:3d}  train loss {loss.item():.3f}")
secs = time.perf_counter() - t0
after = held_loss()
print(f"held-out loss after:  {after:.3f}  ({secs:.0f} s on {DEVICE})")
print("  ", " | ".join(f"{c} -> {say(c)}" for c, _ in held[:3]))

# ── 7. What the optimiser kept, and merging the adapter back ─────────────
adam = sum(t.numel() * t.element_size() for st in opt.state.values()
           for t in st.values() if torch.is_tensor(t) and t.dim() > 0)
print(f"\nAdam state held: {mib(adam)}; full fine-tuning would hold "
      f"{mib(N * 8)} (8 bytes x {N:,})")
model.eval()
probe, _, att = batch_of(held[:2])
with torch.no_grad():
    with_adapter = model(input_ids=probe, attention_mask=att).logits
    merged = model.merge_and_unload()           # W = W0 + (alpha/r) B A
    without = merged(input_ids=probe, attention_mask=att).logits
print(f"merged weights vs adapter: max |logit difference| = "
      f"{(with_adapter - without).abs().max().item():.1e}")
