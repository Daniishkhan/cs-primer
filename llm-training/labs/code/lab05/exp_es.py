"""Milestone 4 experiment: watch the strategy converge, and what sigma and decay do."""
import random
from solution import evolve

target = [1.0, -1.0, 0.5, 2.0]
sphere = lambda x: -sum((a - b) ** 2 for a, b in zip(x, target))
print("best fitness (0 is perfect) after generation g, mean of 20 seeds")
print(f"{'sigma':>6} {'decay':>6} " + " ".join(f"{'g=' + str(g):>8}" for g in (0, 5, 10, 20, 40)))
for sigma, decay in ((0.1, 1.0), (0.5, 1.0), (0.5, 0.92), (2.0, 0.92), (0.5, 0.5)):
    acc = [0.0] * 5
    for seed in range(20):
        h = evolve(sphere, [0.0] * 4, random.Random(seed), generations=40, sigma=sigma, decay=decay).history
        for j, g in enumerate((0, 5, 10, 20, 40)):
            acc[j] += h[g] / 20
    print(f"{sigma:6.1f} {decay:6.2f} " + " ".join(f"{v:8.3f}" for v in acc))
