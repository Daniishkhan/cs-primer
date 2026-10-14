"""Demo for Lab 4: train the tiny GPT, show the loss curve and sample names at three temperatures.

    python3 demo.py             # uses your starter.py
    python3 demo.py solution    # uses the reference solution
"""
import importlib
import math
import random
import sys
import time

sys.dont_write_bytecode = True
m = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "starter")

cfg = m.CFG
t0 = time.time()
params, losses = m.train(cfg, m.TRAIN, 600, seed=0)
print(f"{len(m.flat_params(params)):,} weights, {len(m.TRAIN)} training names, {len(m.HELD_OUT)} held out, "
      f"trained in {time.time() - t0:.0f} s")
print("loss, mean of each block of 100 steps (one name per step, so the numbers are noisy):")
print("  " + "  ".join(f"{sum(losses[i:i + 100]) / 100:.2f}" for i in range(0, 600, 100)))
print(f"held-out loss {m.average_loss(cfg, params, m.HELD_OUT):.3f}   chance {math.log(m.V):.3f}")

# a baseline with no neural network: P(next letter | previous letter) from counts, add-one smoothing
counts = {}
for name in m.TRAIN:
    ids = m.encode(name)
    for a, b in zip(ids, ids[1:]):
        counts.setdefault(a, [1.0] * m.V)[b] += 1
nll = n = 0
for name in m.HELD_OUT:
    ids = m.encode(name)
    for a, b in zip(ids, ids[1:]):
        row = counts.get(a, [1.0] * m.V)
        nll += -math.log(row[b] / sum(row))
        n += 1
print(f"bigram count baseline on the same held-out names: {nll / n:.3f}")

for temp in (0.5, 1.0, 1.5):
    rng = random.Random(42)
    print(f"\ntemperature {temp}:")
    print("  " + ", ".join(m.sample_name(cfg, params, rng, temp) or "(empty)" for _ in range(14)))
