"""The verifier on the surface forms a policy actually produces."""
from solution import *

task = make_task()
q = task.questions[2]
print(f"question {q.text} (true answer {q.answer}); candidates and their rewards:")
for c in q.candidates:
    print(f"  {c!r:14s} -> {reward(c, q.answer)}")
print()
for text in ["560", "560.0", " 560\n", "0560", "5.6e2", "1120/2", "560 or 561", "about 560", "", "559.9999999"]:
    print(f"  {text!r:16s} parse_number = {parse_number(text)!s:>8s}   reward {reward(text, 560)}")
print()
counts = [sum(rewards_of(qq)) for qq in task.questions]
print("correct candidates per question:", [int(c) for c in counts], f"-> {int(sum(counts))} of {task.n_questions * task.k} candidates are correct")
print("reference probability of a correct answer per question:")
print("  " + " ".join(f"{sum(p * r for p, r in zip(softmax(z), rewards_of(qq))):.3f}" for qq, z in zip(task.questions, task.ref)))
print(f"mean {expected_reward(task, task.ref):.3f}; greedy accuracy {greedy_accuracy(task, task.ref):.2f}")
