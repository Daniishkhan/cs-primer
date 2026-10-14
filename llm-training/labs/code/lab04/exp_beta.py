"""The leash: beta in DPO and in GRPO, reward gained against drift from the reference."""
import random
from solution import *

task = make_task()
pairs = make_pairs(task, 400, random.Random(0))
print(f"reference: expected reward {expected_reward(task, task.ref):.3f}\n")
print(f"{'method':>14s} {'beta':>6s} {'expected reward':>16s} {'greedy acc':>11s} {'KL to ref':>10s}")
for beta in (0.05, 0.1, 0.5, 1.0):
    z, _ = train_dpo(task, pairs, beta, 5.0, 300)
    print(f"{'DPO':>14s} {beta:6.2f} {expected_reward(task, z):16.3f} {greedy_accuracy(task, z):11.2f} {mean_kl(task, z, task.ref):10.3f}")
for beta in (0.0, 0.04, 0.2, 1.0):
    z, _ = train_grpo(task, 60, beta=beta)
    print(f"{'GRPO':>14s} {beta:6.2f} {expected_reward(task, z):16.3f} {greedy_accuracy(task, z):11.2f} {mean_kl(task, z, task.ref):10.3f}")
