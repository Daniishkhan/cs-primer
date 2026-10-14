"""Milestone 1 experiment: walk the straight line between two models and score every point.

Two fine-tunes of ONE base (same ancestor) against two runs from different random starts.
Change the import to `starter` to run it on your own code."""
import random
from solution import accuracy, init_model, interpolate, make_means, sample, train, K

SEEDS = range(4)
ts = [0.0, 0.25, 0.5, 0.75, 1.0]
same = [0.0] * len(ts)
indep = [0.0] * len(ts)
for s in SEEDS:
    means = make_means(s)
    r = random.Random(s + 50)
    xs, ys = sample(means, list(range(K)), 240, r)
    xt, yt = sample(means, list(range(K)), 600, r)
    start = train(init_model(r), xs, ys, 40, 0.05, r)
    f1, f2 = (train(start, xs, ys, 200, 0.05, random.Random(k)) for k in (1, 2))
    i1, i2 = (train(init_model(random.Random(k)), xs, ys, 240, 0.05, random.Random(k + 2)) for k in (11, 12))
    for j, t in enumerate(ts):
        same[j] += accuracy(interpolate(f1, f2, t), xt, yt) / len(SEEDS)
        indep[j] += accuracy(interpolate(i1, i2, t), xt, yt) / len(SEEDS)
print("test accuracy along the line from model 1 (t = 0) to model 2 (t = 1), mean of 4 worlds")
print(f"{'t':>5} {'same ancestor':>14} {'different starts':>17}")
for t, a, b in zip(ts, same, indep):
    print(f"{t:5.2f} {a:14.3f} {b:17.3f}")
