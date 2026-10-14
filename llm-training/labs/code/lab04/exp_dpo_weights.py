"""DPO's self-limiting weight sigmoid(-m): watch it fall as a pair gets ranked correctly."""
import random
from solution import *

task = make_task()
pairs = make_pairs(task, 400, random.Random(0))
beta = 0.5
print(f"{len(pairs)} pairs from the reference policy, beta = {beta}")
print(f"{'step':>5s} {'loss':>7s} {'mean margin':>12s} {'pairs ranked right':>19s} {'mean weight sigmoid(-m)':>24s}")
z = copy_logits(task.ref)
for step in range(301):
    if step in (0, 10, 30, 100, 300):
        ms = [dpo_margin(z[q], task.ref[q], w, l, beta) for q, w, l in pairs]
        print(f"{step:5d} {dpo_loss(z, task.ref, pairs, beta):7.3f} {sum(ms) / len(ms):12.3f} "
              f"{sum(m > 0 for m in ms) / len(ms):19.2f} {sum(sigmoid(-m) for m in ms) / len(ms):24.3f}")
    g = dpo_grads(z, task.ref, pairs, beta)
    z = [[v - 5.0 * d for v, d in zip(zq, gq)] for zq, gq in zip(z, g)]
