"""Lab 6: Automated canary analysis.

One process, no network, no clock. Every metric sample is drawn from a seeded
random.Random, so the same seed gives the same deploy and the same verdict.

The vocabulary is chapter 12 of this course (and chapter 4 for percentiles):

    baseline     a few fresh instances of the OLD version, started with the canary
    canary       a few instances of the NEW version
    judge        a program that compares canary metrics with baseline metrics and
                 returns promote or roll back
    effect size  how big a difference is (not just whether it is real)

    1  gen_latency, gen_errors, gen_memory, generate
    2  ranks_with_ties, mann_whitney_u
    3  median, effect_size, classify
    4  judge, score, decide, rollback_rate
    5  rollout, compare_baselines

What is GIVEN: the daily load curve, the metric table, the policy and the wave
definitions. What YOU write is marked TODO. `python3 check.py` runs the
milestones; the lab page explains each one.
"""
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# =============================================================================
# GIVEN: metrics, regressions, the policy, the daily load curve
# =============================================================================
@dataclass(frozen=True)
class Metric:
    name: str
    direction: str       # "lower" = lower is better (latency, errors); "higher" = higher is better
    weight: float
    critical: bool       # a critical metric that goes the wrong way fails the canary by itself
    min_effect: float    # relative change below which a difference is ignored, however significant
    floor: float         # smallest baseline value used as the denominator of the effect size


METRICS = [
    Metric("latency_ms", "lower", 3.0, True, 0.10, 1.0),
    Metric("error_rate", "lower", 3.0, True, 0.50, 1e-4),
    Metric("memory_mb", "lower", 1.0, False, 0.03, 1.0),
]
METRIC_BY_NAME = {m.name: m for m in METRICS}


@dataclass(frozen=True)
class Regression:
    """What is wrong with the new build (all zero = a healthy build)."""
    latency: float = 0.0     # relative shift of the typical latency: 0.2 = 20% slower
    errors: float = 0.0      # extra error probability per request: 0.002 = +0.2 points
    leak: float = 0.0        # memory growth in MB per minute


@dataclass(frozen=True)
class Policy:
    alpha: float = 0.01      # significance level for the rank-sum test
    pass_score: float = 90.0 # promote only if the weighted score is at least this


BASE_LATENCY_MS = 100.0
LATENCY_SIGMA = 0.3          # lognormal spread of the per-instance-minute latency
BASE_ERROR = 0.001           # 0.1% of requests fail
REQUESTS_PER_SAMPLE = 2000   # requests behind one instance-minute error rate
BASE_MEMORY_MB = 800.0
MEMORY_NOISE_MB = 15.0


def day_load(hour: float) -> float:
    """The daily traffic pattern: 1.0 on average, 1.5 at 15:00 and 0.5 at 03:00."""
    return 1.0 + 0.5 * math.sin(2.0 * math.pi * (hour - 9.0) / 24.0)


def latency_factor(load: float) -> float:
    """Busier means slower: 60% of the load change shows up in latency."""
    return 1.0 + 0.6 * (load - 1.0)


# =============================================================================
# 1. Seeded metric samples
# =============================================================================
def gen_latency(rng: random.Random, n: int, shift: float = 0.0, load: float = 1.0) -> List[float]:
    """n latency samples in ms (one per instance-minute): lognormal with median
    BASE_LATENCY_MS * (1 + shift) * latency_factor(load) and log-spread LATENCY_SIGMA.
    Use rng.lognormvariate(mu, sigma) with mu = log(median)."""
    median = BASE_LATENCY_MS * (1.0 + shift) * latency_factor(load)
    return [rng.lognormvariate(math.log(median), LATENCY_SIGMA) for _ in range(n)]


def gen_errors(rng: random.Random, n: int, extra: float = 0.0, load: float = 1.0) -> List[float]:
    """n error-rate samples (fraction of failed requests in one instance-minute).
    The true probability is p = (BASE_ERROR + extra) * load; the sample is the
    fraction of REQUESTS_PER_SAMPLE requests that failed, which for this many
    requests is well approximated by rng.gauss(p, sqrt(p * (1 - p) / REQUESTS_PER_SAMPLE)).
    A rate cannot be negative: clip at 0."""
    p = (BASE_ERROR + extra) * load
    sd = math.sqrt(p * (1.0 - p) / REQUESTS_PER_SAMPLE)
    return [max(0.0, rng.gauss(p, sd)) for _ in range(n)]


def gen_memory(rng: random.Random, minutes: int, instances: int, leak: float = 0.0) -> List[float]:
    """Memory samples (MB), ordered by minute: for minute m = 0 .. minutes-1, one
    sample per instance: BASE_MEMORY_MB + leak * m + rng.gauss(0, MEMORY_NOISE_MB).
    A leak shows up as a slope, so the same window can hide it (short) or expose it (long)."""
    return [BASE_MEMORY_MB + leak * m + rng.gauss(0.0, MEMORY_NOISE_MB) for m in range(minutes) for _ in range(instances)]


def generate(rng: random.Random, reg: Regression, minutes: int = 30, instances: int = 3,
             load: float = 1.0, baseline_load: Optional[float] = None) -> Dict[str, Tuple[List[float], List[float]]]:
    """Samples for one analysis window: {metric name: (baseline samples, canary samples)}.
    n = minutes * instances per group. The baseline runs the old build (a healthy
    Regression) at `baseline_load` (default: the same load as the canary); the canary
    has the regression. Draw the baseline first, then the canary, from the one rng."""
    n = minutes * instances
    bl = load if baseline_load is None else baseline_load
    return {
        "latency_ms": (gen_latency(rng, n, 0.0, bl), gen_latency(rng, n, reg.latency, load)),
        "error_rate": (gen_errors(rng, n, 0.0, bl), gen_errors(rng, n, reg.errors, load)),
        "memory_mb": (gen_memory(rng, minutes, instances, 0.0), gen_memory(rng, minutes, instances, reg.leak)),
    }


# =============================================================================
# 2. The Mann-Whitney U test
# =============================================================================
def ranks_with_ties(values: List[float]) -> Tuple[List[float], List[int]]:
    """Return (ranks, tie_sizes). ranks[i] is the 1-based rank of values[i] in the
    sorted order; values that are equal share the AVERAGE of the ranks they occupy
    (three values tied for ranks 4, 5, 6 all get 5.0). tie_sizes lists the size of
    every group of equal values (singletons are size 1)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    ties = []
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        ties.append(j - i + 1)
        i = j + 1
    return ranks, ties


def mann_whitney_u(x: List[float], y: List[float]) -> Tuple[float, float, float]:
    """Two-sided Mann-Whitney U test with a normal approximation. Returns (u, z, p):

      u  the U statistic of x: R_x - n_x (n_x + 1) / 2, where R_x is the sum of x's ranks
         in the pooled sample. (It counts the pairs (a, b) with a > b, ties as half.)
      z  (u - mean - cc) / sd  with mean = n_x n_y / 2 and the continuity correction
         cc = +0.5 if u > mean, -0.5 if u < mean, 0 if u == mean. The variance with the
         tie correction is
             sd^2 = n_x n_y / 12 * ( (N + 1) - sum(t^3 - t) / (N (N - 1)) ),   N = n_x + n_y
         where t runs over the tie group sizes.
      p  the two-sided p-value: math.erfc(|z| / sqrt(2)).

    z > 0 means x tends to be larger than y. If every value is equal (sd = 0),
    return z = 0 and p = 1."""
    nx, ny = len(x), len(y)
    ranks, ties = ranks_with_ties(list(x) + list(y))
    u = sum(ranks[:nx]) - nx * (nx + 1) / 2.0
    n = nx + ny
    mean = nx * ny / 2.0
    var = nx * ny / 12.0 * ((n + 1) - sum(t ** 3 - t for t in ties) / (n * (n - 1)))
    if var <= 0.0:
        return u, 0.0, 1.0
    diff = u - mean
    cc = 0.5 if diff > 0 else (-0.5 if diff < 0 else 0.0)
    z = (diff - cc) / math.sqrt(var)
    return u, z, math.erfc(abs(z) / math.sqrt(2.0))


# =============================================================================
# 3. Per-metric classification with an effect size
# =============================================================================
def median(xs: List[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def effect_size(baseline: List[float], canary: List[float], floor: float) -> float:
    """Relative change of the median: (median(canary) - median(baseline)) /
    max(|median(baseline)|, floor). +0.2 means the canary's typical value is 20% higher."""
    mb = median(baseline)
    return (median(canary) - mb) / max(abs(mb), floor)


def classify(baseline: List[float], canary: List[float], alpha: float, min_effect: float, floor: float = 1e-9) -> str:
    """"high" if the canary is significantly higher than the baseline, "low" if it is
    significantly lower, "pass" otherwise. A difference counts only if BOTH hold:
    the rank-sum test gives p < alpha, and |effect_size| >= min_effect."""
    _, z, p = mann_whitney_u(canary, baseline)
    eff = effect_size(baseline, canary, floor)
    if p < alpha and abs(eff) >= min_effect:
        return "high" if z > 0 else "low"
    return "pass"


# =============================================================================
# 4. Score, decision, and how often the decision is wrong
# =============================================================================
def is_bad(label: str, metric: Metric) -> bool:
    """A change is bad if it moves against the metric's direction."""
    return (label == "high" and metric.direction == "lower") or (label == "low" and metric.direction == "higher")


def judge(data: Dict[str, Tuple[List[float], List[float]]], policy: Policy, metrics: List[Metric] = METRICS) -> Dict[str, str]:
    """Classify every metric: {name: "pass" | "high" | "low"}, using each metric's
    own min_effect and floor and the policy's alpha."""
    out = {}
    for m in metrics:
        base, canary = data[m.name]
        out[m.name] = classify(base, canary, policy.alpha, m.min_effect, m.floor)
    return out


def score(labels: Dict[str, str], metrics: List[Metric] = METRICS) -> float:
    """0-100: the share of total weight carried by metrics that are NOT bad."""
    total = sum(m.weight for m in metrics)
    good = sum(m.weight for m in metrics if not is_bad(labels[m.name], m))
    return 100.0 * good / total


def decide(data, policy: Policy, metrics: List[Metric] = METRICS) -> Tuple[bool, float, Dict[str, str]]:
    """Return (promote, score, labels). Promote only if score >= policy.pass_score
    AND no critical metric is bad."""
    labels = judge(data, policy, metrics)
    sc = score(labels, metrics)
    critical_bad = any(m.critical and is_bad(labels[m.name], m) for m in metrics)
    return (sc >= policy.pass_score and not critical_bad), sc, labels


def rollback_rate(reg: Regression, n_deploys: int, seed: int, policy: Policy = Policy(),
                  minutes: int = 30, instances: int = 3, metrics: List[Metric] = METRICS) -> float:
    """The fraction of n_deploys simulated deploys with regression `reg` that the
    judge rolls back. Deploy i uses random.Random(seed * 100003 + i) and generate().
    For a healthy build this is the false-rollback rate; for a bad build one minus
    it is the missed-regression rate."""
    rolled = 0
    for i in range(n_deploys):
        rng = random.Random(seed * 100003 + i)
        promote, _, _ = decide(generate(rng, reg, minutes, instances), policy, metrics)
        rolled += 0 if promote else 1
    return rolled / n_deploys


# =============================================================================
# 5. A multi-wave rollout, and what to compare against
# =============================================================================
@dataclass(frozen=True)
class Wave:
    fraction: float      # share of the fleet running the new build in this wave
    instances: int       # canary instances (and as many baseline instances) analysed
    bake_minutes: int


WAVES = [Wave(0.015, 3, 30), Wave(0.05, 6, 30), Wave(0.25, 12, 30), Wave(1.0, 12, 30)]


@dataclass
class Rollout:
    promoted: bool
    halted_at: Optional[int]      # index of the wave whose analysis failed, else None
    exposure: float               # largest share of the fleet that ran the new build
    waves_judged: int


def yesterday_baseline(rng: random.Random, n: int) -> Dict[str, List[float]]:
    """GIVEN. The 'compare with yesterday' reference: n samples per metric drawn from
    the old build over the whole previous day (each sample at a random hour of the
    day's traffic curve), as a dashboard that shows 'last 24 hours' would."""
    lat, err = [], []
    for _ in range(n):
        load = day_load(rng.uniform(0.0, 24.0))
        lat.append(gen_latency(rng, 1, 0.0, load)[0])
        err.append(gen_errors(rng, 1, 0.0, load)[0])
    return {"latency_ms": lat, "error_rate": err}


def rollout(rng: random.Random, reg: Regression, start_hour: float, baseline: str, policy: Policy = Policy(),
            waves: List[Wave] = WAVES) -> Rollout:
    """Roll a build out in waves, starting at `start_hour` (0-24, may exceed 24).

    For each wave in order, at the wave's own time of day (the hour at the middle of
    its bake: start_hour + elapsed minutes / 60 + bake / 120, where elapsed is the sum
    of the earlier bakes), take the traffic load day_load(hour % 24) and generate()
    one window of w.bake_minutes x w.instances. Then judge it:

      baseline == "concurrent":  compare the canary with the baseline instances in
                                 the window (as generated: same time, same load).
      baseline == "yesterday":   replace the baseline of latency_ms and error_rate by
                                 yesterday_baseline(rng, n) (n = samples in the window);
                                 memory keeps its concurrent baseline.

    Use decide(). If the verdict is to roll back, HALT: stop rolling out, return
    Rollout(promoted=False, halted_at=<wave index>, exposure=<that wave's fraction>,
    waves_judged=<waves analysed so far>). If every wave passes, return promoted=True
    with exposure 1.0 (the whole fleet) and halted_at None."""
    elapsed = 0
    exposure = 0.0
    for i, w in enumerate(waves):
        hour = (start_hour + elapsed / 60.0 + w.bake_minutes / 120.0) % 24.0
        load = day_load(hour)
        data = generate(rng, reg, w.bake_minutes, w.instances, load)
        if baseline == "yesterday":
            ref = yesterday_baseline(rng, w.bake_minutes * w.instances)
            data = dict(data)
            for name, base in ref.items():
                data[name] = (base, data[name][1])
        exposure = max(exposure, w.fraction)
        promote, _, _ = decide(data, policy)
        if not promote:
            return Rollout(False, i, w.fraction, i + 1)
        elapsed += w.bake_minutes
    return Rollout(True, None, 1.0, len(waves))


def compare_baselines(n_deploys: int, seed: int, bad: Regression = Regression(latency=0.20),
                      policy: Policy = Policy()) -> Dict[str, Dict[str, float]]:
    """For each baseline mode ("concurrent", "yesterday"), run n_deploys healthy and
    n_deploys bad rollouts. Deploy i starts at hour random.Random(seed*100003 + i).uniform(0, 24)
    (the same hour for its healthy and its bad rollout); the healthy rollout uses
    rng = random.Random(seed*100003 + i + 50000), the bad one random.Random(seed*100003 + i + 90000).
    Return

        {mode: {"false_rollback": share of healthy deploys halted,
                "missed": share of bad deploys promoted,
                "exposure": mean fleet share exposed to a bad build}}"""
    out = {}
    for mode in ("concurrent", "yesterday"):
        halted = missed = 0
        exposure = 0.0
        for i in range(n_deploys):
            hour = random.Random(seed * 100003 + i).uniform(0.0, 24.0)
            good = rollout(random.Random(seed * 100003 + i + 50000), Regression(), hour, mode, policy)
            halted += 0 if good.promoted else 1
            badr = rollout(random.Random(seed * 100003 + i + 90000), bad, hour, mode, policy)
            missed += 1 if badr.promoted else 0
            exposure += badr.exposure
        out[mode] = {"false_rollback": halted / n_deploys, "missed": missed / n_deploys, "exposure": exposure / n_deploys}
    return out
