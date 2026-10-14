import random
from solution import *

def drift(clip, seed=3, epochs=10, lr=1.0, eps=0.2):
    """Reuse ONE batch of 8 for `epochs` steps; report the largest |ratio - 1| among its samples after each epoch."""
    rng = random.Random(seed)
    old = [0.0] * CH8_BANDIT.k
    probs = softmax(old)
    acts = [sample_action(probs, rng) for _ in range(8)]
    rews = [CH8_BANDIT.pull(a, rng) for a in acts]
    mean = sum(rews) / 8
    std = (sum((r - mean) ** 2 for r in rews) / 8) ** 0.5
    advs = [(r - mean) / (std + 1e-8) for r in rews]
    z, out = list(old), []
    for _ in range(epochs):
        g = ppo_gradient(z, old, acts, advs, eps if clip else float("inf"))
        z = [zi + lr * gi for zi, gi in zip(z, g)]
        p = softmax(z)
        out.append(max(abs(p[a] / probs[a] - 1) for a in acts))
    return out

for clip in (False, True):
    print(("clipped  " if clip else "unclipped"), " ".join(f"{x:5.2f}" for x in drift(clip)))
print("epoch    ", " ".join(f"{i + 1:5d}" for i in range(10)))
