"""Where training memory goes: predict weights, gradients, Adam state and
activations from chapter 2's accounting, then add up the real tensors after
one training step and compare.

Lab VM (SmolLM2-135M, 32-bit floats, CPU):
    python training_memory.py
GPU box (a 0.5B model, with CUDA's own peak counters per phase):
    python training_memory.py --model Qwen/Qwen2.5-0.5B --batch 4 --seq 512
    python training_memory.py --model Qwen/Qwen2.5-0.5B --sweep
Prediction only, no weights downloaded (reads config.json):
    python training_memory.py --model Qwen/Qwen2.5-1.5B --predict-only

Needs: torch, transformers (workbench/requirements.txt)."""
import argparse

import torch
from transformers import AutoConfig, AutoModelForCausalLM

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M")
ap.add_argument("--dtype", default="fp32", choices=["fp32", "bf16"])
ap.add_argument("--batch", type=int, default=4)        # sequences per step
ap.add_argument("--seq", type=int, default=256)        # tokens per sequence
ap.add_argument("--checkpoint", action="store_true")   # recompute layers
ap.add_argument("--predict-only", action="store_true")
ap.add_argument("--sweep", action="store_true")        # GPU: batch to OOM
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
DTYPE = torch.float32 if args.dtype == "fp32" else torch.bfloat16
B = torch.tensor([], dtype=DTYPE).element_size()      # bytes per number


def mib(n):
    return f"{n / 2**20:,.1f} MiB"


# ── 2. Predict from the config alone (chapter 2) ─────────────────────────
cfg = AutoConfig.from_pretrained(args.model)
with torch.device("meta"):                  # shapes only: no memory used
    shell = AutoModelForCausalLM.from_config(cfg)
N = sum(p.numel() for p in shell.parameters())    # tied weights count once
L, h, a = cfg.num_hidden_layers, cfg.hidden_size, cfg.num_attention_heads
s, b = args.seq, args.batch
W = N * B                                   # weights
G = N * B                                   # one gradient per weight
O = 2 * N * B                               # Adam: m and v, same dtype
# Korthikanti et al. (2022): bytes per layer for 16-bit activations,
# scaled by B / 2 for other widths. Checkpointing keeps only layer inputs.
per_layer = s * b * h * (34 + 5 * a * s / h) * B / 2
A = L * (s * b * h * B if args.checkpoint else per_layer)
print(f"model {args.model}: {N:,} parameters, {B} bytes each, "
      f"L={L}, h={h}, heads={a}")
print(f"step shape: batch {b} x {s} tokens, device {DEVICE}"
      f"{', checkpointed' if args.checkpoint else ''}")
print(f"predicted weights     {mib(W):>12}   ({B} B x N)")
print(f"predicted gradients   {mib(G):>12}   ({B} B x N)")
print(f"predicted Adam state  {mib(O):>12}   (2 x {B} B x N)")
print(f"predicted activations {mib(A):>12}   (chapter 2 formula)")
print(f"predicted model states {mib(W + G + O):>11}   "
      f"= {(W + G + O) / N:.0f} bytes per parameter")
print(f"predicted peak        {mib(max(W + A, W + G + O)):>12}   "
      "(larger of: end of forward, or after the update)")
if args.predict_only:
    raise SystemExit

# ── 3. Measure: one real training step, summing real tensors ─────────────
torch.manual_seed(0)
model = AutoModelForCausalLM.from_pretrained(args.model, dtype=DTYPE)
model = model.to(DEVICE).train()
if args.checkpoint:
    model.gradient_checkpointing_enable()
opt = torch.optim.AdamW(model.parameters(), lr=1e-5)
param_ptrs = {p.untyped_storage().data_ptr() for p in model.parameters()}


def allocated():
    """Bytes the allocator holds now (None on CPU, which has no counter)."""
    if DEVICE == "cuda":
        return torch.cuda.memory_allocated()


def peak():
    if DEVICE == "cuda":
        return torch.cuda.max_memory_allocated()


saved = {}                                  # storage address -> bytes


def pack(t):
    """Called for every tensor autograd keeps for the backward pass."""
    st = t.untyped_storage()
    if st.data_ptr() not in param_ptrs:     # weights are not activations
        saved[st.data_ptr()] = st.nbytes()
    return t


def step(batch):
    saved.clear()
    ids = torch.randint(0, cfg.vocab_size, (batch, s), device=DEVICE)
    if DEVICE == "cuda":
        torch.cuda.reset_peak_memory_stats()
    rows = [("load", allocated(), peak())]
    with torch.autograd.graph.saved_tensors_hooks(pack, lambda t: t):
        loss = model(ids, labels=ids).loss
    rows.append(("forward", allocated(), peak()))
    act = sum(saved.values())
    loss.backward()
    rows.append(("backward", allocated(), peak()))
    opt.step()
    rows.append(("step", allocated(), peak()))
    return rows, act


rows, act = step(b)
w_m = sum(p.numel() * p.element_size() for p in model.parameters())
g_m = sum(p.grad.numel() * p.grad.element_size() for p in model.parameters()
          if p.grad is not None)
o_m = sum(t.numel() * t.element_size()
          for st in opt.state.values() for t in st.values()
          if torch.is_tensor(t) and t.dim() > 0)    # skip the step counter
print()
print(f"{'':22}{'predicted':>14}{'measured':>14}{'measured/pred':>15}")
for name, pred, got in (("weights", W, w_m), ("gradients", G, g_m),
                        ("Adam state", O, o_m), ("activations", A, act)):
    print(f"{name:22}{mib(pred):>14}{mib(got):>14}{got / pred:>15.3f}")
if DEVICE != "cpu":
    print(f"\nallocator after each phase ({DEVICE}):")
    for name, now, pk in rows:
        extra = f", peak during phase {mib(pk)}" if pk is not None else ""
        print(f"  {name:9}{mib(now):>12}{extra}")

# ── 4. GPU only: double the batch until the card runs out ────────────────
if args.sweep and DEVICE == "cuda":
    print("\nsweep (peak allocated memory in one step):")
    bs = b
    while True:
        try:
            opt.zero_grad(set_to_none=True)
            r, a_m = step(bs)
            print(f"  batch {bs:4d}: peak {mib(r[-1][2])}, "
                  f"activations {mib(a_m)}")
            bs *= 2
        except torch.OutOfMemoryError:
            print(f"  batch {bs:4d}: out of memory")
            break
