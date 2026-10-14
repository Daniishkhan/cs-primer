"""Lab 5: A Statistics Toolkit for Experiments.

The tools of chapter 15 written over plain Python lists: intervals for means and proportions,
the bootstrap, permutation tests, power by simulation, the peeking trap, and a small experiment
report. Standard library only.

Notation follows chapters 12 and 15: n is a sample size, p a probability, k a count of
successes, z a standardised statistic and alpha the false-positive rate you accept.
Every random function takes a `seed` (or an `rng`) so a run can be replayed exactly.

What is GIVEN: the normal cdf and quantile, `binomial` (a fast exact sampler), `median`, `mean`
and `bernoulli_sample`. What YOU write:

    1  sample_variance, std_error, mean_interval, wald_interval, wilson_interval
    2  percentile, bootstrap_stats, bootstrap_interval, paired_bootstrap_interval
    3  two_proportion_z_test, permutation_test, sign_flip_test
    4  sample_size, simulate_power, winners_curse
    5  z_paths, end_only_rate, peeking_rate, bonferroni_boundary, pocock_boundary
    6  coverage, ab_report

`python3 check.py` runs the milestones; the lab page explains each one.
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
    """The unbiased sample variance: sum((x - mean)^2) / (n - 1).

    sample_variance([2, 4, 4, 4, 5, 5, 7, 9]) == 32 / 7 = 4.5714...  (the mean is 5)
    """
    raise NotImplementedError("TODO milestone 1: sample_variance")


def std_error(xs):
    """The standard error of the mean: sqrt(sample variance / n), i.e. sigma-hat / sqrt(n).

    std_error([2, 4, 6]) == sqrt(4 / 3) = 1.1547...
    """
    raise NotImplementedError("TODO milestone 1: std_error")


def mean_interval(xs, conf=0.95):
    """Normal-approximation interval for a mean: mean +/- z * standard error (z = 1.96 for 95%).

    Get z from the given phi_inv: for conf = 0.95 it is phi_inv(0.975).
    Returns a tuple (lo, hi).
    """
    raise NotImplementedError("TODO milestone 1: mean_interval")


def wald_interval(k, n, conf=0.95):
    """The simple interval for a proportion: p-hat +/- z * sqrt(p-hat (1 - p-hat) / n).

    wald_interval(50, 100) == (0.4020, 0.5980). Do NOT clip to [0, 1]: its failure is part of
    the lesson (wald_interval(20, 20) is the single point (1.0, 1.0)). Returns (lo, hi).
    """
    raise NotImplementedError("TODO milestone 1: wald_interval")


def wilson_interval(k, n, conf=0.95):
    """The Wilson (1927) interval for a proportion, always inside [0, 1].

    wilson_interval(20, 20) == (0.8389, 1.0): 20 out of 20 still leaves real doubt.
    wilson_interval(0, 50) starts at exactly 0.0. Returns (lo, hi); clip to [0, 1] to stay clear
    of rounding at the edges.

    centre = (p + z^2 / 2n) / (1 + z^2 / n)
    half   = z * sqrt(p (1 - p) / n + z^2 / 4n^2) / (1 + z^2 / n)
    """
    raise NotImplementedError("TODO milestone 1: wilson_interval")


# =============================================================================
# Milestone 2: the bootstrap
# =============================================================================
def percentile(sorted_xs, q):
    """The q-th percentile (0 to 100) of an already sorted list, by linear interpolation.

    The same rule as NumPy's default: position (n - 1) * q / 100, blending the two neighbours.

    percentile([10, 20, 30, 40], 50) == 25.0 (position 1.5); percentile(xs, 0) is the minimum
    and percentile(xs, 100) the maximum. Take care at q = 100: there is no neighbour above.
    """
    raise NotImplementedError("TODO milestone 2: percentile")


def bootstrap_stats(data, stat, B, rng):
    """B values of stat(resample), each resample drawn WITH replacement and the same size as data.

    `rng` is a random.Random; rng.choices(data, k=n) draws one resample. Do not modify `data`.
    Example: bootstrap_stats([1, 2, 3], max, 5, random.Random(0)) is a list of 5 values from {1, 2, 3}.
    """
    raise NotImplementedError("TODO milestone 2: bootstrap_stats")


def bootstrap_interval(data, stat, B=2000, conf=0.95, seed=0):
    """Percentile bootstrap interval for stat(data): the (1-conf)/2 and (1+conf)/2 percentiles.

    Build the bootstrap distribution with random.Random(seed), sort it, and read the 2.5th and
    97.5th percentiles for conf = 0.95 using your `percentile`. Returns (lo, hi); the same seed
    must give the same interval.
    """
    raise NotImplementedError("TODO milestone 2: bootstrap_interval")


def paired_bootstrap_interval(a, b, B=2000, conf=0.95, seed=0):
    """Interval for mean(b) - mean(a) when a[i] and b[i] are two systems on the SAME question i.

    Resample the question indices, so each question keeps both of its results. If b[i] == a[i] + 0.1
    for every i, the difference is 0.1 in EVERY resample and the interval is the single point
    (0.1, 0.1). Returns (lo, hi).
    """
    raise NotImplementedError("TODO milestone 2: paired_bootstrap_interval")


# =============================================================================
# Milestone 3: hypothesis tests
# =============================================================================
def two_proportion_z_test(k1, n1, k2, n2):
    """Pooled two-proportion z-test of H0: both arms convert at the same rate.

    Returns (z, two_sided_p) with z = (p2 - p1) / sqrt(pooled (1 - pooled) (1/n1 + 1/n2)),
    where pooled = (k1 + k2) / (n1 + n2). Use the given two_sided_p(z) for the tail area.

    two_proportion_z_test(790, 8000, 864, 8000) == (1.9216, 0.0547): the example of chapter 15.
    """
    raise NotImplementedError("TODO milestone 3: two_proportion_z_test")


def permutation_test(x, y, B=5000, seed=0):
    """Two-sided permutation test for a difference in means.

    Shuffle the pooled values B times, split them into groups of the original sizes, and count
    how often |difference| is at least the observed one. Return (count + 1) / (B + 1): the +1
    counts the observed split itself as one of the permutations, so p is never 0.

    The difference is mean(second group) - mean(first group). Use random.Random(seed), shuffle a
    COPY of the pooled list, and compare with a tiny tolerance (>= observed - 1e-12) so that exact
    ties count. permutation_test([1, 2, 3], [4, 5, 6]) is about 0.10: of the 20 ways to split six
    values into two groups of three, exactly 2 are as extreme as the observed one.
    """
    raise NotImplementedError("TODO milestone 3: permutation_test")


def sign_flip_test(diffs, B=5000, seed=0):
    """Two-sided paired test: under H0 each per-question difference is as likely to be + as -.

    Flip the sign of every difference at random B times; return (count + 1) / (B + 1) where
    count is how often |mean of flipped diffs| >= |observed mean|.

    sign_flip_test([1, 2, 3, 4]) is about 0.125: of the 16 sign patterns only the all-plus and
    all-minus ones give a mean as large as 2.5. Use random.Random(seed); compare with a tiny
    tolerance as in permutation_test.
    """
    raise NotImplementedError("TODO milestone 3: sign_flip_test")


# =============================================================================
# Milestone 4: power and the winner's curse
# =============================================================================
def sample_size(p1, p2, alpha=0.05, power=0.80):
    """Users per arm (rounded UP to an integer) to detect p1 -> p2 with a two-sided z-test.

    n = (z_{alpha/2} + z_{power})^2 * (p1 (1 - p1) + p2 (1 - p2)) / (p2 - p1)^2

    sample_size(0.10, 0.11) == 14749 and sample_size(0.10, 0.105) == 57760, the numbers of chapter 15.
    z_{alpha/2} = phi_inv(1 - alpha/2) and z_{power} = phi_inv(power). Use math.ceil.
    """
    raise NotImplementedError("TODO milestone 4: sample_size")


def simulate_power(p1, p2, n, E=2000, alpha=0.05, seed=0):
    """Fraction of E simulated experiments (n users per arm, true rates p1 and p2) that reject H0.

    Each experiment draws k1 = binomial(rng, n, p1) and k2 = binomial(rng, n, p2) with
    rng = random.Random(seed), then runs two_proportion_z_test and rejects when p < alpha. If
    k1 + k2 is 0 or 2n the pooled variance is 0: count that experiment as not rejecting.
    With p1 == p2 the answer is the false-positive rate, about alpha.
    """
    raise NotImplementedError("TODO milestone 4: simulate_power")


def winners_curse(p1, p2, n, E=4000, alpha=0.05, seed=0):
    """Simulate E experiments and report what 'ship the significant ones' does to the estimate.

    A win is p < alpha with a POSITIVE observed lift. Returns a dict:
      power:                 fraction of experiments that are wins
      mean_lift_all:         average observed lift (p2-hat - p1-hat) over every experiment
      mean_lift_significant: average observed lift over the wins only (0.0 if there are none)
    The lift of one experiment is (k2 - k1) / n. Draw the counts with binomial, as in simulate_power.
    """
    raise NotImplementedError("TODO milestone 4: winners_curse")


# =============================================================================
# Milestone 5: peeking
# =============================================================================
def z_paths(looks, n_final, p, E, seed):
    """E simulated A/A tests (both arms convert at p), each analysed at `looks` equally spaced looks.

    Returns a list of E lists of `looks` z statistics. Look i (1-based) uses the CUMULATIVE data
    of the first i blocks of n_final // looks users per arm, so the paths are random walks.
    If the standard error is 0 (everyone converted, or nobody), use z = 0.

    The z at look i is the pooled two-proportion z of the cumulative counts (ka, kb) over
    n = block * i users per arm: z = (kb/n - ka/n) / sqrt(2 * pooled * (1 - pooled) / n).
    Draw each block with binomial(rng, block, p) from rng = random.Random(seed): the arm A count
    first, then arm B. The last look of a path is the analysis you would do with no peeking.
    """
    raise NotImplementedError("TODO milestone 5: z_paths")


def end_only_rate(paths, c):
    """Fraction of paths whose LAST z has |z| > c: one look, at the planned end.

    end_only_rate([[0.5, 2.0], [3.0, 1.0]], 1.96) == 0.5 (only the first path ends beyond 1.96).
    """
    raise NotImplementedError("TODO milestone 5: end_only_rate")


def peeking_rate(paths, c):
    """Fraction of paths where ANY look has |z| > c: stop at the first look that crosses.

    peeking_rate([[0.5, 2.0], [3.0, 1.0]], 1.96) == 1.0 (the second path crossed at its first look).
    """
    raise NotImplementedError("TODO milestone 5: peeking_rate")


def bonferroni_boundary(looks, alpha=0.05):
    """The z boundary that splits alpha equally over the looks: z_{alpha / (2 * looks)}.

    bonferroni_boundary(10) == 2.807 (use phi_inv of 1 - alpha / (2 * looks)).
    """
    raise NotImplementedError("TODO milestone 5: bonferroni_boundary")


def pocock_boundary(paths, alpha=0.05):
    """The constant boundary c whose peeking_rate on THESE paths is at most alpha.

    That is the (1 - alpha) quantile of the per-path maximum of |z|: the smallest c such that
    at most a fraction alpha of the paths ever exceed it.

    With 100 paths and alpha = 0.05, the answer is the 95th smallest of the 100 maxima: exactly 5
    paths have a larger maximum. Watch the index (the ceil of (1 - alpha) * E, minus 1 for 0-based;
    wrap the product in round(..., 9) so that 19.000000000000004 does not become 20).
    """
    raise NotImplementedError("TODO milestone 5: pocock_boundary")


# =============================================================================
# Milestone 6: coverage audit and the experiment report
# =============================================================================
def coverage(interval_fn, sampler, truth, E=1000, seed=0):
    """How often does the interval contain the truth? Repeat the experiment E times.

    sampler(rng) draws one fresh sample; interval_fn(sample) returns (lo, hi). Return the
    fraction of the E intervals with lo <= truth <= hi.

    Use one rng = random.Random(seed) for the whole audit and pass it to the sampler every time.
    Example: coverage(lambda s: (min(s), max(s)), lambda rng: [rng.random(), rng.random()], 0.5, 1000)
    is about 0.5, since the range of two uniform draws contains 0.5 half the time.
    """
    raise NotImplementedError("TODO milestone 6: coverage")


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
    Example: ab_report(790, 8000, 864, 8000, 0.012) gives lift +0.00925, z 1.92, p 0.0547, verdict
    "inconclusive", power about 0.70, and n_needed 10,219 per arm.
    """
    raise NotImplementedError("TODO milestone 6: ab_report")
