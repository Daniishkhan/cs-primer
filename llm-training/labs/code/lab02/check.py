"""Self-check for Lab 2: Policy Gradients & PPO.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 3     # milestone 4, replaying ONLY the random cases of seed 3

Everything is seeded: the bandits, the gridworld rollouts and every random test input. There is no
network and no clock, so every run gives identical numbers. The whole check takes a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


def vnear(u, v, tol=1e-9):
    return len(u) == len(v) and all(near(a, b, tol) for a, b in zip(u, v))


ENV = mod.GridWorld()


class FakeRng:
    """random() returns the queued numbers in order and counts the calls."""

    def __init__(self, values):
        self.values, self.calls = list(values), 0

    def random(self):
        self.calls += 1
        return self.values.pop(0)


def mean_std(xs):
    m = sum(xs) / len(xs)
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


# =============================================================================
# Milestone 1: the softmax policy
# =============================================================================
def m1():
    assert vnear(mod.softmax([0, 0, 0, 0]), [0.25] * 4), "equal logits give a uniform distribution"
    assert vnear(mod.softmax([1, 2, 3]), [0.09003057, 0.24472847, 0.66524096], 1e-7), f"softmax([1, 2, 3]) should be [0.0900, 0.2447, 0.6652]; got {mod.softmax([1, 2, 3])}"
    big = mod.softmax([1000.0, 1001.0])
    assert vnear(big, [1 / (1 + math.e), math.e / (1 + math.e)], 1e-9), f"softmax([1000, 1001]) overflowed or lost precision; subtract the maximum first. Got {big}"
    assert vnear(mod.log_softmax([1000.0, 0.0]), [0.0, -1000.0], 1e-9), f"log_softmax([1000, 0]) should be [0, -1000] (no overflow, no log(0)); got {mod.log_softmax([1000.0, 0.0])}"
    z = [0.3, -1.2, 2.0, 0.0]
    assert vnear([math.exp(x) for x in mod.log_softmax(z)], mod.softmax(z)), "exp(log_softmax(z)) must equal softmax(z)"

    probs = [0.2, 0.5, 0.3]
    for u, want in [(0.0, 0), (0.19, 0), (0.2, 1), (0.69, 1), (0.71, 2), (0.999999, 2)]:
        got = mod.sample_action(probs, FakeRng([u]))
        assert got == want, f"with u = {u} and probabilities {probs} the inverse-CDF sample is {want} (first index whose running total exceeds u); got {got}"
    rng = FakeRng([0.5, 0.5])
    mod.sample_action(probs, rng)
    assert rng.calls == 1, f"sample_action must call rng.random() exactly once; it called it {rng.calls} times"
    assert mod.sample_action([0.5, 0.4999999], FakeRng([0.99999999])) == 1, "if rounding leaves u above the total, return the last index"
    r, counts = random.Random(1), [0, 0, 0]
    for _ in range(60000):
        counts[mod.sample_action(probs, r)] += 1
    assert all(abs(c / 60000 - p) < 0.01 for c, p in zip(counts, probs)), f"60,000 draws from {probs} came out as {[round(c / 60000, 3) for c in counts]}"

    assert vnear(mod.grad_log_prob([0, 0, 0, 0], 2), [-0.25, -0.25, 0.75, -0.25]), f"grad log pi(2) at uniform logits is onehot(2) - 0.25; got {mod.grad_log_prob([0, 0, 0, 0], 2)}"
    for seed in seeds(range(1, 6)):
        rng = random.Random(seed)
        z = [rng.uniform(-2, 2) for _ in range(5)]
        a = rng.randrange(5)
        g = mod.grad_log_prob(z, a)
        assert near(sum(g), 0.0, 1e-12), f"seed {seed}: the entries of grad log pi always sum to 0 (probabilities sum to 1); got {sum(g)}"
        for k in range(5):
            h = 1e-6
            zp, zm = list(z), list(z)
            zp[k] += h
            zm[k] -= h
            fd = (mod.log_softmax(zp)[a] - mod.log_softmax(zm)[a]) / (2 * h)
            assert near(g[k], fd, 1e-6), f"seed {seed}: d log pi({a}) / d z[{k}] by finite differences is {fd:.6f}; your grad_log_prob gives {g[k]:.6f}"
    return "stable softmax, inverse-CDF sampling with one random draw, and onehot(a) - pi agreeing with finite differences"


# =============================================================================
# Milestone 2: REINFORCE with a baseline on a bandit
# =============================================================================
def batch_gradient_estimates(bandit, logits, baseline, batch, n, seed):
    """The best-arm entry of n independent REINFORCE gradient estimates, using YOUR functions."""
    rng = random.Random(seed)
    probs = mod.softmax(logits)
    out = []
    for _ in range(n):
        acts = [mod.sample_action(probs, rng) for _ in range(batch)]
        rews = [bandit.pull(a, rng) for a in acts]
        out.append(mod.policy_gradient(logits, acts, mod.advantages(rews, baseline))[bandit.k - 1])
    return out


def m2():
    assert vnear(mod.advantages([1, 0, 0.5], "none"), [1, 0, 0.5]), "baseline 'none': advantages are the rewards"
    assert vnear(mod.advantages([1, 0, 0.5], "mean"), [0.5, -0.5, 0.0]), f"'mean' subtracts the batch mean 0.5; got {mod.advantages([1, 0, 0.5], 'mean')}"
    assert vnear(mod.advantages([1, 0, 0.5], "loo"), [0.75, -0.75, 0.0]), (
        f"'loo' subtracts the mean of the OTHER rewards: [1 - 0.25, 0 - 0.75, 0.5 - 0.5] = [0.75, -0.75, 0]; got {mod.advantages([1, 0, 0.5], 'loo')}")
    for bad, kw in [([1.0], "loo"), ([1, 2], "median")]:
        try:
            mod.advantages(bad, kw)
        except ValueError:
            pass
        else:
            raise AssertionError(f"advantages({bad}, {kw!r}) should raise ValueError")

    g = mod.policy_gradient([0, 0, 0, 0], [3, 0], [1.0, -1.0])
    assert vnear(g, [-0.5, 0.0, 0.0, 0.5]), f"two samples, A = +1 on arm 3 and -1 on arm 0, at uniform logits: the mean of A*(onehot - 0.25) is [-0.5, 0, 0, 0.5]; got {g}"
    z = [math.log(4), math.log(2), 0.0, 0.0]                      # pi = [0.5, 0.25, 0.125, 0.125]
    acts = [0] * 4 + [1] * 2 + [2] + [3]                         # 8 samples in exactly those proportions
    g = mod.policy_gradient(z, acts, [mod.CH7_BANDIT.means[a] for a in acts])
    assert vnear(g, mod.true_gradient(z, mod.CH7_BANDIT.means), 1e-12), (
        f"with samples in exactly the proportions of pi, the estimate IS the true gradient {mod.true_gradient(z, mod.CH7_BANDIT.means)}; got {g}")

    shifted = mod.Bandit([m + 10 for m in mod.CH7_BANDIT.means], 0.3)
    truth = mod.true_gradient([0.0] * 4, mod.CH7_BANDIT.means)[3]        # 0.075, the same whatever the shift
    stats = {}
    for name in ("none", "mean", "loo"):
        est = batch_gradient_estimates(shifted, [0.0] * 4, name, 16, 3000, 3)
        m_, s_ = mean_std(est)
        stats[name] = (m_, s_, sum(e > 0 for e in est) / len(est))
    assert stats["loo"][1] < stats["none"][1] / 10, (
        f"rewards shifted by +10 and batch 16: the spread of the gradient estimate should be about 30 times smaller with a baseline "
        f"(chapter 7). none {stats['none'][1]:.3f}, loo {stats['loo'][1]:.3f}")
    assert near(stats["loo"][0], truth, 0.01) and stats["loo"][2] > 0.95, (
        f"leave-one-out should stay unbiased (mean {truth:.3f}) and point the right way 95% of the time; got mean {stats['loo'][0]:.3f}, sign right {stats['loo'][2]:.2f}")
    b2 = mod.CH7_BANDIT
    est_mean = mean_std(batch_gradient_estimates(b2, [0.0] * 4, "mean", 2, 12000, 4))[0]
    est_loo = mean_std(batch_gradient_estimates(b2, [0.0] * 4, "loo", 2, 12000, 4))[0]
    assert near(est_loo, truth, 0.012), f"with batches of 2, leave-one-out must still average to the true gradient {truth:.3f}; got {est_loo:.3f}"
    assert near(est_mean, truth / 2, 0.012), (
        f"the batch-mean baseline includes the sample's own reward and shrinks the gradient by (B - 1)/B = 1/2 at B = 2: expected about {truth / 2:.3f}; got {est_mean:.3f}")

    wins = {}
    for name in ("none", "loo"):
        ok = 0
        for s in seeds(range(30)):
            z = mod.train_bandit(shifted, steps=300, batch=8, lr=0.5, baseline=name, seed=s)
            ok += mod.softmax(z)[3] > 0.9
        wins[name] = ok
    n_seeds = len(seeds(range(30)))
    assert wins["loo"] >= 0.9 * n_seeds, f"train_bandit with a leave-one-out baseline should find the best arm (p > 0.9) in at least 90% of seeds even with rewards shifted by +10; it did in {wins['loo']}/{n_seeds}"
    if ONLY_SEED is None:
        assert wins["none"] <= wins["loo"] - 5, f"without a baseline the +10 shift should hurt noticeably (none {wins['none']}/{n_seeds}, loo {wins['loo']}/{n_seeds}); is `baseline` being ignored?"
    return (f"hand values, then 3,000 batches of 16 at reward shift +10: gradient spread {stats['none'][1]:.2f} (no baseline), {stats['mean'][1]:.3f} (batch mean), {stats['loo'][1]:.3f} (leave-one-out);\n"
            f"batch of 2: batch-mean averages {est_mean:.3f}, leave-one-out {est_loo:.3f}, truth {truth:.3f};\n"
            f"training at shift +10 finds the best arm in {wins['loo']}/{n_seeds} seeds with leave-one-out and {wins['none']}/{n_seeds} with no baseline")


# =============================================================================
# Milestone 3: REINFORCE on a gridworld
# =============================================================================
def forced_table(env, moves):
    """A table that picks the given action in the given states with probability 1 - 1e-20."""
    t = mod.zeros_table(env)
    for s, a in moves.items():
        t[s][a] = 50.0
    return t


def m3():
    assert vnear(mod.returns_to_go([0, 0, 0, 10], 0.9), [7.29, 8.1, 9.0, 10.0]), f"returns_to_go([0,0,0,10], 0.9) should be [7.29, 8.1, 9.0, 10.0]; got {mod.returns_to_go([0, 0, 0, 10], 0.9)}"
    assert vnear(mod.returns_to_go([1, 2, 3], 1.0), [6, 5, 3]) and mod.returns_to_go([], 0.9) == [], "gamma = 1 sums the rest of the episode; no rewards, no returns"

    goal = forced_table(ENV, {0: 3, 1: 3, 2: 1, 6: 1, 10: 1, 14: 3})
    rng = FakeRng([0.5] * 40)
    states, actions, rewards = mod.run_episode(ENV, goal, rng)
    assert (states, actions) == ([0, 1, 2, 6, 10, 14], [3, 3, 1, 1, 1, 3]) and vnear(rewards, [-0.01] * 5 + [1.0]), (
        f"a policy forced right, right, down, down, down, right from the start should walk states [0,1,2,6,10,14] and end with +1; "
        f"got states {states}, actions {actions}, rewards {rewards}")
    assert rng.calls == 6, f"run_episode should draw one random number per step (6); it drew {rng.calls}"
    states, actions, rewards = mod.run_episode(ENV, forced_table(ENV, {0: 1, 4: 1, 8: 1}), random.Random(0))
    assert (states, actions) == ([0, 4, 8], [1, 1, 1]) and vnear(rewards, [-0.01, -0.01, -1.0]), f"walking down the left edge ends in the pit at state 12 with reward -1; got {states}, {actions}, {rewards}"
    short = mod.GridWorld(max_steps=5)
    states, _, rewards = mod.run_episode(short, forced_table(short, {0: 0}), random.Random(0))
    assert states == [0] * 5 and vnear(rewards, [-0.01] * 5), f"bumping into the edge forever must stop after max_steps = 5 steps; got {len(states)} steps"

    one = ([0, 1], [3, 3], [0.0, 1.0])
    zero_t, zero_v = mod.zeros_table(ENV), [0.0] * ENV.n_states
    g = mod.reinforce_grid_gradient(zero_t, [one], zero_v, 0.5)
    assert vnear(g[0], [-0.125, -0.125, -0.125, 0.375]) and vnear(g[1], [-0.25, -0.25, -0.25, 0.75]) and all(not any(r) for i, r in enumerate(g) if i > 1), (
        f"one episode, gamma 0.5: G = [0.5, 1.0], so row 0 is 0.5*(onehot(3) - 0.25) and row 1 is 1.0*(onehot(3) - 0.25); got row0 {g[0]}, row1 {g[1]}")
    v = list(zero_v)
    v[0], v[1] = 0.5, 1.0
    g = mod.reinforce_grid_gradient(zero_t, [one], v, 0.5)
    assert all(abs(x) < 1e-12 for r in g for x in r), "if the baseline equals the return, every advantage is 0 and the gradient vanishes"
    two = ([0], [0], [-1.0])
    g = mod.reinforce_grid_gradient(zero_t, [one, two], zero_v, 0.5)
    assert vnear(g[0], [-0.4375, 0.0625, 0.0625, 0.3125]) and vnear(g[1], [-0.125, -0.125, -0.125, 0.375]), (
        f"two episodes: divide by the number of EPISODES (2), not the number of steps. Expected row0 [-0.4375, 0.0625, 0.0625, 0.3125] and row1 [-0.125, -0.125, -0.125, 0.375]; got {g[0]}, {g[1]}")

    V = [0.0] * 3
    ret = mod.update_values(V, [([0, 1], [3, 3], [0.0, 1.0])], 0.5, 0.5)
    assert ret is None and vnear(V, [0.25, 0.5, 0.0]), f"update_values should change V in place to [0.25, 0.5, 0.0] (G = [0.5, 1.0], alpha 0.5); got {V}"
    V = [0.0] * 3
    mod.update_values(V, [([2, 2], [0, 0], [1.0, 1.0])], 1.0, 0.5)
    assert near(V[2], 1.0), f"a state visited twice is updated twice, in order (0 -> 1.0 -> 1.0); got V[2] = {V[2]}"

    curves = {}
    notes = []
    for s in seeds(range(3)):
        table, Vt, hist = mod.train_reinforce_grid(ENV, seed=s)
        ret, win = mod.evaluate(ENV, table, 300)
        assert len(hist) == 150, f"seed {s}: history must have one entry per iteration (150); got {len(hist)}"
        assert win >= 0.9 and ret >= 0.7, f"seed {s}: after 150 iterations the trained policy should reach the goal in at least 90% of episodes with a mean return of at least 0.7; got success {win:.2f}, return {ret:.2f}"
        early, late = sum(hist[:10]) / 10, sum(hist[-10:]) / 10
        assert late > early + 1.0, f"seed {s}: the mean return should climb by more than 1.0 (first 10 iterations {early:.2f}, last 10 {late:.2f})"
        assert Vt[14] > 0.8 and Vt[0] > 0.6, f"seed {s}: V should approach the discounted return (about 0.9 next to the goal); got V[14] = {Vt[14]:.2f}, V[0] = {Vt[0]:.2f}"
        notes.append(f"seed {s}: return {early:.2f} -> {late:.2f} in training; trained policy reaches the goal in {100 * win:.0f}% of episodes, V[start] = {Vt[0]:.2f}")
    return ("hand values, forced-path episodes, then REINFORCE with a value baseline on the 4 x 4 grid:\n" + "\n".join(notes))


# =============================================================================
# Milestone 4: PPO's clipped objective
# =============================================================================
def m4():
    assert near(mod.ratio(math.log(0.3), math.log(0.2)), 1.5) and near(mod.ratio(-1.7, -1.7), 1.0), "ratio = exp(logp_new - logp_old): 0.3 / 0.2 = 1.5"
    table = [  # (r, A, eps, value, clipped?)
        (1.5, 1.0, 0.2, 1.2, True), (0.5, -1.0, 0.2, -0.8, True), (0.9, 1.0, 0.2, 0.9, False), (0.9, -1.0, 0.2, -0.9, False),
        (1.5, -1.0, 0.2, -1.5, False), (0.5, 1.0, 0.2, 0.5, False), (1.5, 1.0, 0.5, 1.5, False), (1.0, 2.0, 0.2, 2.0, False),
    ]
    for r, A, eps, want, clipped in table:
        got = mod.clipped_surrogate(r, A, eps)
        assert near(got, want), (f"clipped_surrogate(r={r}, A={A}, eps={eps}) = min(r*A, clip(r, {1 - eps:.1f}, {1 + eps:.1f})*A) should be {want}; got {got}. "
                                 f"(When A is negative and r is above 1 + eps the min picks the UNCLIPPED term.)")
        assert mod.is_clipped(r, A, eps) is clipped, f"is_clipped(r={r}, A={A}, eps={eps}) should be {clipped}: a sample passes gradient only while the unclipped term is the smaller one"
    assert not mod.is_clipped(1.0 + 0.2, 1.0, 0.2), "a sample exactly on the boundary still passes gradient"

    z0 = [0.4, -0.3, 0.1, 0.0]
    acts, advs = [0, 2, 2, 3, 1], [1.0, -0.5, 2.0, 0.3, -1.2]
    assert vnear(mod.ppo_gradient(z0, z0, acts, advs, 0.2), mod.policy_gradient(z0, acts, advs), 1e-12), \
        "when the policy equals the old policy every ratio is 1, nothing is clipped, and the PPO gradient is exactly the REINFORCE gradient"
    old = [0.0, 0.0]
    z = [math.log(3), 0.0]                                       # pi(0) = 0.75 against 0.5: ratio 1.5
    assert vnear(mod.ppo_gradient(z, old, [0], [1.0], 0.2), [0.0, 0.0]), "A = +1 and ratio 1.5 is clipped: the gradient must be exactly zero"
    assert vnear(mod.ppo_gradient(z, old, [0], [-1.0], 0.2), [-0.375, 0.375]), (
        f"A = -1 and ratio 1.5 is NOT clipped (a bad action that became more likely must still be pushed down): A * r * (onehot - pi) = -1.5 * [0.25, -0.25]; got {mod.ppo_gradient(z, old, [0], [-1.0], 0.2)}")
    assert vnear(mod.ppo_gradient(z, old, [0, 0], [-1.0, -1.0], 0.2), [-0.375, 0.375]), "the gradient is the MEAN over samples: two identical samples give the same answer as one"

    checked = 0
    for seed in seeds(range(1, 7)):
        rng = random.Random(seed)
        K, n = 4, 7
        old = [rng.uniform(-1, 1) for _ in range(K)]
        z = [o + rng.gauss(0, 0.6) for o in old]
        acts = [rng.randrange(K) for _ in range(n)]
        advs = [rng.gauss(0, 1) for _ in range(n)]
        p, po = mod.softmax(z), mod.softmax(old)
        if any(abs(abs(p[a] / po[a] - 1) - 0.2) < 1e-3 for a in acts):
            continue                                              # too close to a kink for finite differences
        f = lambda zz: sum(mod.clipped_surrogate(mod.softmax(zz)[a] / po[a], A, 0.2) for a, A in zip(acts, advs)) / n
        g = mod.ppo_gradient(z, old, acts, advs, 0.2)
        for k in range(K):
            h = 1e-6
            zp, zm = list(z), list(z)
            zp[k] += h
            zm[k] -= h
            fd = (f(zp) - f(zm)) / (2 * h)
            assert near(g[k], fd, 1e-5), f"seed {seed}: d(mean clipped surrogate)/d z[{k}] by finite differences is {fd:.6f}; ppo_gradient gives {g[k]:.6f} (ratios {[round(p[a] / po[a], 2) for a in acts]}, advantages {[round(A, 2) for A in advs]})"
        checked += 1
    assert checked >= 1 or ONLY_SEED is not None, "no random case could be checked by finite differences"

    res = {}
    for clip in (False, True):
        er, stuck = [], 0
        for s in range(100):
            p = mod.softmax(mod.train_bandit_ppo(mod.CH8_BANDIT, clip=clip, seed=s))
            er.append(sum(pa * m for pa, m in zip(p, mod.CH8_BANDIT.means)))
            stuck += max(p) > 0.9 and p.index(max(p)) != 4
        res[clip] = (sum(er) / len(er), stuck)
    assert res[True][0] > res[False][0] + 0.04, (
        f"reusing each batch of 8 ten times, the clipped run should end clearly better than the unclipped one (chapter 8: 0.98 against 0.89 with NumPy's random numbers); "
        f"got clipped {res[True][0]:.3f}, unclipped {res[False][0]:.3f}")
    assert res[True][0] > 0.95 and res[True][1] <= 3 and res[False][1] >= 8, (
        f"expected the clipped runs to get stuck on a wrong arm in at most 3 of 100 seeds and the unclipped in at least 8; got {res[True][1]} and {res[False][1]}")
    return (f"hand values, finite-difference gradient checks on {checked} random cases, then the six-armed bandit (100 seeds, batch of 8 reused 10 times):\n"
            f"unclipped: expected reward {res[False][0]:.3f}, stuck on a wrong arm in {res[False][1]} runs;  clipped: {res[True][0]:.3f}, stuck in {res[True][1]}")


# =============================================================================
# Milestone 5: the KL leash
# =============================================================================
def m5():
    assert near(mod.kl_k3(math.log(0.5), math.log(0.5)), 0.0), "k3 is 0 when the policy and the reference agree"
    assert near(mod.kl_k3(math.log(0.5), math.log(0.25)), -0.5 + math.log(2)), f"rho = 0.25/0.5 = 0.5 gives (0.5 - 1) - ln 0.5 = 0.1931; got {mod.kl_k3(math.log(0.5), math.log(0.25))}"
    rng = random.Random(0)
    for _ in range(200):
        a, b = math.log(rng.uniform(0.01, 0.99)), math.log(rng.uniform(0.01, 0.99))
        assert mod.kl_k3(a, b) >= -1e-12, f"k3 is never negative (log rho <= rho - 1); got {mod.kl_k3(a, b)} for logp={a:.3f}, logp_ref={b:.3f}"
    pi, ref = [0.5, 0.3, 0.15, 0.05], [0.25] * 4
    exact = mod.kl_divergence(pi, ref)
    rng = random.Random(7)
    xs = [mod.kl_k3(math.log(pi[a]), math.log(ref[a])) for a in (mod.sample_action(pi, rng) for _ in range(40000))]
    assert near(sum(xs) / len(xs), exact, 0.01), f"the mean of k3 over 40,000 samples from pi should approach the exact KL {exact:.4f}; got {sum(xs) / len(xs):.4f}"

    got = mod.shaped_rewards([0.0, 0.0, 1.0], [math.log(0.5), math.log(0.4), math.log(0.5)], [math.log(0.25), math.log(0.4), math.log(0.5)], 0.1)
    assert vnear(got, [-0.1 * math.log(2), 0.0, 1.0]), f"shaped = r - beta * (log pi - log ref): expected [-0.0693, 0, 1.0]; got {got}"
    assert vnear(mod.shaped_rewards([1.0, 2.0], [-1.0, -2.0], [-3.0, -0.5], 0.0), [1.0, 2.0]), "beta = 0 leaves the rewards alone"

    ref = mod.reference_table(ENV)
    t0, V0 = mod.train_ppo_grid(ENV, ref, 0.5, iterations=0)
    assert t0 == ref and t0 is not ref and t0[0] is not ref[0] and V0 == [0.0] * ENV.n_states, "with no iterations you get a COPY of the reference table (not the same list) and V = zeros"
    before = [row[:] for row in ref]
    mod.train_ppo_grid(ENV, ref, 0.5, iterations=3)
    assert ref == before, "training must not modify the reference table"

    rows, betas = {}, (0.0, 0.3, 1.0, 3.0)
    for beta in betas:
        kls, rets, wins = [], [], []
        for s in seeds((0, 1)):
            table, _ = mod.train_ppo_grid(ENV, ref, beta, seed=s)
            r_, w_ = mod.evaluate(ENV, table, 300)
            kls.append(mod.mean_kl(ENV, table, ref))
            rets.append(r_)
            wins.append(w_)
        rows[beta] = (sum(kls) / len(kls), sum(rets) / len(rets), sum(wins) / len(wins))
    assert rows[0.0][2] >= 0.9 and rows[0.0][1] >= 0.7, f"with beta = 0 PPO should solve the grid: success >= 0.9 and return >= 0.7; got success {rows[0.0][2]:.2f}, return {rows[0.0][1]:.2f}"
    for lo, hi in zip(betas, betas[1:]):
        assert rows[hi][0] < rows[lo][0] / 1.5, (f"a bigger beta must keep the policy closer to the reference: mean KL should fall by at least a third from beta = {lo} to beta = {hi}; "
                                                 f"got {rows[lo][0]:.3f} then {rows[hi][0]:.3f}")
        assert rows[hi][1] < rows[lo][1], f"and the price is reward: the mean return should fall from beta = {lo} ({rows[lo][1]:.2f}) to beta = {hi} ({rows[hi][1]:.2f})"
    assert rows[3.0][0] < 0.02, f"at beta = 3 the policy should barely leave the reference (mean KL < 0.02); got {rows[3.0][0]:.3f}"
    lines = [f"  beta {b:>3}: mean KL to the reference {rows[b][0]:.3f}  return {rows[b][1]:+.2f}  success {rows[b][2]:.2f}" for b in betas]
    return "hand values, then PPO on the grid starting from the reference policy (average of 2 seeds):\n" + "\n".join(lines)


MILESTONES = [
    (1, "Milestone 1: the softmax policy", m1),
    (2, "Milestone 2: REINFORCE with a baseline on a bandit", m2),
    (3, "Milestone 3: REINFORCE on a gridworld", m3),
    (4, "Milestone 4: PPO's clipped objective", m4),
    (5, "Milestone 5: PPO with a KL penalty", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 2 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
