"""Milestone 3 experiment: the six-weight example of chapter 16, then a sweep of the kept fraction."""
from solution import (make_world, task_vector, merge_ties, mean_score, ties_merge, LAMBDA_GRID)

A = [[0.8, 0.05, 0.5, -0.6, 0.02, -0.1]]
B = [[0.6, -0.1, -0.7, -0.5, 0.05, 0.02]]
print("A            ", A[0])
print("B            ", B[0])
print("plain mean   ", [round((a + b) / 2, 3) for a, b in zip(A[0], B[0])])
print("TIES keep 50%", [round(v, 3) for v in ties_merge([A, B], 0.5)[0]])

SEEDS = range(6)
print("\nheld-out mean accuracy of TIES merges (lambda picked on the search split), mean of 6 worlds")
print(f"{'keep':>6} {'lambda chosen':>14} {'held-out':>9}")
for keep in (0.1, 0.2, 0.3, 0.5, 0.7, 1.0):
    lam_sum = hold = 0.0
    for s in SEEDS:
        w = make_world(s)
        tvs = [task_vector(ft, w.base) for ft in w.finetunes]
        lam = max(LAMBDA_GRID, key=lambda l: mean_score(merge_ties(w.base, tvs, keep, l), w.search))
        lam_sum += lam / len(SEEDS)
        hold += mean_score(merge_ties(w.base, tvs, keep, lam), w.hold) / len(SEEDS)
    print(f"{keep:6.1f} {lam_sum:14.2f} {hold:9.3f}")
