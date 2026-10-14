"""Self-check for Lab 5: A Statistics Toolkit for Experiments.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 5 12    # milestone 5, replaying ONLY the random cases of seed 12

Everything is deterministic. The checks come in three layers: values worked out by hand or
enumerated exactly (every way of shuffling a tiny data set, every sign pattern), properties that
must hold whatever random numbers you draw (an interval for a maximum can never pass the
sample's maximum), and statistical checks with tolerances of four or more standard errors of the
simulation, so a correct implementation passes whatever order it draws its random numbers in.
A failure prints its seed so it can be replayed. The whole check takes a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
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

Z95 = 1.959963984540054          # the 97.5th percentile of the standard normal, typed in so the oracles do not use the lab's code
Z90 = 1.6448536269514722
Z995 = 2.5758293035489004
ZP80 = 0.8416212335729143
ZP90 = 1.2815515655446004


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


def pair_near(got, want, tol=1e-9):
    try:
        return len(got) == 2 and near(got[0], want[0], tol) and near(got[1], want[1], tol)
    except TypeError:
        return False


def fp(pair):
    return "(" + ", ".join(f"{x:.6g}" for x in pair) + ")"


def mean(xs):
    return sum(xs) / len(xs)


def exact_wilson(k, n, z=Z95):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


# =============================================================================
# Milestone 1: standard errors and intervals
# =============================================================================
def m1():
    xs = [2, 4, 4, 4, 5, 5, 7, 9]
    assert near(mod.sample_variance(xs), 32 / 7), (
        f"sample_variance of {xs} should be 32/7 = 4.5714 (sum of squared deviations 32, divided by n - 1 = 7); got {mod.sample_variance(xs)}. "
        "Dividing by n gives 4.0: that is the population variance, which is biased low for a sample")
    assert near(mod.sample_variance([3.0, 3.0, 3.0]), 0.0), "constant data has variance 0"
    assert near(mod.std_error([2, 4, 6]), math.sqrt(4 / 3)), f"std_error([2, 4, 6]) should be sqrt(4/3) = 1.1547 (variance 4, n = 3); got {mod.std_error([2, 4, 6])}"
    data = [10, 12, 14, 16, 18]
    se = math.sqrt(10 / 5)
    got = mod.mean_interval(data)
    assert pair_near(got, (14 - Z95 * se, 14 + Z95 * se), 1e-6), f"mean_interval([10, 12, 14, 16, 18]) should be 14 -/+ 1.96 x 1.4142 = {fp((14 - Z95 * se, 14 + Z95 * se))}; got {fp(got)}"
    got = mod.mean_interval(data, 0.90)
    assert pair_near(got, (14 - Z90 * se, 14 + Z90 * se), 1e-6), (
        f"a 90% interval uses z = 1.645, not 1.96: expected {fp((14 - Z90 * se, 14 + Z90 * se))}; got {fp(got)}. For a general conf, z = phi_inv(0.5 + conf / 2)")

    got = mod.wald_interval(50, 100)
    assert pair_near(got, (0.5 - Z95 * 0.05, 0.5 + Z95 * 0.05), 1e-6), f"wald_interval(50, 100) should be 0.5 -/+ 1.96 x 0.05 = (0.402, 0.598); got {fp(got)}"
    got = mod.wald_interval(20, 20)
    assert pair_near(got, (1.0, 1.0)), (f"wald_interval(20, 20) should be the single point (1.0, 1.0): with p-hat = 1 the standard error is 0. "
                                        f"That collapse is the weakness of the Wald interval; got {fp(got)}. Do not clip or patch it")
    got = mod.wilson_interval(20, 20)
    assert pair_near(got, (0.8388748419, 1.0), 1e-6), f"wilson_interval(20, 20) should be (0.8389, 1.0): 20 of 20 is still compatible with a true rate of 84%; got {fp(got)}"
    got = mod.wilson_interval(50, 100)
    assert pair_near(got, exact_wilson(50, 100), 1e-9), f"wilson_interval(50, 100) should be {fp(exact_wilson(50, 100))}; got {fp(got)}"
    got = mod.wilson_interval(0, 50)
    assert abs(got[0]) < 1e-12 and 0.05 < got[1] < 0.09, f"wilson_interval(0, 50) should start at 0 and end near 0.071; got {fp(got)}"

    # whole grid: inside [0, 1], contains the point estimate, mirror symmetry, agrees with the oracle, narrower as n grows
    for n in (1, 2, 5, 30, 400):
        for k in range(n + 1):
            lo, hi = mod.wilson_interval(k, n)
            assert -1e-12 <= lo <= k / n + 1e-12 <= hi + 2e-12 and hi <= 1 + 1e-12, f"wilson_interval({k}, {n}) = {fp((lo, hi))} must lie in [0, 1] and contain p-hat = {k / n:.4g}"
            mlo, mhi = mod.wilson_interval(n - k, n)
            assert near(lo, 1 - mhi, 1e-9) and near(hi, 1 - mlo, 1e-9), f"wilson_interval({k}, {n}) and ({n - k}, {n}) should mirror each other (p and 1 - p)"
            assert pair_near((lo, hi), exact_wilson(k, n), 1e-9), f"wilson_interval({k}, {n}) should be {fp(exact_wilson(k, n))}; got {fp((lo, hi))}"
    w = [mod.wilson_interval(n // 2, n) for n in (20, 80, 320)]
    assert w[0][1] - w[0][0] > w[1][1] - w[1][0] > w[2][1] - w[2][0], "intervals should narrow as n grows (about by half for 4 times the data)"
    lo90, hi90 = mod.wilson_interval(30, 100, 0.90)
    lo95, hi95 = mod.wilson_interval(30, 100)
    assert lo95 < lo90 < hi90 < hi95, "a 90% interval must sit inside the 95% interval for the same data"
    return f"Wilson(20 of 20) = {fp(mod.wilson_interval(20, 20))}; Wald(20 of 20) = {fp(mod.wald_interval(20, 20))}; mean_interval of the five values: {fp(mod.mean_interval(data))}"


# =============================================================================
# Milestone 2: the bootstrap
# =============================================================================
def oracle_percentile(xs, q):
    xs = sorted(xs)
    pos = (len(xs) - 1) * q / 100
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def m2():
    p = mod.percentile
    for q, want in ((0, 10), (100, 40), (50, 25), (25, 17.5), (90, 37), (10, 13)):
        got = p([10, 20, 30, 40], q)
        assert near(got, want), f"percentile([10, 20, 30, 40], {q}) should be {want} (position {(3 * q / 100):.2g} of 0..3); got {got}"
    assert p([5], 50) == 5 and p([5], 100) == 5, "a one-element list has every percentile equal to that element (q = 100 has no neighbour above it)"
    for s in seeds(range(1, 7)):
        rng = random.Random(s)
        xs = sorted(rng.uniform(-5, 5) for _ in range(rng.randint(2, 40)))
        for q in (0, 2.5, 33, 50, 97.5, 100):
            assert near(p(xs, q), oracle_percentile(xs, q)), f"seed {s}: percentile of {len(xs)} sorted values at q = {q} should be {oracle_percentile(xs, q):.6g}; got {p(xs, q):.6g}"

    # bootstrap_stats: B values, resamples of size n, drawn with replacement from the data, data untouched
    data = [5, 3, 9, 1, 7]
    seen = []
    out = mod.bootstrap_stats(data, lambda r: seen.append(list(r)) or sum(r), 200, random.Random(1))
    assert len(out) == 200 and len(seen) == 200, f"bootstrap_stats must return B = 200 values and call stat once per resample; got {len(out)} values from {len(seen)} calls"
    assert all(len(r) == 5 and all(x in data for x in r) for r in seen), "each resample must have the same size as the data and contain only values from it"
    assert any(len(set(r)) < 5 for r in seen), "resamples must be drawn WITH replacement: out of 200 draws of 5 from 5 values, almost all have a repeat (96%); none did"
    assert data == [5, 3, 9, 1, 7], "bootstrap_stats must not sort, shuffle or otherwise modify its data"
    # the spread of the bootstrap means is the plug-in standard error
    base = random.Random(7)
    sample = [base.gauss(50, 10) for _ in range(50)]
    boots = mod.bootstrap_stats(sample, mean, 4000, random.Random(3))
    sd = math.sqrt(sum((b - mean(boots)) ** 2 for b in boots) / len(boots))
    plug = math.sqrt(sum((x - mean(sample)) ** 2 for x in sample) / len(sample) / len(sample))
    assert abs(mean(boots) - mean(sample)) < 0.3 * plug and 0.93 * plug < sd < 1.07 * plug, (
        f"the bootstrap means should centre on the sample mean {mean(sample):.3f} with spread close to the plug-in standard error {plug:.3f}; got centre {mean(boots):.3f}, spread {sd:.3f}")

    # bootstrap_interval
    a = mod.bootstrap_interval(sample, mean, B=1000, seed=4)
    b = mod.bootstrap_interval(sample, mean, B=1000, seed=4)
    assert a == b, "the same seed must give the same interval (create random.Random(seed) inside the function)"
    assert mod.bootstrap_interval([4.0] * 12, mean, B=50) == (4.0, 4.0), "constant data: every resample has the same mean, so the interval is a single point"
    lo, hi = mod.bootstrap_interval(sample, mean, B=4000, seed=2)
    se = math.sqrt(sum((x - mean(sample)) ** 2 for x in sample) / (len(sample) - 1) / len(sample))
    assert lo < mean(sample) < hi, f"the interval {fp((lo, hi))} should contain the sample mean {mean(sample):.3f}"
    assert abs(lo - (mean(sample) - Z95 * se)) < 0.3 * se and abs(hi - (mean(sample) + Z95 * se)) < 0.3 * se, (
        f"for a mean the bootstrap interval should be close to the formula's {fp((mean(sample) - Z95 * se, mean(sample) + Z95 * se))}; got {fp((lo, hi))}. "
        "Read the 2.5th and 97.5th percentiles of the SORTED bootstrap statistics")
    n95 = mod.bootstrap_interval(sample, mean, B=2000, conf=0.95, seed=2)
    n50 = mod.bootstrap_interval(sample, mean, B=2000, conf=0.50, seed=2)
    assert n95[0] < n50[0] < n50[1] < n95[1], f"a 50% interval {fp(n50)} must sit inside the 95% interval {fp(n95)}"
    # the bootstrap cannot see beyond the sample: for the maximum, the upper end is exactly the sample's maximum
    lo, hi = mod.bootstrap_interval(sample, max, B=1000, seed=5)
    assert hi == max(sample) and lo < hi, (
        f"a resample can never exceed the sample's maximum {max(sample):.3f}, and 63% of resamples contain it, so the upper end of the interval for the maximum is exactly it; got {fp((lo, hi))}")
    # a statistic with no formula: the median of a skewed sample
    r = random.Random(11)
    skew = [r.expovariate(1 / 100) for _ in range(80)]
    med = sorted(skew)[39] / 2 + sorted(skew)[40] / 2
    lo, hi = mod.bootstrap_interval(skew, lambda s: sorted(s)[len(s) // 2 - 1] / 2 + sorted(s)[len(s) // 2] / 2, B=2000, seed=1)
    assert lo < med < hi and 0.15 * med < hi - lo < 1.2 * med, f"median interval {fp((lo, hi))} should contain the sample median {med:.1f} and be a sensible width"

    # paired bootstrap
    a_scores = [random.Random(i).random() for i in range(30)]
    b_scores = [x + 0.1 for x in a_scores]
    got = mod.paired_bootstrap_interval(a_scores, b_scores, B=200, seed=1)
    assert pair_near(got, (0.1, 0.1), 1e-9), (
        f"if b[i] = a[i] + 0.1 for every question, the paired difference is 0.1 in every resample and the interval is the point (0.1, 0.1); got {fp(got)}. "
        "Resample ONE list of question indices and use it for both a and b")
    n = 500
    a_r = [1] * 386 + [0] * 114                                    # model A: 77.2% on 500 questions
    b_r = list(a_r)
    flipped_up = 0
    for i in range(n):                                              # B fixes 26 of A's mistakes and breaks 9 of its successes
        if a_r[i] == 0 and flipped_up < 26:
            b_r[i] = 1
            flipped_up += 1
    for i in range(9):
        b_r[i] = 0
    d = mean(b_r) - mean(a_r)
    lo, hi = mod.paired_bootstrap_interval(a_r, b_r, B=3000, seed=9)
    se_un = math.sqrt(mean(a_r) * (1 - mean(a_r)) / n + mean(b_r) * (1 - mean(b_r)) / n)
    assert abs(d - 0.034) < 1e-9 and lo < d < hi, f"setup: difference {d:+.3f}; the interval {fp((lo, hi))} must contain it"
    assert lo > 0.0 and hi - lo < 0.07, (
        f"paired, this comparison has standard error about 0.0117, so the 95% interval is about +0.012 to +0.058 and excludes 0; got {fp((lo, hi))}. "
        f"An unpaired analysis would give a standard error of {se_un:.4f} and include 0")
    return f"paired interval for B - A on the 500-question example: [{lo:+.3f}, {hi:+.3f}] (an unpaired analysis: [{d - Z95 * se_un:+.3f}, {d + Z95 * se_un:+.3f}])"


# =============================================================================
# Milestone 3: hypothesis tests
# =============================================================================
def exact_permutation_p(x, y):
    pooled = list(x) + list(y)
    nx = len(x)
    obs = abs(mean(y) - mean(x))
    total = hits = 0
    for idx in itertools.combinations(range(len(pooled)), nx):
        s = set(idx)
        gx = [pooled[i] for i in idx]
        gy = [pooled[i] for i in range(len(pooled)) if i not in s]
        total += 1
        hits += abs(mean(gy) - mean(gx)) >= obs - 1e-12
    return hits / total


def exact_sign_flip_p(diffs):
    obs = abs(sum(diffs))
    hits = sum(abs(sum(s * d for s, d in zip(signs, diffs))) >= obs - 1e-12 for signs in itertools.product((1, -1), repeat=len(diffs)))
    return hits / 2 ** len(diffs)


def m3():
    z, p = mod.two_proportion_z_test(790, 8000, 864, 8000)
    assert near(z, 1.9215803331713335, 1e-9) and near(p, 0.05465858520909599, 1e-6), (
        f"two_proportion_z_test(790, 8000, 864, 8000) should give z = 1.9216, p = 0.0547 (chapter 15); got z = {z:.4f}, p = {p:.4f}. "
        "Under H0 both arms share one rate, so use the POOLED rate (k1 + k2) / (n1 + n2) in the standard error")
    z2, p2 = mod.two_proportion_z_test(864, 8000, 790, 8000)
    assert near(z2, -z) and near(p2, p), "swapping the arms should flip the sign of z and leave the two-sided p unchanged"
    z0, p0 = mod.two_proportion_z_test(100, 1000, 100, 1000)
    assert near(z0, 0.0) and near(p0, 1.0), f"equal rates give z = 0 and p = 1; got z = {z0}, p = {p0}"
    k1, n1, k2, n2 = 30, 100, 70, 250
    pool = (k1 + k2) / (n1 + n2)
    want = (k2 / n2 - k1 / n1) / math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    z3, _ = mod.two_proportion_z_test(k1, n1, k2, n2)
    assert near(z3, want, 1e-9), f"with unequal arms (30/100 against 70/250) z should be {want:.4f}, with the variance term pooled * (1 - pooled) * (1/n1 + 1/n2); got {z3:.4f}"

    # permutation test against exhaustive enumeration
    for x, y in (([1, 2, 3], [4, 5, 6]), ([1, 2, 3, 4], [2, 6, 7, 9]), ([3.1, 2.7, 4.0, 3.3, 2.9], [3.0, 3.6]), ([5, 5, 5], [5, 5, 6])):
        exact = exact_permutation_p(x, y)
        B = 20000
        got = mod.permutation_test(x, y, B=B, seed=3)
        tol = max(0.012, 5 * math.sqrt(exact * (1 - exact) / B))
        assert abs(got - exact) < tol, (
            f"permutation_test({x}, {y}) should be close to the exact two-sided p = {exact:.4f} (found by trying all {math.comb(len(x) + len(y), len(x))} splits); got {got:.4f} with B = {B}. "
            "Check: two-sided (|difference|), the difference taken between the two groups of the ORIGINAL sizes, and (count + 1) / (B + 1)")
    assert mod.permutation_test([0] * 10, [1] * 10, B=99, seed=1) == 0.01, (
        "perfectly separated groups: no random shuffle will be as extreme, so p = (0 + 1) / (99 + 1) = 0.01, never 0 (the observed split is itself one permutation)")
    assert near(mod.permutation_test([0.1, 0.2, 0.3], [0.3, 0.2, 0.1], B=300, seed=1), 1.0), (
        "groups with the same values have observed difference 0, and EVERY shuffle is at least that extreme, so p = 1. "
        "If you got less, rounding made a shuffled 0.0000000000000001 'smaller' than the observed 0: compare with a tolerance (>= observed - 1e-12)")
    assert mod.permutation_test([1, 2, 3, 9], [4, 5, 6, 7], B=500, seed=8) == mod.permutation_test([1, 2, 3, 9], [4, 5, 6, 7], B=500, seed=8), "same seed, same p"
    x = [1, 2, 3, 4, 5, 6]
    y = [3, 4, 5, 6, 7, 20]
    xs0, ys0 = list(x), list(y)
    mod.permutation_test(x, y, B=50, seed=1)
    assert x == xs0 and y == ys0, "permutation_test must not shuffle the caller's lists; shuffle a copy of the pooled values"

    # sign-flip test against exhaustive enumeration
    for diffs in ([1, 2, 3, 4], [3, -1, 2, 5, -2, 4, 1], [0.5, -0.5, 1.0, 0.25, -2.0, 0.75, 1.5, -0.1], [0, 0, 0]):
        exact = exact_sign_flip_p(diffs)
        B = 20000
        got = mod.sign_flip_test(diffs, B=B, seed=2)
        tol = max(0.012, 5 * math.sqrt(exact * (1 - exact) / B))
        assert abs(got - exact) < tol, (f"sign_flip_test({diffs}) should be close to the exact p = {exact:.4f} (all {2 ** len(diffs)} sign patterns); got {got:.4f}. "
                                        "Flip every difference's sign independently with probability 1/2 and compare |mean|")
    diffs = [1] * 26 + [-1] * 9 + [0] * 465                       # the chapter's pattern: 26 questions only B gets right, 9 only A
    k = 35
    exact = 2 * sum(math.comb(k, j) for j in range(26, k + 1)) / 2 ** k
    got = mod.sign_flip_test(diffs, B=20000, seed=4)
    assert abs(got - exact) < 0.004, (f"the 500 per-question differences (26 of +1, 9 of -1, 465 zeros) have exact two-sided p = {exact:.5f} (a binomial tail over the 35 that differ); got {got:.5f}. "
                                      "Questions where the models agree (difference 0) never change the flipped sum")

    # calibration: with no real difference the test rejects at the stated rate; with a real one it usually rejects
    for s in seeds([5]):
        rng = random.Random(s)
        reject_null = reject_real = 0
        E = 300
        for _ in range(E):
            xs = [rng.gauss(0, 1) for _ in range(15)]
            ys = [rng.gauss(0, 1) for _ in range(15)]
            reject_null += mod.permutation_test(xs, ys, B=300, seed=rng.randrange(10 ** 6)) < 0.05
            zs = [v + 1.5 for v in ys]
            reject_real += mod.permutation_test(xs, zs, B=300, seed=rng.randrange(10 ** 6)) < 0.05
        assert 3 <= reject_null <= 32, (f"seed {s}: with NO real difference, p < 0.05 should happen in about 5% of experiments (15 of {E}); it happened in {reject_null}. "
                                        "A rate far from 5% means the p-value is not the fraction of shuffles at least as extreme")
        assert reject_real > 0.8 * E, f"seed {s}: a shift of 1.5 standard deviations with 15 per group should be detected in most experiments; rejected {reject_real} of {E}"
    return f"z-test on the chapter's example: z = {z:.3f}, p = {p:.4f}; sign-flip p for the 26-versus-9 pattern = {got:.4f} (exact {exact:.4f}); null rejection rate {reject_null / E:.1%}, power {reject_real / E:.1%}"


# =============================================================================
# Milestone 4: power and the winner's curse
# =============================================================================
def oracle_n(p1, p2, alpha_z, power_z):
    return math.ceil((alpha_z + power_z) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2)


def m4():
    for p1, p2 in ((0.10, 0.13), (0.10, 0.12), (0.10, 0.11), (0.10, 0.105), (0.5, 0.52)):
        want = oracle_n(p1, p2, Z95, ZP80)
        got = mod.sample_size(p1, p2)
        assert got == want, (f"sample_size({p1}, {p2}) should be {want:,} per arm = ceil((1.96 + 0.8416)^2 x (p1(1-p1) + p2(1-p2)) / (p2-p1)^2); got {got}. "
                             "Round UP: a fraction of a user still needs a whole one")
    got = mod.sample_size(0.20, 0.25, alpha=0.01, power=0.90)
    assert got == oracle_n(0.20, 0.25, Z995, ZP90), f"sample_size(0.20, 0.25, alpha=0.01, power=0.90) should be {oracle_n(0.20, 0.25, Z995, ZP90):,} (z = 2.576 and 1.282); got {got}"
    assert abs(mod.sample_size(0.10, 0.12) - mod.sample_size(0.12, 0.10)) < 0.05 * mod.sample_size(0.10, 0.12), "a lift and a drop of the same size need about the same n"
    ratio = mod.sample_size(0.10, 0.105) / mod.sample_size(0.10, 0.110)
    assert 3.7 < ratio < 4.1, f"halving the effect should cost about 4 times the users; the ratio was {ratio:.2f}"

    n = mod.sample_size(0.10, 0.12)
    for s in seeds([1]):
        power = mod.simulate_power(0.10, 0.12, n, E=4000, seed=s)
        assert 0.76 < power < 0.84, (f"seed {s}: at the sample size the formula chose ({n:,} per arm) for 80% power, {4000} simulated experiments should reject about 80% of the time; got {power:.1%}. "
                                     "Draw both counts with binomial, test with two_proportion_z_test, and count p < alpha")
        fpr = mod.simulate_power(0.10, 0.10, 1000, E=4000, seed=s)
        assert 0.035 < fpr < 0.065, f"seed {s}: with no true difference the rejection rate should be near alpha = 5%; got {fpr:.1%}"
        assert mod.simulate_power(0.10, 0.50, 200, E=300, seed=s) == 1.0, "a huge effect (10% to 50%) with 200 per arm should be detected every time"
        assert mod.simulate_power(0.10, 0.12, 500, E=300, seed=s) == mod.simulate_power(0.10, 0.12, 500, E=300, seed=s), "the same seed must give the same answer"
        none = mod.simulate_power(0.0, 0.0, 100, E=50, seed=s)
        assert none == 0.0, "if nobody ever converts, the pooled variance is 0: do not divide by it, and do not count it as a rejection"
    small = mod.simulate_power(0.10, 0.12, 300, E=3000, seed=2)
    big = mod.simulate_power(0.10, 0.12, 8000, E=1500, seed=2)
    assert small < 0.2 and big > 0.95, f"power should rise with n: expected under 20% at 300 per arm and over 95% at 8,000; got {small:.2f} and {big:.2f}"

    # winner's curse
    for s in seeds([3]):
        under = mod.winners_curse(0.10, 0.105, 2000, E=5000, seed=s)
        assert 0.05 < under["power"] < 0.10, f"seed {s}: true lift +0.5 points with 2,000 per arm has power of only about 7%; got {under['power']:.1%}"
        assert 0.0042 < under["mean_lift_all"] < 0.0058, f"seed {s}: averaged over ALL experiments the observed lift is unbiased, about +0.50 points; got {under['mean_lift_all']:+.2%}"
        ratio = under["mean_lift_significant"] / 0.005
        assert 3.0 < ratio < 5.5, (f"seed {s}: among the experiments that reach significance the average observed lift is inflated to about 4.5 times the truth "
                                   f"(+2.3 points); got {under['mean_lift_significant']:+.2%}, {ratio:.1f}x. Only wins with p < alpha AND a positive lift count")
        strong = mod.winners_curse(0.10, 0.13, 4000, E=1500, seed=s)
        assert strong["power"] > 0.97 and abs(strong["mean_lift_significant"] - strong["mean_lift_all"]) < 0.1 * 0.03, (
            f"seed {s}: with high power nearly every experiment is a win and the filter does little harm; got power {strong['power']:.1%}, lifts {strong['mean_lift_all']:+.3f} and {strong['mean_lift_significant']:+.3f}")
    worse = mod.winners_curse(0.20, 0.10, 500, E=200, seed=1)
    assert worse["power"] == 0.0 and worse["mean_lift_significant"] == 0.0, (
        "a treatment that is clearly WORSE is never a 'win': power 0 and mean_lift_significant 0.0 (the value for 'no wins'). "
        f"Got {worse}")
    return (f"80% design: n = {n:,}, simulated power {power:.1%}, false positives {fpr:.1%}; winner's curse: power {under['power']:.1%}, "
            f"true +0.50 points, all experiments {under['mean_lift_all']:+.2%}, significant ones {under['mean_lift_significant']:+.2%}")


# =============================================================================
# Milestone 5: peeking
# =============================================================================
def m5():
    paths = [[0.5, 2.0], [3.0, 1.0], [0.1, 0.2], [-2.5, 0.0]]
    assert mod.end_only_rate(paths, 1.96) == 0.25, f"only the first path ends beyond 1.96, so end_only_rate should be 0.25; got {mod.end_only_rate(paths, 1.96)}"
    assert mod.peeking_rate(paths, 1.96) == 0.75, f"paths 1, 2 and 4 cross 1.96 at some look (absolute value: -2.5 counts), so peeking_rate should be 0.75; got {mod.peeking_rate(paths, 1.96)}"
    assert mod.peeking_rate(paths, 5.0) == 0.0 and mod.peeking_rate(paths, 0.0) == 1.0, "a boundary above every z gives 0, a boundary of 0 gives 1"
    for looks, want in ((1, Z95), (2, 2.241402727604945), (10, 2.8070337683438042), (20, 3.0233414397391405)):
        assert near(mod.bonferroni_boundary(looks), want, 1e-6), f"bonferroni_boundary({looks}) should be z at 1 - 0.05 / {2 * looks} = {want:.4f}; got {mod.bonferroni_boundary(looks):.4f}"
    fake = [[float(i), -0.5] for i in range(1, 21)]               # per-path maxima 1, 2, ..., 20
    c = mod.pocock_boundary(fake, 0.05)
    assert near(c, 19.0), (f"with maxima 1..20 and alpha = 5%, exactly one path (the 20) may exceed the boundary, so it is 19.0; got {c}. "
                           "Take the (1 - alpha) quantile of the per-path maxima of |z|: the ceil(0.95 x 20) = 19th smallest")
    fake = [[-float(i), 0.0] for i in range(1, 101)]
    assert near(mod.pocock_boundary(fake, 0.05), 95.0) and near(mod.pocock_boundary(fake, 0.10), 90.0), (
        "maxima 1..100 (the sign does not matter): alpha = 5% leaves five paths above, so 95.0; alpha = 10% gives 90.0")

    for s in seeds([7]):
        P = mod.z_paths(2, 2000, 0.10, 3000, s)
        assert len(P) == 3000 and all(len(r) == 2 for r in P), f"seed {s}: z_paths(2, 2000, 0.1, 3000, s) should give 3000 lists of 2 z values; got {len(P)} lists of {len(P[0]) if P else '?'}"
        for j in (0, 1):
            col = [r[j] for r in P]
            m = mean(col)
            sd = math.sqrt(mean([(v - m) ** 2 for v in col]))
            assert abs(m) < 0.08 and 0.92 < sd < 1.08, (f"seed {s}: with no real difference the z at look {j + 1} should have mean 0 and spread 1; got mean {m:+.3f}, std dev {sd:.3f}. "
                                                        "Check the pooled standard error sqrt(2 pooled (1 - pooled) / n) and that n is the CUMULATIVE users per arm")
        c1 = [r[0] for r in P]
        c2 = [r[1] for r in P]
        m1_, m2_ = mean(c1), mean(c2)
        cov = mean([(a - m1_) * (b - m2_) for a, b in zip(c1, c2)])
        corr = cov / (math.sqrt(mean([(a - m1_) ** 2 for a in c1])) * math.sqrt(mean([(b - m2_) ** 2 for b in c2])))
        assert 0.62 < corr < 0.79, (f"seed {s}: look 2 contains all of look 1's data plus as much again, so the two z values should correlate at about 1/sqrt(2) = 0.71; got {corr:.2f}. "
                                    "Values near 0 mean each look used only its own new block: accumulate the counts instead")
        assert mod.z_paths(4, 400, 0.1, 5, s) == mod.z_paths(4, 400, 0.1, 5, s), f"seed {s}: the same seed must reproduce the same paths"
        assert len(mod.z_paths(3, 100, 0.1, 2, s)[0]) == 3, "n_final not divisible by looks (100 over 3 looks): use blocks of 33"
        assert all(z == 0.0 for r in mod.z_paths(3, 30, 0.0, 4, s) for z in r), "nobody converts: the standard error is 0, so z must be 0.0, not an error"

        one = mod.z_paths(1, 2000, 0.10, 4000, s)
        r1 = mod.end_only_rate(one, 1.96)
        assert 0.037 < r1 < 0.066, f"seed {s}: a single look at the end should be wrong 5% of the time; got {r1:.1%}"
        ten = mod.z_paths(10, 2000, 0.10, 4000, s)
        e10, p10 = mod.end_only_rate(ten, 1.96), mod.peeking_rate(ten, 1.96)
        assert 0.037 < e10 < 0.066, f"seed {s}: looking at the end only, the false-positive rate is still 5% however many looks you planned; got {e10:.1%}"
        assert 0.16 < p10 < 0.24, f"seed {s}: stopping at the first of 10 looks with p < 0.05 should give a false-positive rate near 19%; got {p10:.1%}"
        bon = mod.bonferroni_boundary(10)
        rb = mod.peeking_rate(ten, bon)
        assert 0.015 < rb < 0.047, f"seed {s}: the Bonferroni boundary {bon:.3f} is safe but conservative; its false-positive rate over 10 looks should be 2% to 4%, got {rb:.1%}"
        cp = mod.pocock_boundary(ten, 0.05)
        rp = mod.peeking_rate(ten, cp)
        assert 2.40 < cp < 2.70 and 0.045 <= rp <= 0.0501, (
            f"seed {s}: the constant boundary giving 5% over 10 looks is about 2.55 (between Bonferroni's {bon:.2f} and the unadjusted 1.96); got {cp:.3f} with rate {rp:.2%}")
        assert cp < bon, f"seed {s}: the calibrated boundary {cp:.3f} should be less strict than Bonferroni's {bon:.3f} (looks are correlated, so Bonferroni over-corrects)"
    return (f"A/A tests, 10 looks, {len(ten):,} experiments: one look at the end {e10:.1%}, stop at first p<0.05 {p10:.1%}; "
            f"Bonferroni z = {bon:.3f} gives {rb:.1%}, calibrated z = {cp:.3f} gives {rp:.1%}")


# =============================================================================
# Milestone 6: coverage audit and the experiment report
# =============================================================================
def m6():
    assert mod.coverage(lambda s: (0, 1), lambda rng: rng.random(), 0.5, E=50) == 1.0, "an interval (0, 1) always contains 0.5"
    assert mod.coverage(lambda s: (2, 3), lambda rng: rng.random(), 0.5, E=50) == 0.0, "an interval (2, 3) never contains 0.5"
    calls = []
    cov = mod.coverage(lambda s: (s - 0.1, s + 0.1), lambda rng: calls.append(1) or rng.random(), 0.5, E=5000, seed=1)
    assert len(calls) == 5000, f"the sampler must be called exactly E = 5000 times, once per experiment; it was called {len(calls)} times"
    assert 0.18 < cov < 0.22, f"the interval U +/- 0.1 contains 0.5 exactly when |U - 0.5| <= 0.1: probability 0.2; got {cov:.3f}. Share one random.Random(seed) across the experiments"
    assert mod.coverage(lambda s: (s - 0.1, s + 0.1), lambda rng: rng.random(), 0.5, E=100, seed=4) == mod.coverage(lambda s: (s - 0.1, s + 0.1), lambda rng: rng.random(), 0.5, E=100, seed=4), "same seed, same answer"

    for s in seeds([1]):
        bern = lambda n, p: (lambda rng: mod.bernoulli_sample(rng, n, p))
        wald = mod.coverage(lambda smp: mod.wald_interval(sum(smp), len(smp)), bern(100, 0.02), 0.02, E=3000, seed=s)
        wilson = mod.coverage(lambda smp: mod.wilson_interval(sum(smp), len(smp)), bern(100, 0.02), 0.02, E=3000, seed=s)
        assert wald < 0.90, f"seed {s}: for a rare event (true rate 2%, n = 100) the Wald interval covers only about 87%; got {wald:.1%}"
        assert 0.92 < wilson < 0.97, f"seed {s}: the Wilson interval should cover close to 95% there; got {wilson:.1%}"
        wald_mid = mod.coverage(lambda smp: mod.wald_interval(sum(smp), len(smp)), bern(400, 0.30), 0.30, E=2000, seed=s)
        assert 0.92 < wald_mid < 0.97, f"seed {s}: in the comfortable middle (rate 30%, n = 400) even the Wald interval is near 95%; got {wald_mid:.1%}"

        expo = lambda n: (lambda rng: [rng.expovariate(1 / 100) for _ in range(n)])
        c10 = mod.coverage(mod.mean_interval, expo(10), 100.0, E=3000, seed=s)
        c200 = mod.coverage(mod.mean_interval, expo(200), 100.0, E=3000, seed=s)
        assert 0.83 < c10 < 0.91 and 0.92 < c200 < 0.97, (f"seed {s}: the formula interval for the mean of a skewed (exponential) population needs data: "
                                                         f"about 87% coverage at n = 10 and 94% at n = 200; got {c10:.1%} and {c200:.1%}")
        logn = lambda rng: [rng.lognormvariate(4.6, 0.7) for _ in range(60)]
        med = lambda xs: sorted(xs)[len(xs) // 2 - 1] / 2 + sorted(xs)[len(xs) // 2] / 2
        boot = mod.coverage(lambda smp: mod.bootstrap_interval(smp, med, B=300, seed=1), logn, math.exp(4.6), E=400, seed=s)
        assert 0.88 < boot < 0.995, f"seed {s}: the bootstrap interval for the MEDIAN of 60 skewed values (no formula needed) should cover about 95%; got {boot:.1%}"

    r = mod.ab_report(790, 8000, 864, 8000, 0.012)
    lift = 864 / 8000 - 790 / 8000
    assert near(r["lift"], lift) and near(r["z"], 1.9215803331713335, 1e-6) and near(r["p"], 0.05465858520909599, 1e-6), f"the chapter's experiment: lift {lift:+.5f}, z 1.9216, p 0.0547; got {r}"
    se = math.sqrt(0.09875 * (1 - 0.09875) / 8000 + 0.108 * (1 - 0.108) / 8000)
    assert pair_near(r["interval"], (lift - Z95 * se, lift + Z95 * se), 1e-6), f"interval should be lift -/+ 1.96 x {se:.5f} = {fp((lift - Z95 * se, lift + Z95 * se))} (UNPOOLED standard error); got {fp(r['interval'])}"
    assert r["verdict"] == "inconclusive", f"p = 0.0547 is above 0.05, so the verdict is 'inconclusive'; got {r['verdict']!r}"
    q = 0.09875 + 0.012
    se_alt = math.sqrt(0.09875 * (1 - 0.09875) / 8000 + q * (1 - q) / 8000)
    want_power = 0.5 * math.erfc(-(0.012 / se_alt - Z95) / math.sqrt(2)) + 0.5 * math.erfc((0.012 / se_alt + Z95) / math.sqrt(2))
    assert near(r["power"], want_power, 1e-6), f"power to detect +1.2 points with 8,000 per arm should be {want_power:.4f}: phi(mde/se - 1.96) + phi(-mde/se - 1.96) with se from the baseline and baseline + mde; got {r['power']:.4f}"
    assert r["n_needed"] == mod.sample_size(0.09875, q), f"n_needed should be sample_size(p1-hat, p1-hat + mde) = {mod.sample_size(0.09875, q):,}; got {r['n_needed']}"
    assert r["power"] < 0.8 < 1, "this design is underpowered for +1.2 points; the report's numbers must show it (power below 80%)"

    win = mod.ab_report(500, 5000, 620, 5000, 0.01)
    assert win["verdict"] == "win" and win["interval"][0] > 0 and win["p"] < 0.05, f"500/5000 against 620/5000 is a clear win; got {win['verdict']!r}, p = {win['p']:.4f}"
    loss = mod.ab_report(620, 5000, 500, 5000, 0.01)
    assert loss["verdict"] == "loss" and loss["interval"][1] < 0, f"the same data with the arms swapped is a significant loss; got {loss['verdict']!r}"
    tie = mod.ab_report(100, 1000, 100, 1000, 0.02)
    assert tie["verdict"] == "inconclusive" and near(tie["lift"], 0.0) and near(tie["p"], 1.0), f"identical arms: lift 0, p = 1, inconclusive; got {tie}"
    nn = mod.sample_size(0.10, 0.11)
    on_design = mod.ab_report(round(0.10 * nn), nn, round(0.10 * nn), nn, 0.01)
    assert 0.78 < on_design["power"] < 0.82, f"an experiment with the n the formula chose for 80% power should report power near 80%; got {on_design['power']:.3f}"
    return (f"coverage (nominal 95%): Wald at rate 2% {wald:.1%}, Wilson {wilson:.1%}; mean of 10 exponentials {c10:.1%}, of 200 {c200:.1%}; bootstrap median {boot:.1%}\n"
            f"ab_report(790/8000, 864/8000): lift {r['lift']:+.2%}, p {r['p']:.4f}, {r['verdict']}, power {r['power']:.0%} at +1.2 points, {r['n_needed']:,} per arm needed")


MILESTONES = [
    (1, "Milestone 1: standard errors and intervals", m1),
    (2, "Milestone 2: the bootstrap", m2),
    (3, "Milestone 3: hypothesis tests", m3),
    (4, "Milestone 4: power and the winner's curse", m4),
    (5, "Milestone 5: peeking", m5),
    (6, "Milestone 6: coverage audit and the experiment report", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 5 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
