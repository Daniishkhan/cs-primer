"""DPO's implicit reward after training, next to the verifier's reward (chapter 12: the policy is its own reward model)."""
import random
from solution import *

task = make_task()
pairs = make_pairs(task, 400, random.Random(0))
beta = 0.1
z, _ = train_dpo(task, pairs, beta, 5.0, 300)
for qi in (1, 5):
    q = task.questions[qi]
    imp = implicit_rewards(z[qi], task.ref[qi], beta)
    print(f"question {q.text} = {q.answer}   ({sum(1 for p in pairs if p[0] == qi)} training pairs)")
    print(f"  {'candidate':>12s} {'verifier':>9s} {'pi_ref':>7s} {'pi_dpo':>7s} {'implicit reward':>16s}")
    for k, c in enumerate(q.candidates):
        print(f"  {c:>12s} {reward(c, q.answer):9.0f} {softmax(task.ref[qi])[k]:7.3f} {softmax(z[qi])[k]:7.3f} {imp[k]:16.3f}")
