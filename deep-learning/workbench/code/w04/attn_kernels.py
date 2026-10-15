"""Attention kernels, benchmarked: naive attention against PyTorch's fused
scaled_dot_product_attention, as the sequence gets longer.

Chapter 19 says the naive version writes a T x T score matrix and its
softmax to memory, and that FlashAttention never does. The script predicts
the memory from that sentence, then measures peak memory and time.

Lab VM (CPU):
    python attn_kernels.py
    python attn_kernels.py --device cpu
GPU box (adds CUDA's flash, memory-efficient and math backends, 16-bit):
    python attn_kernels.py --lengths 1024 4096 16384 --heads 32 --dim 128

Needs: torch (workbench/requirements.txt). No downloads."""
import argparse
import math
import statistics
import time

import torch
import torch.nn.functional as F
from torch.profiler import ProfilerActivity, profile

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--lengths", type=int, nargs="+",
                default=[256, 512, 1024, 2048, 4096])
ap.add_argument("--heads", type=int, default=8)
ap.add_argument("--dim", type=int, default=64)        # head width d_k
ap.add_argument("--device", default="auto")           # auto: CUDA, CPU
ap.add_argument("--repeats", type=int, default=5)
args, _ = ap.parse_known_args()        # notebooks pass their own flags

if args.device != "auto":
    DEVICE = args.device
elif torch.cuda.is_available():
    DEVICE = "cuda"
else:
    DEVICE = "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
BYTES = torch.tensor([], dtype=DTYPE).element_size()
B, H, D = 1, args.heads, args.dim
torch.manual_seed(0)


def mib(n):
    return n / 2**20


def sync():
    if DEVICE == "cuda":
        torch.cuda.synchronize()


# ── 2. The two implementations ───────────────────────────────────────────


def naive(q, k, v):
    """Chapter 9's formula, one step per line: S, mask, P, then P V."""
    T = q.shape[-2]
    s = (q @ k.transpose(-1, -2)) / math.sqrt(q.shape[-1])    # S: T x T
    mask = torch.ones(T, T, dtype=torch.bool, device=q.device).triu(1)
    s = s.masked_fill(mask, float("-inf"))
    return torch.softmax(s, dim=-1) @ v                       # P: T x T


def fused(q, k, v):
    """One call; PyTorch picks a tiled kernel that never forms S."""
    return F.scaled_dot_product_attention(q, k, v, is_causal=True)


def make(T, device, dtype):
    return [torch.randn(B, H, T, D, device=device, dtype=dtype)
            for _ in range(3)]


# ── 3. Predict (chapter 19) ──────────────────────────────────────────────
# S has B*H*T*T numbers; the softmax writes a second T x T matrix while S is
# still alive. The fused kernel keeps only the output, B*H*T*D numbers.
print(f"device {DEVICE}, {DTYPE}, B={B} H={H} d_k={D}, torch "
      f"{torch.__version__}")
print("\n== predicted, before measuring ==")
print(f"{'T':>6} {'one T x T (MiB)':>16} {'naive peak = 2x':>16} "
      f"{'fused = output':>15} {'attention GFLOP':>16}")
for T in args.lengths:
    one = B * H * T * T * BYTES
    out = B * H * T * D * BYTES
    gflop = 4 * B * H * T * T * D / 1e9      # Q K^T and P V, 2 FLOPs each
    print(f"{T:6d} {mib(one):16.2f} {mib(2 * one):16.2f} "
          f"{mib(out):15.2f} {gflop:16.2f}")

# ── 4. Same answer? ──────────────────────────────────────────────────────
q, k, v = make(512, DEVICE, DTYPE)
err = (naive(q, k, v).float() - fused(q, k, v).float()).abs().max().item()
print(f"\nmax |naive - fused| at T=512: {err:.2e}  (same maths, rounded "
      f"differently)")


# ── 5. Measure peak memory ───────────────────────────────────────────────


def peak_bytes(fn, T):
    """Peak extra memory while fn runs, inputs excluded."""
    if DEVICE == "cuda":
        q, k, v = make(T, "cuda", DTYPE)
        torch.cuda.synchronize()
        base = torch.cuda.memory_allocated()
        torch.cuda.reset_peak_memory_stats()
        try:
            out = fn(q, k, v)
        except torch.OutOfMemoryError:
            return None
        torch.cuda.synchronize()
        return torch.cuda.max_memory_allocated() - base
    # No CUDA peak counter here, so use the CPU: add up the profiler's
    # allocations and frees in time order and keep the maximum.
    q, k, v = make(T, "cpu", DTYPE)
    with profile(activities=[ProfilerActivity.CPU],
                 profile_memory=True) as prof:
        out = fn(q, k, v)
    steps = sorted((e.time_range.start, e.self_cpu_memory_usage)
                   for e in prof.events() if e.self_cpu_memory_usage)
    now = peak = 0
    for _, delta in steps:
        now += delta
        peak = max(peak, now)
    return peak


where = "CUDA" if DEVICE == "cuda" else "CPU, float32"
print(f"\n== peak memory (measured on {where}) ==")
print(f"{'T':>6} {'naive MiB':>10} {'/ 2x pred':>10} {'fused MiB':>10} "
      f"{'/ out pred':>10}")
for T in args.lengths:
    n, f = peak_bytes(naive, T), peak_bytes(fused, T)
    out = B * H * T * D * BYTES
    if n is None:
        print(f"{T:6d} {'OOM':>10}")
        continue
    print(f"{T:6d} {mib(n):10.2f} {n / (2 * B * H * T * T * BYTES):10.3f} "
          f"{mib(f):10.2f} {f / out:10.3f}")

# ── 6. Measure time on the chosen device ─────────────────────────────────


def median_ms(fn, q, k, v):
    fn(q, k, v)                                          # warm up
    sync()
    times = []
    for _ in range(args.repeats):
        t0 = time.perf_counter()
        fn(q, k, v)
        sync()
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times)


print(f"\n== time per call on {DEVICE} (median of {args.repeats}) ==")
print(f"{'T':>6} {'naive ms':>9} {'fused ms':>9} {'speed-up':>9} "
      f"{'naive GFLOP/s':>14} {'fused GFLOP/s':>14}")
for T in args.lengths:
    try:
        q, k, v = make(T, DEVICE, DTYPE)
        tn, tf = median_ms(naive, q, k, v), median_ms(fused, q, k, v)
    except (torch.OutOfMemoryError, RuntimeError) as e:
        print(f"{T:6d}  failed: {str(e)[:50]}")
        continue
    g = 4 * B * H * T * T * D / 1e9                      # nominal FLOPs
    print(f"{T:6d} {tn:9.2f} {tf:9.2f} {tn / tf:9.2f} "
          f"{g / tn * 1000:14.0f} {g / tf * 1000:14.0f}")

# ── 7. CUDA only: the three backends ─────────────────────────────────────
if DEVICE == "cuda":
    from torch.nn.attention import SDPBackend, sdpa_kernel
    print("\n== CUDA backends of scaled_dot_product_attention ==")
    for name, be in [("flash", SDPBackend.FLASH_ATTENTION),
                     ("mem-efficient", SDPBackend.EFFICIENT_ATTENTION),
                     ("math", SDPBackend.MATH)]:
        for T in args.lengths:
            with sdpa_kernel(be):
                try:
                    q, k, v = make(T, "cuda", DTYPE)
                    ms = median_ms(fused, q, k, v)
                    mem = peak_bytes(fused, T)
                    print(f"  {name:14s} T={T:6d}: {ms:8.2f} ms, peak "
                          f"{mib(mem):9.2f} MiB")
                except (torch.OutOfMemoryError, RuntimeError) as e:
                    print(f"  {name:14s} T={T:6d}: failed "
                          f"({str(e)[:40]})")
