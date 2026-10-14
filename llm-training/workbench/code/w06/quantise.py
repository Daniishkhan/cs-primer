"""Quantise a model's linear layers yourself, then measure perplexity.

Absmax quantisation (chapter 19): s = max|w| / q_max, q = round(w / s).
int8 uses one scale per output row; int4 uses one scale per group of 128
weights along a row. We store nothing packed: each weight is quantised and
dequantised in place, so the model runs unchanged and perplexity shows
what the rounding cost. Memory is predicted from the packed layout.

Laptop (SmolLM2-135M, about 270 MB download, WikiText-2 test):
    python quantise.py
GPU box (a 7B model; add --tokens 16384):
    python quantise.py --model Qwen/Qwen2.5-7B-Instruct

Needs: torch, transformers, datasets (workbench/requirements.txt)."""
import argparse
import math

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M")
ap.add_argument("--tokens", type=int, default=4096)   # text to score
ap.add_argument("--window", type=int, default=512)    # tokens per window
ap.add_argument("--group", type=int, default=128)     # int4 group size
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if torch.cuda.is_available():
    DEVICE = "cuda"          # a 7B model needs 16-bit compute to fit
elif torch.backends.mps.is_available():
    DEVICE = "mps"
else:
    DEVICE = "cpu"
COMPUTE = torch.bfloat16 if DEVICE == "cuda" else torch.float32
torch.manual_seed(0)


# ── 2. Absmax quantisation, written out ──────────────────────────────────
def absmax_quantise(w, bits, group=None):
    """Return (dequantised w, number of scales). Rows are output channels;
    group=None gives one scale per row, else one per `group` weights."""
    q_max = 2 ** (bits - 1) - 1                      # 127 or 7
    rows, cols = w.shape
    g = group or cols
    while cols % g:                  # 576 columns: 128 does not divide
        g //= 2                      # so fall back to 64
    blocks = w.float().reshape(rows, cols // g, g)   # maths in fp32
    s = blocks.abs().amax(dim=-1, keepdim=True) / q_max   # s = max|w|/qmax
    s = s.clamp(min=1e-12)
    q = torch.round(blocks / s).clamp(-q_max, q_max)      # q = round(w/s)
    return (q * s).reshape(rows, cols).to(w.dtype), s.numel()  # w_hat


def quantise_model(model, bits, group=None):
    """Quantise every nn.Linear except the output head. Returns the
    predicted packed size in bytes of the quantised layers."""
    packed = 0
    for name, mod in model.named_modules():
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in name:
            w_hat, n_scales = absmax_quantise(mod.weight.data, bits, group)
            mod.weight.data = w_hat
            packed += mod.weight.numel() * bits // 8 + n_scales * 2
    return packed


# ── 3. Perplexity on a fixed sample ──────────────────────────────────────
tok = AutoTokenizer.from_pretrained(args.model)
text = "\n\n".join(load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1",
                                split="test")["text"])
ids = tok(text, return_tensors="pt").input_ids[0][:args.tokens]
windows = ids[: len(ids) // args.window * args.window].view(
    -1, args.window).to(DEVICE)
print(f"{args.model} on {DEVICE}; {windows.numel()} WikiText-2 test tokens "
      f"in {len(windows)} windows of {args.window}")


@torch.no_grad()
def perplexity(model):
    nll, n = 0.0, 0
    for x in windows:
        logits = model(x[None]).logits[0, :-1].float()
        loss = torch.nn.functional.cross_entropy(logits, x[1:],
                                                 reduction="sum")
        nll, n = nll + loss.item(), n + len(x) - 1
    return math.exp(nll / n)


def fresh():
    m = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)
    return m.to(COMPUTE).to(DEVICE).eval()   # bf16 values; fp32 off-GPU


# ── 4. Predict, quantise, measure ────────────────────────────────────────
model = fresh()
lin = sum(m.weight.numel() for n, m in model.named_modules()
          if isinstance(m, torch.nn.Linear) and "lm_head" not in n)
total = sum(p.numel() for p in model.parameters())
other = total - lin                  # embeddings, norms: left in 16 bits
print(f"{total / 1e6:.1f}M parameters, {lin / 1e6:.1f}M in quantised "
      f"linear layers, {other / 1e6:.1f}M left in 16 bits")
print(f"\n{'format':<22}{'predicted MiB':>14}{'perplexity':>12}")
base = perplexity(model)
mib = (lin * 2 + other * 2) / 2**20
print(f"{'16-bit (bf16 values)':<22}{mib:>14.1f}{base:>12.3f}")
del model

for label, bits, group in (("int8, per channel", 8, None),
                           (f"int4, group {args.group}", 4, args.group),
                           ("int4, per channel", 4, None)):
    model = fresh()
    packed = quantise_model(model, bits, group)
    mib = (packed + other * 2) / 2**20
    ppl = perplexity(model)
    print(f"{label:<22}{mib:>14.1f}{ppl:>12.3f}   "
          f"({ppl / base:.3f}x the 16-bit perplexity)")
    del model
    if DEVICE == "cuda":
        torch.cuda.empty_cache()
