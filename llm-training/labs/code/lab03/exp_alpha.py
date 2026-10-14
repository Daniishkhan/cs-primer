"""Alpha is a learning-rate-like knob: the scale s = alpha / r multiplies a step the optimiser has already sized."""
from solution import *

w = World()
print("clean task-B loss of a rank-4 adapter (lr 0.02) after k Adam steps; the layer starts at 0.200")
print(f"{'alpha':>6s} {'s':>6s} " + " ".join(f"{'k=' + str(k):>7s}" for k in (5, 20, 80, 200)))
for alpha in (1.0, 4.0, 16.0, 64.0, 256.0):
    cells = []
    for k in (5, 20, 80, 200):
        A, B, _ = train_lora(w.W0, w.train_b, 4, alpha, 0.02, k)
        cells.append(evaluate(merge(w.W0, A, B, alpha), w.test_b))
    print(f"{alpha:6.0f} {alpha / 4:6.2f} " + " ".join(f"{c:7.3f}" for c in cells))
print()
print("the same alpha / r = 4 at two ranks: same learning speed at the start")
for r in (2, 8):
    A, B, _ = train_lora(w.W0, w.train_b, r, 4.0 * r, 0.02, 20)
    print(f"  r={r}: loss after 20 steps {evaluate(merge(w.W0, A, B, 4.0 * r), w.test_b):.3f}")
