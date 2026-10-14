from solution import *

def run(eps, clip=True, seeds=100, **kw):
    er, stuck = 0.0, 0
    for s in range(seeds):
        p = softmax(train_bandit_ppo(CH8_BANDIT, clip=clip, eps=eps, seed=s, **kw))
        er += sum(pa * m for pa, m in zip(p, CH8_BANDIT.means)) / seeds
        stuck += max(p) > 0.9 and p.index(max(p)) != 4
    return er, stuck

print(f"{'setting':28s} {'E[reward]':>9s} {'stuck':>6s}")
for label, eps, clip in [("no clip", 0.2, False), ("eps = 0.02", 0.02, True), ("eps = 0.1", 0.1, True),
                         ("eps = 0.2", 0.2, True), ("eps = 0.5", 0.5, True)]:
    er, st = run(eps, clip)
    print(f"{label:28s} {er:9.3f} {st:5d}%")
er, st = run(0.2, False, batch=64)
print(f"{'no clip, batch of 64':28s} {er:9.3f} {st:5d}%")
