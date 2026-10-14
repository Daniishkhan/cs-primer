"""The setting: one world, scored per task. Rows are models, columns are the three tasks' held-out sets."""
from solution import make_world, task_scores, mean_score, n_params, average_models

w = make_world(0)
print(f"world 0: {n_params(w.base)} weights, search split {len(w.search[0][0])} examples per task, held-out {len(w.hold[0][0])} per task")
print(f"{'model':<12} {'task 0':>7} {'task 1':>7} {'task 2':>7} {'mean':>7}")
for name, m in [("base", w.base), ("specialist 0", w.finetunes[0]), ("specialist 1", w.finetunes[1]),
                ("specialist 2", w.finetunes[2]), ("average", average_models(w.finetunes))]:
    s = task_scores(m, w.hold)
    print(f"{name:<12} {s[0]:7.3f} {s[1]:7.3f} {s[2]:7.3f} {mean_score(m, w.hold):7.3f}")
