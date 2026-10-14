"""Self-check for Lab 4: DPO & GRPO on a Toy Policy.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 5       # only milestone 5
    python3 check.py solution 2 3     # milestone 2, replaying ONLY the random cases of seed 3

Everything is seeded: the task, the sampled answers, the preference pairs and every random test
input. There is no network and no clock, so every run gives identical numbers. The whole check
takes a few seconds. Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import itertools
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
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def vec_near(u, v, tol=1e-9):
    return len(u) == len(v) and all(near(a, b, tol) for a, b in zip(u, v))


class FixedRng:
    """A stand-in for random.Random whose random() returns a scripted sequence and counts the calls."""

    def __init__(self, values):
        self.values, self.calls = list(values), 0

    def random(self):
        v = self.values[self.calls % len(self.values)]
        self.calls += 1
        return v


_task = None


def task():
    global _task
    if _task is None:
        _task = mod.make_task()
    return _task


def num_grad(f, vec, k, eps=1e-6):
    old = vec[k]
    vec[k] = old + eps
    hi = f()
    vec[k] = old - eps
    lo = f()
    vec[k] = old
    return (hi - lo) / (2 * eps)


# =============================================================================
# Milestone 1: the verifier, sampling, KL
# =============================================================================
def m1():
    from fractions import Fraction
    for text, want in [("391", 391), ("391.0", 391), (" 391\n", 391), ("0391", 391), ("3.91e2", 391), ("782/2", 391), ("-5", -5), ("0.1", Fraction(1, 10))]:
        got = mod.parse_number(text)
        assert got is not None and got == want, f"parse_number({text!r}) should be the number {want}, got {got!r}"
    assert mod.parse_number("0.1") == Fraction(1, 10) and mod.parse_number("0.1") != 0.1, \
        "0.1 must parse to the EXACT value one tenth (use fractions.Fraction), not the float 0.1"
    for text in ["", "   ", "about 391", "391 or 392", "39l", "twelve", "nan", "inf", "1/0"]:
        assert mod.parse_number(text) is None, f"parse_number({text!r}) is not a number: expected None, got {mod.parse_number(text)!r}"

    for text, ans, want in [("391", 391, 1.0), ("391.0", 391, 1.0), (" 0391 ", 391, 1.0), ("390", 391, 0.0), ("391 or 392", 391, 0.0),
                            ("", 391, 0.0), ("391.0000001", 391, 0.0), ("3.91e2", 391, 1.0), ("-391", 391, 0.0), ("about 391", 391, 0.0)]:
        got = mod.reward(text, ans)
        assert got == want, f"reward({text!r}, {ans}) should be {want}, got {got!r} (an exact numeric match: 1.0 or 0.0, nothing in between)"

    t = task()
    counts = [sum(mod.rewards_of(q)) for q in t.questions]
    assert counts == [2, 1] * 6, f"each question should have 1 or 2 correct candidate strings, alternating 2, 1, ...; the verifier gives {counts}"

    probs = [0.2, 0.5, 0.3]
    for u, want in [(0.0, 0), (0.19, 0), (0.2, 1), (0.69, 1), (0.7, 2), (0.9999, 2)]:
        rng = FixedRng([u])
        got = mod.sample_index(probs, rng)
        assert got == want and rng.calls == 1, f"u = {u} with probs {probs} should pick index {want} using exactly one rng.random() call; got {got} after {rng.calls} calls"
    assert mod.sample_index([0.0, 1.0, 0.0], FixedRng([0.0])) == 1, "an index with probability 0 must never be drawn, even for u = 0.0"
    assert mod.sample_index([0.5, 0.5], FixedRng([0.9999999999999999])) == 1
    rng = random.Random(7)
    probs = [0.1, 0.0, 0.6, 0.3]
    draws = [mod.sample_index(probs, rng) for _ in range(20000)]
    for k, p in enumerate(probs):
        f = draws.count(k) / len(draws)
        assert abs(f - p) < 0.015, f"index {k} should be drawn about {p:.2f} of the time, got {f:.3f}"

    assert near(mod.kl_divergence([0.5, 0.5], [0.25, 0.75]), 0.5 * math.log(2) + 0.5 * math.log(2 / 3)), "KL([.5, .5] || [.25, .75]) = 0.14384"
    assert mod.kl_divergence([0.3, 0.7], [0.3, 0.7]) == 0.0 and near(mod.kl_divergence([1.0, 0.0], [0.5, 0.5]), math.log(2)), \
        "KL of a distribution with itself is 0; a term with p = 0 contributes 0"
    assert abs(mod.kl_divergence([0.5, 0.5], [0.25, 0.75]) - mod.kl_divergence([0.25, 0.75], [0.5, 0.5])) > 0.01, "KL is not symmetric"
    r = random.Random(1)
    for _ in range(20):
        p, q = mod.softmax([r.gauss(0, 1) for _ in range(5)]), mod.softmax([r.gauss(0, 1) for _ in range(5)])
        assert mod.kl_divergence(p, q) >= -1e-12, "KL is never negative"
    return (f"verifier on many surface forms of one number (exact Fractions), inverse-CDF sampling with one rng.random() call, KL;\n"
            f"the reference policy answers correctly {mod.expected_reward(t, t.ref):.3f} of the time (greedy accuracy {mod.greedy_accuracy(t, t.ref):.2f})")


# =============================================================================
# Milestone 2: the DPO loss and its gradient
# =============================================================================
def m2():
    ref = [0.0, 0.0]
    z = [math.log(3.0), 0.0]                       # pi = (0.75, 0.25) against a uniform reference
    r = mod.implicit_rewards(z, ref, 2.0)
    assert vec_near(r, [2 * math.log(1.5), 2 * math.log(0.5)]), f"beta = 2: implicit rewards are 2 ln(0.75 / 0.5) and 2 ln(0.25 / 0.5); got {r}"
    assert near(mod.dpo_margin(z, ref, 0, 1, 2.0), 2 * math.log(3.0)), "the margin of (w = 0, l = 1) is 2 ln 3 = 2.197"
    assert near(mod.dpo_margin(z, ref, 1, 0, 2.0), -2 * math.log(3.0)), "swapping chosen and rejected flips the sign of the margin"
    assert near(mod.dpo_loss([z], [ref], [(0, 0, 1)], 2.0), math.log(1 + 1 / 9)), "loss = -log sigmoid(2.197) = ln(1 + 1/9) = 0.10536"
    zero = mod.implicit_rewards([0.3, -1.0, 2.0], [0.3, -1.0, 2.0], 0.7)
    assert all(abs(v) < 1e-12 for v in zero), "when the policy equals the reference every implicit reward is 0"
    shifted = mod.implicit_rewards([v + 5.0 for v in z], ref, 2.0)
    assert vec_near(shifted, r), "adding the same constant to every logit does not change the policy, so it must not change the implicit rewards"

    g = mod.dpo_grads([[0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0]], [(0, 0, 2)], 0.5)
    assert vec_near(g[0], [-0.25, 0.0, 0.25]), f"at the reference the margin is 0 and sigmoid(-0) = 0.5: grad = beta * 0.5 * (-e_w + e_l) = [-0.25, 0, 0.25]; got {g[0]}"
    g2 = mod.dpo_grads([[0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0]], [(0, 0, 2), (0, 0, 2)], 0.5)
    assert vec_near(g2[0], [-0.25, 0.0, 0.25]), "the loss is a MEAN over pairs: two identical pairs give the same gradient as one"

    note = ""
    for s in seeds((1, 2, 3)):
        rng = random.Random(s)
        K, Q = 5, 4
        zz = [[rng.gauss(0, 1) for _ in range(K)] for _ in range(Q)]
        rr = [[rng.gauss(0, 1) for _ in range(K)] for _ in range(Q)]
        pairs = []
        for _ in range(7):
            q = rng.randrange(Q)
            w, l = rng.sample(range(K), 2)
            pairs.append((q, w, l))
        beta = rng.choice([0.1, 0.5, 2.0])
        grads = mod.dpo_grads(zz, rr, pairs, beta)
        assert len(grads) == Q and all(len(row) == K for row in grads), "dpo_grads must have the shape of z"
        worst = 0.0
        for q in range(Q):
            assert abs(sum(grads[q])) < 1e-12, f"seed {s}: the gradient of a softmax policy sums to 0 across the logits of a question"
            for k in range(K):
                num = num_grad(lambda: mod.dpo_loss(zz, rr, pairs, beta), zz[q], k)
                worst = max(worst, abs(num - grads[q][k]))
                assert abs(num - grads[q][k]) < 1e-6, (f"seed {s}: d loss / d z[{q}][{k}] = {grads[q][k]:.6g} but a finite difference gives {num:.6g}. "
                                                       "Remember the weight is beta * sigmoid(-margin) and the loss is averaged over pairs")
        note = f"finite-difference check of every logit gradient (worst error {worst:.1e})"
    # a big margin barely moves, a wrong one moves almost fully; no overflow
    big = [[40.0, -40.0]]
    wrong = [[-800.0, 800.0]]
    gb = mod.dpo_grads(big, [[0.0, 0.0]], [(0, 0, 1)], 1.0)[0][0]
    gw = mod.dpo_grads(wrong, [[0.0, 0.0]], [(0, 0, 1)], 1.0)[0][0]
    assert abs(gb) < 1e-30 and near(gw, -1.0), f"a pair ranked right by a wide margin has weight ~0 (got {gb}); one ranked wrong has weight ~1, gradient -beta (got {gw})"
    lw = mod.dpo_loss(wrong, [[0.0, 0.0]], [(0, 0, 1)], 1.0)
    assert math.isfinite(lw) and near(lw, 1600.0, 1e-6), f"a margin of -1600 gives a loss of about 1600, not inf: got {lw}"
    return note + "; self-limiting weight: a pair already ranked right by a wide margin stops pulling"


# =============================================================================
# Milestone 3: preference pairs from a verifier, and DPO training
# =============================================================================
def oracle_pairs(t, n, rng, max_attempts=None):
    pairs, probs = [], [mod.softmax(z) for z in t.ref]
    for _ in range(max_attempts or 50 * n):
        if len(pairs) == n:
            break
        q = rng.randrange(t.n_questions)
        a = mod.sample_index(probs[q], rng)
        b = mod.sample_index(probs[q], rng)
        ra, rb = mod.reward(t.questions[q].candidates[a], t.questions[q].answer), mod.reward(t.questions[q].candidates[b], t.questions[q].answer)
        if ra == rb:
            continue
        pairs.append((q, a, b) if ra > rb else (q, b, a))
    return pairs


def m3():
    t = task()
    for s in seeds((3, 4)):
        got = mod.make_pairs(t, 60, random.Random(s))
        assert len(got) == 60, f"seed {s}: make_pairs should return 60 pairs, got {len(got)}"
        for q, w, l in got:
            assert reward_of(t, q, w) == 1.0 and reward_of(t, q, l) == 0.0, f"seed {s}: pair {(q, w, l)}: the chosen answer must be verified correct and the rejected one wrong"
        want = oracle_pairs(t, 60, random.Random(s))
        assert got == want, (f"seed {s}: pairs differ from the specified procedure (q = rng.randrange(...), then two sample_index draws a, b from softmax(ref[q]); "
                             f"keep only pairs whose rewards differ). First difference at index {next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), '?')}")
    assert len(mod.make_pairs(t, 100, random.Random(1), max_attempts=5)) <= 5, "max_attempts caps the number of draws"
    assert mod.make_pairs(t, 0, random.Random(1)) == [], "n = 0 gives no pairs"

    ref_copy = [row[:] for row in t.ref]
    pairs = mod.make_pairs(t, 400, random.Random(0))
    z, losses = mod.train_dpo(t, pairs, 0.1, 5.0, 300)
    assert t.ref == ref_copy, "train_dpo must not modify task.ref"
    assert len(losses) == 300 and near(losses[0], math.log(2), 1e-9), f"the loss before the first step is ln 2 = 0.693 (policy = reference); got {losses[0]:.4f}"
    z2, l2 = mod.train_dpo(t, pairs[:100], 0.5, 1.0, 200)
    assert all(b <= a + 1e-12 for a, b in zip(l2, l2[1:])), "gradient descent with a small learning rate on this convex loss must never go uphill"
    assert l2[-1] < 0.7 * l2[0], f"loss should fall clearly: {l2[0]:.3f} -> {l2[-1]:.3f}"

    only = [(q, w, l) for q, w, l in pairs if q in (0, 1)]
    z3, _ = mod.train_dpo(t, only, 0.5, 2.0, 50)
    assert all(z3[q] == t.ref[q] for q in range(2, t.n_questions)), "a question with no preference pair must keep its reference logits exactly"
    assert z3[0] != t.ref[0], "a question with pairs must move"

    R0, A0, K0 = mod.expected_reward(t, t.ref), mod.greedy_accuracy(t, t.ref), mod.mean_kl(t, t.ref, t.ref)
    R, A, K = mod.expected_reward(t, z), mod.greedy_accuracy(t, z), mod.mean_kl(t, z, t.ref)
    assert K0 == 0.0 and K > 0.3, f"training must move the policy away from the reference (KL {K:.3f})"
    assert R > R0 + 0.35 and A >= 0.67, f"DPO on 400 verified pairs should lift the expected reward from {R0:.3f} to above {R0 + 0.35:.2f} and greedy accuracy to 0.67+; got {R:.3f} and {A:.2f}"
    for qi in (0, 1, 2, 3):
        imp = mod.implicit_rewards(z[qi], t.ref[qi], 0.1)
        rs = mod.rewards_of(t.questions[qi])
        right = [v for v, rw in zip(imp, rs) if rw == 1.0]
        wrong = [v for v, rw in zip(imp, rs) if rw == 0.0]
        assert min(right) > max(wrong), f"question {qi}: after DPO every correct answer's implicit reward should exceed every wrong one's; got {right} against {wrong}"
    zl, _ = mod.train_dpo(t, pairs, 0.1, 5.0, 300)
    zh, _ = mod.train_dpo(t, pairs, 0.1, 5.0, 30)
    assert mod.mean_kl(t, zh, t.ref) < mod.mean_kl(t, zl, t.ref), "fewer steps, less drift"
    return (f"{len(pairs)} verified pairs from the reference; DPO (beta 0.1, 300 steps): expected reward {R0:.3f} -> {R:.3f}, "
            f"greedy accuracy {A0:.2f} -> {A:.2f}, KL to the reference {K:.2f};\n"
            f"questions 10 and 11 (reference right 1.5% and 0.8% of the time) got only {sum(1 for p in pairs if p[0] == 10)} and {sum(1 for p in pairs if p[0] == 11)} pairs")


def reward_of(t, q, k):
    return mod.reward(t.questions[q].candidates[k], t.questions[q].answer)


# =============================================================================
# Milestone 4: group-relative advantages
# =============================================================================
def m4():
    a = mod.group_advantages([1, 0, 0, 0, 0, 0, 0, 0])
    assert near(a[0], 2.6458, 1e-3) and all(near(v, -0.37796, 1e-3) for v in a[1:]), \
        f"one correct answer in eight: advantage (1 - 1/8) / sqrt(1/8 * 7/8) = +2.646 and -0.378 for the rest; got {[round(v, 3) for v in a]}"
    assert near(sum(abs(v) for v in a), 5.2915, 1e-3), "the group's total pull sum|A| is 5.29 for 1 of 8"
    assert [round(v, 3) for v in mod.group_advantages([1.0, 1.0, 0.0, 0.0])] == [1.0, 1.0, -1.0, -1.0], "two of four: +1 and -1 (population std 0.5)"
    assert vec_near(mod.group_advantages([1, 1, 0, 0], eps=0.0), [1, 1, -1, -1], 1e-12), "with eps = 0 the standardised advantages are exactly +-1 here"
    m = mod.group_advantages([1, 0, 0, 0, 0, 0, 0, 0], "mean")
    assert vec_near(m, [0.875] + [-0.125] * 7), f"mean-only advantages for 1 of 8: +0.875, -0.125; got {m}"
    lo = mod.group_advantages([1, 0, 0, 0, 0, 0, 0, 0], "rloo")
    assert vec_near(lo, [1.0] + [-1 / 7] * 7), f"leave-one-out: the correct answer is compared with the mean of the other seven (0): +1.0, and each wrong one with 1/7: -0.143; got {lo}"
    assert vec_near(mod.group_advantages([1, 0], "rloo"), [1, -1]), "G = 2: each answer is compared with the other one"
    for mode in ("std", "mean", "rloo"):
        z = mod.group_advantages([0.0] * 8, mode)
        assert all(v == 0.0 for v in z), f"mode {mode!r}: when every reward ties the advantages must all be exactly 0 (no NaN, no division by zero), got {z}"
        z = mod.group_advantages([1.0] * 5, mode)
        assert all(v == 0.0 for v in z), f"mode {mode!r}: all-correct group should also give all zeros, got {z}"
    assert mod.zero_signal([0.0] * 8) and mod.zero_signal([1.0, 1.0, 1.0]) and mod.zero_signal([0.5, 0.5])
    assert not mod.zero_signal([1.0, 0.0]) and not mod.zero_signal([0.0, 0.0, 0.1])

    for s in seeds((1, 2, 3)):
        rng = random.Random(s)
        G = rng.randint(3, 12)
        rs = [rng.choice([0.0, 1.0, 2.0]) for _ in range(G)]
        if len(set(rs)) == 1:
            rs[0] += 1.0
        std, mean, rl = (mod.group_advantages(rs, m) for m in ("std", "mean", "rloo"))
        assert abs(sum(std)) < 1e-9 and abs(sum(mean)) < 1e-9, f"seed {s}: advantages centred on the group mean sum to 0"
        assert vec_near(rl, [G / (G - 1) * v for v in mean], 1e-9), f"seed {s}: leave-one-out advantage = G / (G - 1) times the mean-only advantage"
        scaled = mod.group_advantages([3.0 * r + 7.0 for r in rs], "std", eps=0.0)
        base = mod.group_advantages(rs, "std", eps=0.0)
        assert vec_near(scaled, base, 1e-9), f"seed {s}: standardised advantages do not change when rewards are rescaled and shifted"

    # the (G-1)/G bias of the group-mean baseline, by exact enumeration over every possible group
    z = [0.4, -0.2, 0.1, 0.0]
    p = mod.softmax(z)
    rewards = [1.0, 0.0, 0.0, 0.0]
    true0 = p[0] * (1.0 - p[0])
    out = []
    for G in (2, 3, 4):
        for mode, want in (("mean", (G - 1) / G), ("rloo", 1.0)):
            g0 = 0.0
            for combo in itertools.product(range(4), repeat=G):
                prob = math.prod(p[x] for x in combo)
                adv = mod.group_advantages([rewards[x] for x in combo], mode)
                g0 += prob * sum(A * ((1.0 if x == 0 else 0.0) - p[0]) for x, A in zip(combo, adv)) / G
            assert near(g0 / true0, want, 1e-9), (f"G = {G}, mode {mode!r}: the expected gradient on the correct logit should be {want:.3f} of the true one "
                                                  f"({'(G-1)/G, the group mean contains the sample itself' if mode == 'mean' else 'exactly 1: the baseline excludes the sample'}); got {g0 / true0:.4f}")
        out.append(f"G={G}: mean baseline {(G - 1) / G:.3f}, leave-one-out 1.000")
    return ("1 of 8 correct: std +2.65 / -0.38, mean-only +0.875, leave-one-out +1.0; ties give exact zeros;\n"
            "exact expectation over all groups of the gradient, as a fraction of the true gradient:\n    " + "\n    ".join(out))


# =============================================================================
# Milestone 5: the GRPO objective for one group
# =============================================================================
def m5():
    zold = [0.0, 0.0, 0.0]
    z = [math.log(2.0), 0.0, 0.0]                  # pi(0) = 0.5 against 1/3 for the old policy: rho = 1.5
    assert near(mod.ratio(z, zold, 0), 1.5) and near(mod.ratio(z, zold, 1), 0.75) and near(mod.ratio(zold, zold, 2), 1.0), "ratio = pi_theta(a) / pi_old(a): 1.5, 0.75, 1.0"
    assert near(mod.ratio([v + 3.0 for v in z], zold, 0), 1.5), "ratio is unchanged when a constant is added to every logit"
    for rho, adv, want in [(1.5, 2.0, 2.4), (1.5, -2.0, -3.0), (0.5, 2.0, 1.0), (0.5, -2.0, -1.6), (1.0, 3.0, 3.0), (1.1, 2.0, 2.2), (0.9, -2.0, -1.8), (1.2, 1.0, 1.2), (3.0, 0.0, 0.0)]:
        got = mod.clipped_objective(rho, adv, 0.2)
        assert near(got, want), (f"clipped_objective(rho={rho}, A={adv}, eps=0.2) should be {want}: min(rho A, clip(rho, 0.8, 1.2) A); got {got}. "
                                 "The min makes it pessimistic: A > 0 stops paying above 1 + eps, A < 0 stops paying below 1 - eps")
    uni = [0.0, 0.0, 0.0, 0.0]
    assert mod.k3([0.0] * 4, [0.0] * 4, 1) == 0.0, "k3 is 0 when the policy equals the reference"
    got = mod.k3([math.log(3.0), 0.0, 0.0, 0.0], uni, 0)       # r = 0.25 / 0.5 = 0.5
    assert near(got, 0.5 + math.log(2) - 1), f"pi = 0.5, pi_ref = 0.25: r = 0.5, k3 = 0.5 - ln 0.5 - 1 = 0.19315; got {got}"
    got = mod.k3(uni, [math.log(3.0), 0.0, 0.0, 0.0], 0)       # r = 0.5 / 0.25 = 2
    assert near(got, 2 - math.log(2) - 1), f"pi = 0.25, pi_ref = 0.5: r = 2, k3 = 2 - ln 2 - 1 = 0.30685; got {got}"
    rng = random.Random(0)
    for _ in range(30):
        a, b = [rng.gauss(0, 1) for _ in range(5)], [rng.gauss(0, 1) for _ in range(5)]
        assert mod.k3(a, b, rng.randrange(5)) >= -1e-12, "k3 = r - log r - 1 is never negative"

    loss, dz = mod.grpo_loss_and_grad([0.0] * 3, [0.0] * 3, [0.0] * 3, [0, 1], [1.0, -1.0], 0.2, 0.0)
    assert near(loss, 0.0, 1e-12), f"at pi = pi_old, rho = 1 and the loss is -(1/G) sum A = 0; got {loss}"
    assert vec_near(dz, [-0.5, 0.5, 0.0]), f"two samples, A = +1 and -1, uniform policy: dz = -(1/2) [(e0 - p) - (e1 - p)] = [-0.5, 0.5, 0]; got {dz}"
    _, dz = mod.grpo_loss_and_grad(z, zold, zold, [0], [1.0], 0.2, 0.0)
    assert all(abs(v) < 1e-15 for v in dz), f"A > 0 and rho = 1.5 > 1.2: the clip is active, the gradient is exactly 0; got {dz}"
    _, dz = mod.grpo_loss_and_grad(z, zold, zold, [0], [-1.0], 0.2, 0.0)
    p = mod.softmax(z)
    assert vec_near(dz, [1.5 * ((1.0 if k == 0 else 0.0) - p[k]) for k in range(3)]), \
        f"A < 0 and rho = 1.5 > 1.2: the clip is NOT active (the min picks the unclipped term), dz = rho * (e_a - p); got {dz}"
    _, dz = mod.grpo_loss_and_grad(z, zold, zold, [1], [-1.0], 0.2, 0.0)
    assert all(abs(v) < 1e-15 for v in dz), "A < 0 and rho = 0.75 < 0.8: the clip is active, gradient exactly 0"
    ref = [0.3, -0.2, 0.1]
    loss, dz = mod.grpo_loss_and_grad(ref, ref, ref, [0, 2], [0.0, 0.0], 0.2, 1.0)
    assert near(loss, 0.0) and all(abs(v) < 1e-15 for v in dz), "no advantage and no drift from the reference: nothing to do"
    zz = [1.0, -0.5, 0.2]
    _, dz = mod.grpo_loss_and_grad(zz, zz, [0.0, 0.0, 0.0], [0], [0.0], 0.2, 1.0)
    pz, pr = mod.softmax(zz), mod.softmax([0.0, 0.0, 0.0])
    want = [(1 - pr[0] / pz[0]) * ((1.0 if k == 0 else 0.0) - pz[k]) for k in range(3)]
    assert vec_near(dz, want), f"KL term only: dz = beta * (1 - pi_ref(a) / pi_theta(a)) * (e_a - p); expected {want}, got {dz}"

    note = ""
    for s in seeds((1, 2, 3)):
        rng = random.Random(s)
        K = 5
        zq = [rng.gauss(0, 1) for _ in range(K)]
        zold = [v + rng.gauss(0, 0.5) for v in zq]
        zref = [rng.gauss(0, 1) for _ in range(K)]
        G = 8
        acts = [rng.randrange(K) for _ in range(G)]
        advs = mod.group_advantages([float(rng.random() < 0.4) for _ in range(G)]) if s != 2 else [rng.gauss(0, 1.5) for _ in range(G)]
        beta, eps = 0.3, 0.2
        rhos = [mod.ratio(zq, zold, a) for a in acts]
        clipped = sum(1 for r, A in zip(rhos, advs) if (A > 0 and r > 1 + eps) or (A < 0 and r < 1 - eps))
        loss, dz = mod.grpo_loss_and_grad(zq, zold, zref, acts, advs, eps, beta)
        want = sum(-mod.clipped_objective(r, A, eps) + beta * mod.k3(zq, zref, a) for r, A, a in zip(rhos, advs, acts)) / G
        assert near(loss, want, 1e-9), f"seed {s}: loss should be -(1/G) sum clipped + beta (1/G) sum k3 = {want:.6f}; got {loss:.6f}"
        f = lambda: mod.grpo_loss_and_grad(zq, zold, zref, acts, advs, eps, beta)[0]
        worst = 0.0
        for k in range(K):
            num = num_grad(f, zq, k)
            worst = max(worst, abs(num - dz[k]))
            assert abs(num - dz[k]) < 1e-6, (f"seed {s}: d loss / d z[{k}] = {dz[k]:.6g} but a finite difference gives {num:.6g} "
                                             f"({clipped} of {G} samples are clipped in this case)")
        assert abs(sum(dz)) < 1e-12
        note = f"finite-difference check with {clipped} of {G} samples clipped (worst error {worst:.1e})"
    return note + "; exact zero gradient when the clip is active"


# =============================================================================
# Milestone 6: the GRPO training loop
# =============================================================================
def m6():
    t = task()
    ref_copy = [row[:] for row in t.ref]
    z, log = mod.train_grpo(t, 60)
    assert t.ref == ref_copy, "train_grpo must not modify task.ref"
    assert len(log) == 60 and all(set(entry) >= {"reward", "zero_groups"} for entry in log), "log needs one dict per step with 'reward' and 'zero_groups'"
    z_again, log_again = mod.train_grpo(t, 60)
    assert z == z_again and log == log_again, "same seed, same run"
    assert log[-1]["reward"] > log[0]["reward"] and near(log[-1]["reward"], mod.expected_reward(t, z)), "log['reward'] is the expected reward AFTER each step"
    R0, R = mod.expected_reward(t, t.ref), mod.expected_reward(t, z)
    K = mod.mean_kl(t, z, t.ref)
    assert R > 0.70, f"60 GRPO steps (6 questions of 12 per step, groups of 8) should lift the expected reward from {R0:.3f} to above 0.70; got {R:.3f}"
    assert mod.greedy_accuracy(t, z) >= 0.75, f"most questions should now be answered correctly by the greedy answer; got {mod.greedy_accuracy(t, z):.2f}"
    zeros = sum(e["zero_groups"] for e in log)
    assert 100 < zeros < 300, f"of 360 groups, between 100 and 300 should have had zero signal (questions already solved, or hopeless); counted {zeros}"
    early, late = sum(e["zero_groups"] for e in log[:10]), sum(e["zero_groups"] for e in log[-10:])
    assert late > early + 5, f"as the policy improves, more groups become all-correct and silent: first 10 steps {early}, last 10 steps {late}"
    for q in (10, 11):
        p = sum(pk * rw for pk, rw in zip(mod.softmax(z[q]), mod.rewards_of(t.questions[q])))
        assert p < 0.2, f"question {q}: the reference is right 1.5% or less of the time, so groups of 8 are almost always all wrong and there is almost no signal; p = {p:.3f} suggests something other than the verifier is moving it"

    z0, _ = mod.train_grpo(t, 60, beta=0.0)
    z1, _ = mod.train_grpo(t, 60, beta=1.0)
    K0, K1 = mod.mean_kl(t, z0, t.ref), mod.mean_kl(t, z1, t.ref)
    R1 = mod.expected_reward(t, z1)
    assert K1 < 0.6 * K0, f"beta = 1.0 should hold the policy much closer to the reference than beta = 0 (KL {K1:.2f} against {K0:.2f})"
    assert R1 < mod.expected_reward(t, z0) - 0.1 and R1 > R0, "a strong leash trades reward for staying close, but still improves on the reference"
    z_one, _ = mod.train_grpo(t, 20, inner=1)
    z_four, _ = mod.train_grpo(t, 20, inner=4)
    assert mod.expected_reward(t, z_four) > mod.expected_reward(t, z_one), "reusing each batch four times (the clip keeps it safe) learns faster per batch than using it once"
    zm, _ = mod.train_grpo(t, 60, mode="mean")
    zr, _ = mod.train_grpo(t, 60, mode="rloo")
    assert mod.expected_reward(t, zm) > 0.6 and mod.expected_reward(t, zr) > 0.6, "the mean-only and leave-one-out variants also learn"

    pairs = mod.make_pairs(t, 400, random.Random(0))
    zd, _ = mod.train_dpo(t, pairs, 0.1, 5.0, 300)
    for q in (10, 11):
        p = sum(pk * rw for pk, rw in zip(mod.softmax(zd[q]), mod.rewards_of(t.questions[q])))
        assert p < 0.2, f"question {q}: DPO had almost no verified pair for this question, so it should still be unsolved; p = {p:.3f}"
    return (f"reference: expected reward {R0:.3f}, greedy accuracy {mod.greedy_accuracy(t, t.ref):.2f}\n"
            f"GRPO 60 steps:    expected reward {R:.3f}, greedy accuracy {mod.greedy_accuracy(t, z):.2f}, KL {K:.2f}, silent groups {zeros} of 360 (first 10 steps {early}, last 10 steps {late})\n"
            f"GRPO beta = 0:    expected reward {mod.expected_reward(t, z0):.3f}, KL {K0:.2f};   beta = 1.0: expected reward {R1:.3f}, KL {K1:.2f}\n"
            f"DPO 400 pairs:    expected reward {mod.expected_reward(t, zd):.3f}, greedy accuracy {mod.greedy_accuracy(t, zd):.2f}, KL {mod.mean_kl(t, zd, t.ref):.2f}\n"
            f"questions 10 and 11 stay unsolved by both: their reference success rates are 1.5% and 0.8%")


MILESTONES = [
    (1, "Milestone 1: the verifier, sampling and KL", m1),
    (2, "Milestone 2: the DPO loss and its gradient", m2),
    (3, "Milestone 3: preference pairs and DPO training", m3),
    (4, "Milestone 4: group-relative advantages", m4),
    (5, "Milestone 5: the GRPO clipped objective with a KL penalty", m5),
    (6, "Milestone 6: the GRPO training loop", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 4 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
