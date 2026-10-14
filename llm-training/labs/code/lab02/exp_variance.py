import random
from solution import *

def estimates(bandit, baseline, batch=16, n=4000, seed=3):
    rng, z = random.Random(seed), [0.0] * 4
    probs = softmax(z)
    out = []
    for _ in range(n):
        acts = [sample_action(probs, rng) for _ in range(batch)]
        rews = [bandit.pull(a, rng) for a in acts]
        out.append(policy_gradient(z, acts, advantages(rews, baseline))[3])
    m = sum(out) / n
    sd = (sum((x - m) ** 2 for x in out) / n) ** 0.5
    return m, sd, sum(x > 0 for x in out) / n

print(f"true gradient of the best arm's logit: {true_gradient([0.0] * 4, CH7_BANDIT.means)[3]:.3f}")
for shift in (0.0, 10.0):
    bandit = Bandit([m + shift for m in CH7_BANDIT.means], CH7_BANDIT.sigma)
    print(f"\nreward shift +{shift:g}, batch of 16, 4,000 estimates")
    print(f"{'baseline':10s} {'mean':>7s} {'std':>7s} {'sign right':>11s}")
    for name in ("none", "mean", "loo"):
        m, sd, ok = estimates(bandit, name)
        print(f"{name:10s} {m:7.3f} {sd:7.3f} {100 * ok:10.1f}%")
