"""What does autoresearch's five-minute H100 budget buy? Arithmetic only.

Usage (lab VM, inside or pointing at the patched checkout):

    python3 h100_budget.py --repo ~/work/re-build/ar-cpu

It builds autoresearch's own GPT class on PyTorch's meta device (shapes,
no weights) for two settings: the published H100 setting and the CPU
proxy of this workbench. It then turns FLOPs per token into tokens per
budget. Nothing is trained and no GPU is needed.
"""
import argparse
import os
import sys

import torch

# ── 1. Settings ──────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.path.expanduser("~/work/re-build/ar-cpu"))
args, _ = ap.parse_known_args()        # notebooks pass their own flags

H100_PEAK = 989.5e12      # bf16 FLOP/s, the constant train.py divides by
BUDGET_S = 300            # published training budget, seconds
CHINCHILLA = 20           # tokens per parameter (nanochat's help text)
MFU_GUESSES = (0.25, 0.40, 0.50)    # ASSUMPTIONS: the script prints the
                                    # real mfu_percent when you measure
SETTINGS = {              # depth, aspect, head_dim, seq_len, batch tokens
    "H100 (published)": (8, 64, 128, 2048, 2 ** 19),
    "CPU proxy (here)": (4, 32, 64, 256, 2 ** 13),
}


# ── 2. Load the model classes from the real train.py ─────────────────
sys.path.insert(0, args.repo)
os.chdir(args.repo)
src = open("train.py").read()
src = src.split("# Hyperparameters (edit these")[0]    # classes only
ns = {"__name__": "train_defs"}
exec(compile(src, "train.py", "exec"), ns)
GPT, GPTConfig = ns["GPT"], ns["GPTConfig"]


# ── 3. Count parameters and FLOPs per token for each setting ─────────
def build(depth, aspect, head_dim, seq_len):
    dim = -(-depth * aspect // head_dim) * head_dim
    cfg = GPTConfig(sequence_len=seq_len, vocab_size=8192, n_layer=depth,
                    n_head=dim // head_dim, n_kv_head=dim // head_dim,
                    n_embd=dim, window_pattern="SSSL")
    with torch.device("meta"):
        return GPT(cfg), dim


for name, (depth, aspect, hd, seq, batch) in SETTINGS.items():
    model, dim = build(depth, aspect, hd, seq)
    counts = model.num_scaling_params()
    scaling = counts["transformer_matrices"] + counts["lm_head"]
    flops = model.estimate_flops()
    print(f"{name}: depth {depth}, width {dim}, "
          f"{counts['total'] / 1e6:.1f} M parameters "
          f"({scaling / 1e6:.1f} M that count for scaling)")
    print(f"  FLOPs per token (fwd+bwd): {flops / 1e6:.1f} M, "
          f"batch {batch:,} tokens")
    if name.startswith("H100"):
        # ── 4. Tokens in the budget, at assumed utilisation ──────────
        for mfu in MFU_GUESSES:
            tokens = H100_PEAK * mfu * BUDGET_S / flops
            print(f"  at {mfu:.0%} MFU: {tokens / 1e6:6.0f} M tokens, "
                  f"{tokens / batch:5.0f} steps, "
                  f"{tokens / scaling:4.1f} tokens per scaling parameter")
        print(f"  Chinchilla-style target: {CHINCHILLA} tokens per "
              f"parameter = {CHINCHILLA * scaling / 1e6:.0f} M tokens")
