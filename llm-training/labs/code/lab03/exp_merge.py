"""Merging: same outputs, no extra layers, and the update keeps its low rank."""
import random
from solution import *

w = World()
A, B, _ = train_lora(w.W0, w.train_b, 2, 16.0, 0.02, 200)
W = merge(w.W0, A, B, 16.0)
rng = random.Random(0)
gap = 0.0
for _ in range(200):
    x = [rng.gauss(0, 1) for _ in range(D)]
    a, b = lora_forward(w.W0, A, B, x, 16.0), matvec(W, x)
    gap = max(gap, max(abs(p - q) for p, q in zip(a, b)))
Wf, _ = train_full(w.W0, w.train_b, 0.005, 200)
print(f"largest output gap, adapter path vs merged matrix, over 200 inputs: {gap:.1e}")
print(f"rank of W0                 {numeric_rank(w.W0, 1e-9)}")
print(f"rank of merged W           {numeric_rank(W, 1e-9)}")
print(f"rank of W - W0 (LoRA r=2)  {numeric_rank(mat_add(W, w.W0, -1.0), 1e-9)}")
print(f"rank of W - W0 (full)      {numeric_rank(mat_add(Wf, w.W0, -1.0), 1e-9)}")
back = unmerge(W, A, B, 16.0)
print(f"largest entry error after unmerge(merge(W0)): {max(abs(a - b) for ra, rb in zip(back, w.W0) for a, b in zip(ra, rb)):.1e}")
print(f"adapter file: {count_lora(D, D, 2)} numbers; merged layer: {count_full(D, D)} numbers (the merged model is as big as the base)")
