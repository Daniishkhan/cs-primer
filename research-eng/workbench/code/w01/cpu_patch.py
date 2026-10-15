"""Make karpathy/autoresearch run on a CPU, and say exactly what changed.

Usage (on the lab VM, inside a fresh copy of the repository):

    python3 cpu_patch.py ~/work/re-build/ar-cpu

Every change is one exact string replacement. If the upstream file has
moved on and a string is not found (or is found a different number of
times), the script stops instead of guessing, so you never run a
half-patched copy. It prints one line per change; the unified diff of
the result is the full record.

The patched copy is NOT the benchmark. Its val_bpb is measured on a
shorter context, a smaller model and a smaller validation slice, so it
cannot be compared with a number from an H100 run.
"""
import os
import sys

# ── 1. The changes ───────────────────────────────────────────────────
# (file, why, old text, new text, times it must occur)
CHANGES = [
    # -- prepare.py: constants of the CPU proxy ------------------------
    ("prepare.py", "shorter context",
     "MAX_SEQ_LEN = 2048       # context length",
     "MAX_SEQ_LEN = 256        # context length (CPU proxy)", 1),
    ("prepare.py", "time budget from the environment, 30 s by default",
     "TIME_BUDGET = 300        # training time budget in seconds (5 minutes)",
     'TIME_BUDGET = int(os.environ.get("AR_BUDGET", "30"))  # seconds (CPU)',
     1),
    ("prepare.py", "validation slice of 262,144 tokens, not about 21M",
     "EVAL_TOKENS = 40 * 524288  # number of tokens for val eval",
     "EVAL_TOKENS = 2**18        # number of tokens for val eval (CPU)", 1),
    # -- prepare.py: no CUDA, no pinned memory -------------------------
    ("prepare.py", "no pinned host memory",
     "cpu_buffer = torch.empty(2 * B * T, dtype=torch.long, pin_memory=True)",
     "cpu_buffer = torch.empty(2 * B * T, dtype=torch.long)", 1),
    ("prepare.py", "the 'GPU' buffer lives on the CPU",
     'gpu_buffer = torch.empty(2 * B * T, dtype=torch.long, device="cuda")',
     'gpu_buffer = torch.empty(2 * B * T, dtype=torch.long, device="cpu")', 1),
    ("prepare.py", "plain synchronous copy",
     "gpu_buffer.copy_(cpu_buffer, non_blocking=True)",
     "gpu_buffer.copy_(cpu_buffer)", 1),
    ("prepare.py", "token byte table on the CPU",
     'token_bytes = get_token_bytes(device="cuda")',
     'token_bytes = get_token_bytes(device="cpu")', 1),
    # -- train.py: attention without the FlashAttention 3 kernel -------
    ("train.py", "drop the CUDA-only FlashAttention 3 import",
     'from kernels import get_kernel\n'
     'cap = torch.cuda.get_device_capability()\n'
     '# varunneal\'s FA3 is Hopper only, use kernels-community on non-Hopper '
     'GPUs\n'
     'repo = "varunneal/flash-attention-3" if cap == (9, 0) else '
     '"kernels-community/flash-attn3"\n'
     'fa3 = get_kernel(repo).flash_attn_interface\n',
     '_MASKS = {}\n\n\n'
     'def windowed_attention(q, k, v, window):\n'
     '    """Causal attention over the last `window` tokens (CPU stand-in).\n\n'
     '    q, k, v are (B, T, heads, head_dim), as the FA3 call expects.\n'
     '    """\n'
     '    T = q.size(1)\n'
     '    if (window, T) not in _MASKS:\n'
     '        i = torch.arange(T)[:, None]\n'
     '        j = torch.arange(T)[None, :]\n'
     '        _MASKS[(window, T)] = (j <= i) & (j >= i - window)\n'
     '    q, k, v = (t.transpose(1, 2) for t in (q, k, v))\n'
     '    y = F.scaled_dot_product_attention(\n'
     '        q, k, v, attn_mask=_MASKS[(window, T)])\n'
     '    return y.transpose(1, 2)\n', 1),
    ("train.py", "call the stand-in",
     "y = fa3.flash_attn_func(q, k, v, causal=True, "
     "window_size=window_size)",
     "y = windowed_attention(q, k, v, window_size[0])", 1),
    # -- train.py: eager mode instead of torch.compile -----------------
    ("train.py", "no torch.compile on the optimiser kernels",
     "@torch.compile(dynamic=False, fullgraph=True)\n", "", 2),
    ("train.py", "no torch.compile on the model",
     "model = torch.compile(model, dynamic=False)\n", "", 1),
    # -- train.py: device, seed, no CUDA calls -------------------------
    ("train.py", "CPU device, bfloat16 autocast, seed from the environment",
     'torch.manual_seed(42)\n'
     'torch.cuda.manual_seed(42)\n'
     'torch.set_float32_matmul_precision("high")\n'
     'device = torch.device("cuda")\n'
     'autocast_ctx = torch.amp.autocast(device_type="cuda", '
     'dtype=torch.bfloat16)\n',
     'torch.manual_seed(int(os.environ.get("AR_SEED", "42")))\n'
     'device = torch.device("cpu")\n'
     'autocast_ctx = torch.amp.autocast(device_type="cpu", '
     'dtype=torch.bfloat16)\n', 1),
    ("train.py", "nothing to synchronise on a CPU",
     "    torch.cuda.synchronize()\n", "", 2),
    ("train.py", "no GPU memory to report",
     "peak_vram_mb = torch.cuda.max_memory_allocated() / 1024 / 1024",
     "peak_vram_mb = 0.0  # no GPU on this machine", 1),
    # -- train.py: a smaller model and batch ---------------------------
    ("train.py", "8K tokens per optimiser step, not 524K",
     "TOTAL_BATCH_SIZE = 2**19 # ~524K tokens per optimizer step",
     "TOTAL_BATCH_SIZE = 2**13 # ~8K tokens per optimizer step (CPU)", 1),
    ("train.py", "model width 32 x depth, not 64 x depth",
     "ASPECT_RATIO = 64       # model_dim = depth * ASPECT_RATIO",
     "ASPECT_RATIO = 32       # model_dim = depth * ASPECT_RATIO (CPU)", 1),
    ("train.py", "head dimension 64, not 128",
     "HEAD_DIM = 128          # target head dimension for attention",
     "HEAD_DIM = 64           # target head dimension for attention (CPU)", 1),
    ("train.py", "4 layers, not 8",
     "DEPTH = 8               # number of transformer layers",
     "DEPTH = 4               # number of transformer layers (CPU)", 1),
    ("train.py", "32 sequences of 256 tokens per forward pass",
     "DEVICE_BATCH_SIZE = 128  # per-device batch size (reduce if OOM)",
     "DEVICE_BATCH_SIZE = 32   # per-device batch size (CPU)", 1),
    # -- train.py: an optional step budget (off unless AR_STEPS is set)
    ("train.py", "LR schedule can follow steps instead of seconds",
     "    progress = min(total_training_time / TIME_BUDGET, 1.0)\n",
     "    progress = min(total_training_time / TIME_BUDGET, 1.0)\n"
     "    if STEP_BUDGET:\n"
     "        progress = min(step / STEP_BUDGET, 1.0)\n", 1),
    ("train.py", "stop after AR_STEPS steps when it is set",
     "    if step > 10 and total_training_time >= TIME_BUDGET:\n",
     "    if STEP_BUDGET and step >= STEP_BUDGET:\n"
     "        break\n"
     "    if not STEP_BUDGET and step > 10 and "
     "total_training_time >= TIME_BUDGET:\n", 1),
    ("train.py", "read AR_STEPS (0 means: use the time budget)",
     "t_start = time.time()\n",
     "t_start = time.time()\n"
     "STEP_BUDGET = int(os.environ.get(\"AR_STEPS\", \"0\"))\n", 1),
]


# ── 2. Apply them, strictly ──────────────────────────────────────────
def main(repo):
    texts = {}
    for name in ("train.py", "prepare.py"):
        with open(os.path.join(repo, name), encoding="utf-8") as fh:
            texts[name] = fh.read()
    for name, why, old, new, times in CHANGES:
        found = texts[name].count(old)
        if found != times:
            sys.exit(f"{name}: expected {times} x {old[:50]!r}, "
                     f"found {found}. Upstream has changed; stopping.")
        texts[name] = texts[name].replace(old, new)
        print(f"{name:11s} {why}")
    for name, text in texts.items():
        with open(os.path.join(repo, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"{len(CHANGES)} changes applied to {repo}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
