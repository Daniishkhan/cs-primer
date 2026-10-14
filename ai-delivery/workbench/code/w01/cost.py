"""Predict a serverless endpoint's cold start and its cost per thousand
requests, in GPU-seconds. Every default is an ASSUMPTION: replace them
with what handler.py and client.py measure for you.

    python cost.py
    python cost.py --boot 8 --disk-gbps 0.3 --exec 1.2

Needs: nothing but Python."""
import argparse

# ── 1. Settings (assumptions, not measurements) ──────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--boot", type=float, default=4.0)      # s: container start
ap.add_argument("--imports", type=float, default=6.0)   # s: import torch...
ap.add_argument("--weights", type=int, default=3_087_467_144)  # bytes
ap.add_argument("--disk-gbps", type=float, default=1.0)  # GB/s weights read
ap.add_argument("--warm", type=float, default=2.0)      # s: CUDA, 1st pass
ap.add_argument("--exec", type=float, default=0.8)      # s: one request
ap.add_argument("--idle", type=float, default=5.0)      # s: idle timeout
args, _ = ap.parse_known_args()        # notebooks pass their own flags

# ── 2. Cold start = sum of the steps before the first job can run ────────
load = args.weights / (args.disk_gbps * 1e9)
start = args.boot + args.imports + load + args.warm
print("cold start, seconds")
for name, s in [("container boot", args.boot), ("import libraries",
                args.imports), (f"load {args.weights / 1e9:.2f} GB of "
                f"weights at {args.disk_gbps:g} GB/s", load),
                ("CUDA set-up and first pass", args.warm)]:
    print(f"  {name:<42}{s:>6.1f}")
print(f"  {'total (what the first caller waits)':<42}{start:>6.1f}")
billed = start - args.boot     # RunPod's docs: image pull is not billed
print(f"  {'of which billed (all but the boot)':<42}{billed:>6.1f}")

# ── 3. GPU-seconds per 1,000 requests ────────────────────────────────────
# Billed: start-up (not the boot) + execution + the idle timeout that
# follows the last request.
# f = share of requests that find no warm worker (and so pay start-up + idle).
print("\nGPU-seconds per 1,000 requests = 1000 x exec + 1000 x f x "
      "(billed + idle)")
print(f"{'f (cold share)':>15} {'GPU-s':>9} {'per request':>12}")
for f in (1.0, 0.5, 0.1, 0.02):
    total = 1000 * args.exec + 1000 * f * (billed + args.idle)
    print(f"{f:>15.2f} {total:>9,.0f} {total / 1000:>11.1f}s")

# ── 4. Against one always-on worker (a whole day is 86,400 GPU-s) ────────
print("\nrequests per day at which an always-on worker costs less:")
for f in (1.0, 0.1):
    per = args.exec + f * (billed + args.idle)
    print(f"  f = {f:.1f}: 86,400 / {per:.1f} = {86400 / per:,.0f}")
