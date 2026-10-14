"""DPO and GRPO side by side, question by question: the probability of a correct answer."""
import random
from solution import *

class CountingRng:
    """Wraps random.Random and counts calls to random(): sample_index makes exactly one per sampled answer."""

    def __init__(self, seed):
        self._r, self.calls = random.Random(seed), 0

    def random(self):
        self.calls += 1
        return self._r.random()

    def randrange(self, n):
        return self._r.randrange(n)


task = make_task()
rng = CountingRng(0)
pairs = make_pairs(task, 400, rng)
zd3, _ = train_dpo(task, pairs, 0.1, 5.0, 300)
zd10, _ = train_dpo(task, pairs, 0.1, 5.0, 1000)
zg, _ = train_grpo(task, 60)


def p_correct(z):
    return [sum(p * r for p, r in zip(softmax(zq), rewards_of(q))) for q, zq in zip(task.questions, z)]


cols = [("ref", task.ref), ("DPO 300", zd3), ("DPO 1000", zd10), ("GRPO 60", zg)]
print(f"{'q':>2s} {'question':>10s} " + " ".join(f"{name:>9s}" for name, _ in cols))
table = [p_correct(z) for _, z in cols]
for qi, q in enumerate(task.questions):
    print(f"{qi:2d} {q.text:>10s} " + " ".join(f"{col[qi]:9.3f}" for col in table))
print(f"{'':>13s}" + " ".join("-" * 9 for _ in cols))
print(f"{'mean':>13s}" + " ".join(f"{sum(c) / len(c):9.3f}" for c in table))
print(f"{'KL to ref':>13s}" + " ".join(f"{mean_kl(task, z, task.ref):9.2f}" for _, z in cols))
print(f"\nsamples drawn from the reference to build the {len(pairs)} pairs: {rng.calls:,}; GRPO samples: {60 * 6 * 8:,}")
