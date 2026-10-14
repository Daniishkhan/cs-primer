"""Is the group mean a valid baseline? Exact expectation over every possible group (chapter 14's (G-1)/G factor)."""
import itertools
from solution import *

z = [0.4, -0.2, 0.1, 0.0]
rewards = [1.0, 0.0, 0.0, 0.0]                       # answer 0 is correct
p = softmax(z)
exact = [p[a] * (rewards[a] - sum(pk * rk for pk, rk in zip(p, rewards))) for a in range(4)]   # true gradient of expected reward
print(f"true gradient on the correct answer's logit: {exact[0]:.4f}")
for G in (2, 3, 4, 5):
    row = []
    for mode in ("mean", "rloo"):
        grad = [0.0] * 4
        for combo in itertools.product(range(4), repeat=G):
            prob = 1.0
            for a in combo:
                prob *= p[a]
            rs = [rewards[a] for a in combo]
            adv = group_advantages(rs, mode)
            for a, A in zip(combo, adv):
                for k in range(4):
                    grad[k] += prob * A * ((1.0 if k == a else 0.0) - p[k]) / G
        row.append(grad[0] / exact[0])
    print(f"G = {G}: expected gradient / true gradient: mean baseline {row[0]:.3f} (theory {(G - 1) / G:.3f}), leave-one-out {row[1]:.3f}")
