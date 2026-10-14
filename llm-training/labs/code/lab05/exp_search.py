"""Milestone 5 experiment: more knobs, more room to fit the search split."""
from solution import make_world, search_recipe, merge_coeffs, coeffs_from_vector, task_vector, mean_score, RECIPE_DIM

SEEDS = range(8)
print("evolved recipes, mean of 8 worlds (20 search examples per task, 300 held-out)")
print(f"{'mode':>7} {'knobs':>6} {'search':>8} {'held-out':>9} {'optimism':>9}")
for mode in ("global", "task", "layer"):
    s_sum = h_sum = 0.0
    for s in SEEDS:
        w = make_world(s)
        tvs = [task_vector(ft, w.base) for ft in w.finetunes]
        vec, res = search_recipe(w, mode, seed=s)
        s_sum += res.fitness / len(SEEDS)
        h_sum += mean_score(merge_coeffs(w.base, tvs, coeffs_from_vector(vec, mode)), w.hold) / len(SEEDS)
    print(f"{mode:>7} {RECIPE_DIM[mode]:6d} {s_sum:8.3f} {h_sum:9.3f} {s_sum - h_sum:+9.3f}")
w = make_world(0)
vec, res = search_recipe(w, "layer", seed=0)
print("\nworld 0, per-layer recipe found (rows: tasks, columns: layer 0, layer 1)")
for t in range(3):
    print(f"  task {t}: {vec[2 * t]:+.2f} {vec[2 * t + 1]:+.2f}")
print("best search score by generation:", " ".join(f"{h:.2f}" for h in res.history))
