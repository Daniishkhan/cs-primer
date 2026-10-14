"""Where GRPO has no signal: groups whose answers all tie, and questions the reference never gets right."""
from solution import *

task = make_task()
G = 8
z, log = train_grpo(task, 60, group_size=G)
print(f"{sum(x['zero_groups'] for x in log)} of {60 * 6} groups had zero signal over 60 steps (6 questions x 60 steps)")
print(f"first 10 steps: {sum(x['zero_groups'] for x in log[:10])} of 60;   last 10 steps: {sum(x['zero_groups'] for x in log[-10:])} of 60")
print()
print(f"{'q':>2s} {'question':>10s} {'p_ref':>6s} {'p_GRPO':>7s} {'P(all wrong) at ref':>20s} {'P(all right) at end':>20s}")
for qi, (q, zq, zr) in enumerate(zip(task.questions, z, task.ref)):
    pr = sum(p * r for p, r in zip(softmax(zr), rewards_of(q)))
    pg = sum(p * r for p, r in zip(softmax(zq), rewards_of(q)))
    print(f"{qi:2d} {q.text:>10s} {pr:6.3f} {pg:7.3f} {(1 - pr) ** G:20.3f} {pg ** G:20.3f}")
