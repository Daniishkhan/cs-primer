"""Training curves: LoRA (r = 2) against full fine-tuning, on the noisy training set and on clean held-out task-B data."""
from solution import *

w = World()
A, B, la = train_lora(w.W0, w.train_b, 2, 16.0, 0.02, 200)
Wf, lf = train_full(w.W0, w.train_b, 0.005, 200)
print(f"{'step':>5s} {'LoRA train':>11s} {'full train':>11s}")
for k in (0, 10, 25, 50, 100, 199):
    print(f"{k:5d} {la[k]:11.4f} {lf[k]:11.4f}")
print(f"final clean test B:  LoRA r=2 {evaluate(merge(w.W0, A, B, 16.0), w.test_b):.4f}   full {evaluate(Wf, w.test_b):.4f}")
print(f"floor if you knew W_B exactly: train loss would still be the label noise, {0.4 ** 2:.2f}")
