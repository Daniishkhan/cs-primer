# Drill: A0 Lab 5, milestone 1 of 6: standard errors and intervals (step 2 of 5)
# Everything else in this file is already written. Fill in:
#     std_error
# Check it with: python3 check.py 1

"""Lab 5: A Statistics Toolkit for Experiments (reference solution).

The tools of chapter 15 written over plain Python lists: intervals for means and proportions,
the bootstrap, permutation tests, power by simulation, the peeking trap, and a small experiment
report. Standard library only.

Notation follows chapters 12 and 15: n is a sample size, p a probability, k a count of
successes, z a standardised statistic and alpha the false-positive rate you accept.
Every random function takes a `seed` (or an `rng`) so a run can be replayed exactly.
"""
import math
import random


# =============================================================================
# Given: the normal distribution, a fast binomial sampler, small helpers
# =============================================================================
def phi(z):
    """The standard normal cdf: P(Z <= z)."""
    return 0.5 * math.erfc(-z / math.sqrt(2))


def phi_inv(p):
    """The standard normal quantile (inverse cdf), found by bisection. phi_inv(0.975) = 1.96."""
    lo, hi = -10.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def two_sided_p(z):
    """The two-sided Gaussian tail area: P(|Z| >= |z|)."""
    return math.erfc(abs(z) / math.sqrt(2))


def median(xs):
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def binomial(rng, n, p):
    """Draw from Binomial(n, p) exactly, by jumping between successes with geometric gaps.

    The cost is about n * p random numbers rather than n, which keeps simulations fast.
    """
    if p <= 0.0:
        return 0
    if p >= 1.0:
        return n
    if p > 0.5:
        return n - binomial(rng, n, 1.0 - p)
    log_q = math.log1p(-p)
    count, pos = 0, -1
    while True:
        pos += 1 + int(math.log(1.0 - rng.random()) / log_q)
        if pos >= n:
            return count
        count += 1


def bernoulli_sample(rng, n, p):
    """n independent 0/1 outcomes, each 1 with probability p."""
    return [1 if rng.random() < p else 0 for _ in range(n)]


def mean(xs):
    return sum(xs) / len(xs)


# =============================================================================
# Milestone 1: standard errors and intervals
# =============================================================================
def sample_variance(xs):
    """The unbiased sample variance: sum((x - mean)^2) / (n - 1)."""
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def std_error(xs):
    """The standard error of the mean: sqrt(sample variance / n), i.e. sigma-hat / sqrt(n).

    std_error([2, 4, 6]) == sqrt(4 / 3) = 1.1547...
    """
    raise NotImplementedError("TODO milestone 1: std_error")


def mean_interval(xs, conf=0.95):
    """Normal-approximation interval for a mean: mean +/- z * standard error (z = 1.96 for 95%)."""
    z = phi_inv(0.5 + conf / 2)
    m, se = mean(xs), std_error(xs)
    return (m - z * se, m + z * se)


def wald_interval(k, n, conf=0.95):
    """The simple interval for a proportion: p-hat +/- z * sqrt(p-hat (1 - p-hat) / n)."""
    z = phi_inv(0.5 + conf / 2)
    p = k / n
    half = z * math.sqrt(p * (1 - p) / n)
    return (p - half, p + half)


def wilson_interval(k, n, conf=0.95):
    """The Wilson (1927) interval for a proportion, always inside [0, 1].

    centre = (p + z^2 / 2n) / (1 + z^2 / n)
    half   = z * sqrt(p (1 - p) / n + z^2 / 4n^2) / (1 + z^2 / n)
    """
    z = phi_inv(0.5 + conf / 2)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# =============================================================================
# Milestone 2: the bootstrap
# =============================================================================
def percentile(sorted_xs, q):
    """The q-th percentile (0 to 100) of an already sorted list, by linear interpolation.

    The same rule as NumPy's default: position (n - 1) * q / 100, blending the two neighbours.
    """
    pos = (len(sorted_xs) - 1) * q / 100
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_xs) - 1)
    frac = pos - lo
    return sorted_xs[lo] * (1 - frac) + sorted_xs[hi] * frac


def bootstrap_stats(data, stat, B, rng):
    """B values of stat(resample), each resample drawn WITH replacement and the same size as data."""
    n = len(data)
    return [stat(rng.choices(data, k=n)) for _ in range(B)]


def bootstrap_interval(data, stat, B=2000, conf=0.95, seed=0):
    """Percentile bootstrap interval for stat(data): the (1-conf)/2 and (1+conf)/2 percentiles."""
    boots = sorted(bootstrap_stats(data, stat, B, random.Random(seed)))
    alpha = 1 - conf
    return (percentile(boots, 100 * alpha / 2), percentile(boots, 100 * (1 - alpha / 2)))


def paired_bootstrap_interval(a, b, B=2000, conf=0.95, seed=0):
    """Interval for mean(b) - mean(a) when a[i] and b[i] are two systems on the SAME question i.

    Resample the question indices, so each question keeps both of its results.
    """
    rng = random.Random(seed)
    n = len(a)
    diffs = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(b[i] - a[i] for i in idx) / n)
    diffs.sort()
    alpha = 1 - conf
    return (percentile(diffs, 100 * alpha / 2), percentile(diffs, 100 * (1 - alpha / 2)))


# =============================================================================
# Milestone 3: hypothesis tests
# =============================================================================
def two_proportion_z_test(k1, n1, k2, n2):
    """Pooled two-proportion z-test of H0: both arms convert at the same rate.

    Returns (z, two_sided_p) with z = (p2 - p1) / sqrt(pooled (1 - pooled) (1/n1 + 1/n2)).
    """
    p1, p2 = k1 / n1, k2 / n2
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se
    return z, two_sided_p(z)


def permutation_test(x, y, B=5000, seed=0):
    """Two-sided permutation test for a difference in means.

    Shuffle the pooled values B times, split them into groups of the original sizes, and count
    how often |difference| is at least the observed one. Return (count + 1) / (B + 1): the +1
    counts the observed split itself as one of the permutations, so p is never 0.
    """
    rng = random.Random(seed)
    nx = len(x)
    obs = abs(mean(y) - mean(x))
    pooled = list(x) + list(y)
    count = 0
    for _ in range(B):
        rng.shuffle(pooled)
        d = mean(pooled[nx:]) - mean(pooled[:nx])
        if abs(d) >= obs - 1e-12:
            count += 1
    return (count + 1) / (B + 1)


def sign_flip_test(diffs, B=5000, seed=0):
    """Two-sided paired test: under H0 each per-question difference is as likely to be + as -.

    Flip the sign of every difference at random B times; return (count + 1) / (B + 1) where
    count is how often |mean of flipped diffs| >= |observed mean|.
    """
    rng = random.Random(seed)
    obs = abs(mean(diffs))
    count = 0
    for _ in range(B):
        m = sum(d if rng.random() < 0.5 else -d for d in diffs) / len(diffs)
        if abs(m) >= obs - 1e-12:
            count += 1
    return (count + 1) / (B + 1)


# =============================================================================
# Milestone 4: power and the winner's curse
# =============================================================================
def sample_size(p1, p2, alpha=0.05, power=0.80):
    """Users per arm (rounded UP to an integer) to detect p1 -> p2 with a two-sided z-test.

    n = (z_{alpha/2} + z_{power})^2 * (p1 (1 - p1) + p2 (1 - p2)) / (p2 - p1)^2
    """
    za, zb = phi_inv(1 - alpha / 2), phi_inv(power)
    var = p1 * (1 - p1) + p2 * (1 - p2)
    return math.ceil((za + zb) ** 2 * var / (p2 - p1) ** 2)


def simulate_power(p1, p2, n, E=2000, alpha=0.05, seed=0):
    """Fraction of E simulated experiments (n users per arm, true rates p1 and p2) that reject H0."""
    rng = random.Random(seed)
    hits = 0
    for _ in range(E):
        k1, k2 = binomial(rng, n, p1), binomial(rng, n, p2)
        if k1 + k2 in (0, 2 * n):
            continue                      # no variation at all: the test cannot reject
        if two_proportion_z_test(k1, n, k2, n)[1] < alpha:
            hits += 1
    return hits / E


def winners_curse(p1, p2, n, E=4000, alpha=0.05, seed=0):
    """Simulate E experiments and report what 'ship the significant ones' does to the estimate.

    A win is p < alpha with a POSITIVE observed lift. Returns a dict:
      power:                 fraction of experiments that are wins
      mean_lift_all:         average observed lift (p2-hat - p1-hat) over every experiment
      mean_lift_significant: average observed lift over the wins only (0.0 if there are none)
    """
    rng = random.Random(seed)
    lifts, wins = [], []
    for _ in range(E):
        k1, k2 = binomial(rng, n, p1), binomial(rng, n, p2)
        lift = (k2 - k1) / n
        lifts.append(lift)
        if k1 + k2 not in (0, 2 * n) and lift > 0 and two_proportion_z_test(k1, n, k2, n)[1] < alpha:
            wins.append(lift)
    return {"power": len(wins) / E, "mean_lift_all": mean(lifts),
            "mean_lift_significant": mean(wins) if wins else 0.0}


# =============================================================================
# Milestone 5: peeking
# =============================================================================
def z_paths(looks, n_final, p, E, seed):
    """E simulated A/A tests (both arms convert at p), each analysed at `looks` equally spaced looks.

    Returns a list of E lists of `looks` z statistics. Look i (1-based) uses the CUMULATIVE data
    of the first i blocks of n_final // looks users per arm, so the paths are random walks.
    If the standard error is 0 (everyone converted, or nobody), use z = 0.
    """
    rng = random.Random(seed)
    block = n_final // looks
    paths = []
    for _ in range(E):
        ka = kb = 0
        path = []
        for i in range(1, looks + 1):
            ka += binomial(rng, block, p)
            kb += binomial(rng, block, p)
            n = block * i
            pooled = (ka + kb) / (2 * n)
            se = math.sqrt(2 * pooled * (1 - pooled) / n)
            path.append((kb - ka) / n / se if se > 0 else 0.0)
        paths.append(path)
    return paths


def end_only_rate(paths, c):
    """Fraction of paths whose LAST z has |z| > c: one look, at the planned end."""
    return sum(1 for path in paths if abs(path[-1]) > c) / len(paths)


def peeking_rate(paths, c):
    """Fraction of paths where ANY look has |z| > c: stop at the first look that crosses."""
    return sum(1 for path in paths if any(abs(z) > c for z in path)) / len(paths)


def bonferroni_boundary(looks, alpha=0.05):
    """The z boundary that splits alpha equally over the looks: z_{alpha / (2 * looks)}."""
    return phi_inv(1 - alpha / (2 * looks))


def pocock_boundary(paths, alpha=0.05):
    """The constant boundary c whose peeking_rate on THESE paths is at most alpha.

    That is the (1 - alpha) quantile of the per-path maximum of |z|: the smallest c such that
    at most a fraction alpha of the paths ever exceed it.
    """
    maxima = sorted(max(abs(z) for z in path) for path in paths)
    k = math.ceil(round((1 - alpha) * len(maxima), 9)) - 1    # 0-based index of the (1 - alpha) quantile (round() guards float noise)
    return maxima[k]


# =============================================================================
# Milestone 6: coverage audit and the experiment report
# =============================================================================
def coverage(interval_fn, sampler, truth, E=1000, seed=0):
    """How often does the interval contain the truth? Repeat the experiment E times.

    sampler(rng) draws one fresh sample; interval_fn(sample) returns (lo, hi). Return the
    fraction of the E intervals with lo <= truth <= hi.
    """
    rng = random.Random(seed)
    hits = 0
    for _ in range(E):
        lo, hi = interval_fn(sampler(rng))
        if lo <= truth <= hi:
            hits += 1
    return hits / E


def ab_report(k1, n1, k2, n2, mde, alpha=0.05):
    """Summarise a two-arm conversion experiment (control k1/n1, treatment k2/n2).

    `mde` is the smallest absolute lift worth detecting (0.012 means +1.2 points). Returns a dict:
      lift:     p2-hat - p1-hat
      interval: (lo, hi), lift +/- z * sqrt(p1(1-p1)/n1 + p2(1-p2)/n2), z for 1 - alpha
      z, p:     from two_proportion_z_test
      verdict:  "win" if p < alpha and lift > 0, "loss" if p < alpha and lift < 0, else "inconclusive"
      power:    the chance THIS design (n1, n2, baseline p1-hat) detects a true lift of exactly `mde`
      n_needed: users per arm for 80% power at `mde` from baseline p1-hat (sample_size)
    For the power, let q = p1-hat + mde and se = sqrt(p1(1-p1)/n1 + q(1-q)/n2), zc = z_{1-alpha/2}:
      power = phi(mde/se - zc) + phi(-mde/se - zc).
    """
    p1, p2 = k1 / n1, k2 / n2
    lift = p2 - p1
    zc = phi_inv(1 - alpha / 2)
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    z, p = two_proportion_z_test(k1, n1, k2, n2)
    if p < alpha:
        verdict = "win" if lift > 0 else "loss"
    else:
        verdict = "inconclusive"
    q = p1 + mde
    se_alt = math.sqrt(p1 * (1 - p1) / n1 + q * (1 - q) / n2)
    power = phi(mde / se_alt - zc) + phi(-mde / se_alt - zc)
    return {"lift": lift, "interval": (lift - zc * se, lift + zc * se), "z": z, "p": p,
            "verdict": verdict, "power": power, "n_needed": sample_size(p1, q, alpha)}
