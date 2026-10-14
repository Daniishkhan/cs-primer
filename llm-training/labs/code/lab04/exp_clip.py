"""The clip at work: one group, many gradient steps on the SAME samples, and the ratio of the sampled answers."""
import random
from solution import *

task = make_task()
qi = 3
rng = random.Random(4)
zold = task.ref[qi][:]
probs = softmax(zold)
actions = [sample_index(probs, rng) for _ in range(8)]
rs = [reward(task.questions[qi].candidates[a], task.questions[qi].answer) for a in actions]
advs = group_advantages(rs)
print(f"question {task.questions[qi].text}: group rewards {[int(r) for r in rs]}, advantages {[round(a, 2) for a in advs]}")
for eps, label in ((0.2, "eps = 0.2"), (100.0, "no clip (eps = 100)")):
    z = zold[:]
    print(f"\n{label}   lr 1.0, beta 0")
    print(f"{'step':>5s} {'max rho (A>0)':>14s} {'min rho (A<0)':>14s} {'clipped samples':>16s} {'P(correct)':>11s}")
    for step in range(9):
        rhos = [ratio(z, zold, a) for a in actions]
        up = max((r for r, A in zip(rhos, advs) if A > 0), default=float("nan"))
        down = min((r for r, A in zip(rhos, advs) if A < 0), default=float("nan"))
        clipped = sum(1 for r, A in zip(rhos, advs) if (A > 0 and r > 1 + eps) or (A < 0 and r < 1 - eps))
        pc = sum(p * r for p, r in zip(softmax(z), rewards_of(task.questions[qi])))
        print(f"{step:5d} {up:14.3f} {down:14.3f} {clipped:16d} {pc:11.3f}")
        _, dz = grpo_loss_and_grad(z, zold, task.ref[qi], actions, advs, eps, 0.0)
        z = [v - 1.0 * g for v, g in zip(z, dz)]
