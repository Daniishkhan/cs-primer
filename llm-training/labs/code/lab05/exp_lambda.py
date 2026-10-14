"""Milestone 2 experiment: one coefficient lambda for all three task vectors, scored per task."""
from solution import make_world, merge_coeffs, coeffs_from_vector, task_vector, task_scores, mean_score, LAMBDA_GRID

SEEDS = range(6)
rows = {lam: [0.0, 0.0, 0.0] for lam in [0.0] + LAMBDA_GRID + [1.5]}
for s in SEEDS:
    w = make_world(s)
    tvs = [task_vector(ft, w.base) for ft in w.finetunes]
    for lam in rows:
        sc = task_scores(merge_coeffs(w.base, tvs, coeffs_from_vector([lam], "global")), w.hold)
        for t in range(3):
            rows[lam][t] += sc[t] / len(SEEDS)
print("held-out accuracy of base + lambda * (tau_0 + tau_1 + tau_2), mean of 6 worlds")
print(f"{'lambda':>7} {'task 0':>7} {'task 1':>7} {'task 2':>7} {'mean':>7}")
for lam, v in rows.items():
    print(f"{lam:7.1f} {v[0]:7.3f} {v[1]:7.3f} {v[2]:7.3f} {sum(v) / 3:7.3f}")
