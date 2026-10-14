"""What happens in the first few steps: B moves, A waits (chapter 11's gradient derivation)."""
import random
from solution import *

w = World()
r, alpha, lr = 4, 16.0, 0.02
A, B = init_adapter(D, D, r, random.Random(0))
opt = Adam([A, B], lr)
print(f"{'step':>4s} {'loss':>8s} {'|dA|':>9s} {'|dB|':>9s} {'|A|':>7s} {'|B|':>7s}")
for step in range(6):
    loss, dA, dB = batch_loss_and_grads(w.W0, A, B, w.train_b, alpha)
    print(f"{step:4d} {loss:8.4f} {frobenius_sq(dA) ** 0.5:9.5f} {frobenius_sq(dB) ** 0.5:9.5f} "
          f"{frobenius_sq(A) ** 0.5:7.3f} {frobenius_sq(B) ** 0.5:7.4f}")
    opt.step([dA, dB])
