"""Milestone 6 experiment: the size of the search split against the optimism of the winner."""
from solution import make_world, compare_methods, mean_table, optimism

SEEDS = range(6)
print("evolved (per-layer) vs the best single lambda, mean of 6 worlds; 300 held-out examples per task")
print(f"{'search/task':>12} {'evolved search':>15} {'evolved held':>13} {'optimism':>9} {'task-arith held':>16}")
for n in (10, 20, 50, 100, 200):
    tables = [compare_methods(make_world(s, n_search=n), seed=s) for s in SEEDS]
    mt = mean_table(tables)
    gap = sum(optimism(t, "evolved") for t in tables) / len(tables)
    print(f"{n:12d} {mt['evolved'][0]:15.3f} {mt['evolved'][1]:13.3f} {gap:+9.3f} {mt['task arithmetic'][1]:16.3f}")
