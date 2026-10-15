# Drill: A6 Lab 1, milestone 3 of 5: error bars (step 2 of 4)
# Everything else in this file is already written. Fill in:
#     wilson
# Check it with: python3 check.py 3

"""Lab 1: an eval harness with error bars (reference solution).

Pipeline: cases (data) -> run each case k times -> grade with assertions -> summarise by tag
          -> put intervals on the scores -> compare two systems case by case -> decide.

    1  load_cases, run_check, grade
    2  run_suite, summarise
    3  mean_se, wilson, clustered_se, bootstrap_ci
    4  paired_stats, diff_runs
    5  n_required, mde, verdict, compare

Standard library only.
"""
import json
import math
import random
import re
from dataclasses import dataclass, field
from statistics import NormalDist

# ----------------------------------------------------------------------------- given

_N = NormalDist()
REQUIRED_FIELDS = ("id", "input", "checks")


@dataclass
class Result:
    """What the harness records for one case: one outcome per attempt.

    outcomes: a list of "pass", "fail" or "error", one entry per sample (attempt).
    reasons:  for each sample, the list of failed-check reasons ([] for a pass or an error).
    """
    id: str
    group: str
    tags: list
    outcomes: list
    reasons: list = field(default_factory=list)

    @property
    def score(self):
        """Share of attempts that passed. An error is not a pass: it stays in the denominator."""
        return sum(o == "pass" for o in self.outcomes) / len(self.outcomes)


def z_for(p):
    """Upper-tail normal quantile: z_for(0.025) = 1.96 (given)."""
    return _N.inv_cdf(1 - p)


# ----------------------------------------------------------------------------- milestone 1

def load_cases(text):
    """Parse a JSON Lines string into a list of case dicts.

    One JSON object per non-blank line. Every case needs the REQUIRED_FIELDS, ids must be unique,
    and `checks` must be a non-empty list. Raise ValueError (naming the line or id) otherwise.
    A case without a "group" gets its own id as its group; one without "tags" gets [].
    """
    cases, seen = [], set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"line {lineno}: not valid JSON ({e.msg})")
        if not isinstance(case, dict):
            raise ValueError(f"line {lineno}: each line must be a JSON object")
        for key in REQUIRED_FIELDS:
            if key not in case:
                raise ValueError(f"line {lineno}: missing field {key!r}")
        if case["id"] in seen:
            raise ValueError(f"line {lineno}: duplicate id {case['id']!r}")
        if not isinstance(case["checks"], list) or not case["checks"]:
            raise ValueError(f"line {lineno}: case {case['id']!r} needs at least one check")
        seen.add(case["id"])
        case.setdefault("group", case["id"])
        case.setdefault("tags", [])
        cases.append(case)
    return cases


def _numbers(text):
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*", text)]


def run_check(output, check):
    """Apply ONE assertion to a reply. Return (ok, reason); reason is "" when ok.

    check["type"] is one of:
      contains      value            the text appears in the reply
      not_contains  value            the text does not appear
      not_regex     pattern          re.search finds no match
      json_keys     keys             the reply parses as a JSON object containing all the keys
      number_close  expected, rel_tol   the LAST number in the reply is within rel_tol * |expected|
      max_words     value            len(reply.split()) <= value
    An unknown type raises ValueError (a typo in a case file must not pass silently).
    """
    kind = check["type"]
    if kind == "contains":
        return check["value"] in output, f"missing {check['value']!r}"
    if kind == "not_contains":
        return check["value"] not in output, f"contains forbidden {check['value']!r}"
    if kind == "not_regex":
        return not re.search(check["pattern"], output), f"matches /{check['pattern']}/"
    if kind == "json_keys":
        try:
            data = json.loads(output)
        except ValueError:
            return False, "not valid JSON"
        if not isinstance(data, dict):
            return False, "JSON is not an object"
        missing = [k for k in check["keys"] if k not in data]
        return not missing, f"missing keys {missing}"
    if kind == "number_close":
        nums = _numbers(output)
        if not nums:
            return False, "no number in the reply"
        ok = abs(nums[-1] - check["expected"]) <= check["rel_tol"] * abs(check["expected"])
        return ok, f"last number {nums[-1]:g} is not within {check['rel_tol']:.1%} of {check['expected']:g}"
    if kind == "max_words":
        n = len(output.split())
        return n <= check["value"], f"{n} words > {check['value']}"
    raise ValueError(f"unknown check type {kind!r}")


def grade(output, checks):
    """Run every check. Return the list of failure reasons ([] means the case passed)."""
    reasons = []
    for check in checks:
        ok, why = run_check(output, check)
        if not ok:
            reasons.append(why)
    return reasons


# ----------------------------------------------------------------------------- milestone 2

def run_suite(system, cases, k=1):
    """Run every case k times against `system` and return one Result per case, in order.

    system(case["input"], sample) returns the reply text for attempt number `sample` (0..k-1).
    If the call raises ANY exception, that attempt's outcome is "error" (reasons []): the run
    carries on. A reply that fails a check is "fail"; one that passes them all is "pass".
    """
    results = []
    for case in cases:
        outcomes, reasons = [], []
        for sample in range(k):
            try:
                reply = system(case["input"], sample)
            except Exception:                          # a harness problem, not a verdict
                outcomes.append("error")
                reasons.append([])
                continue
            why = grade(reply, case["checks"])
            outcomes.append("fail" if why else "pass")
            reasons.append(why)
        results.append(Result(case["id"], case.get("group", case["id"]), list(case.get("tags", [])),
                              outcomes, reasons))
    return results


def summarise(results):
    """Roll results up into {"n", "score", "errors", "attempts", "by_tag"}.

    n          number of cases
    score      mean of the per-case scores (errors count as not passing)
    errors     total number of "error" attempts, over all cases
    attempts   total number of attempts
    by_tag     {tag: {"n": cases with the tag, "score": their mean score}}
    """
    scores = [r.score for r in results]
    by_tag = {}
    for r in results:
        for tag in r.tags:
            by_tag.setdefault(tag, []).append(r.score)
    return {
        "n": len(results),
        "score": sum(scores) / len(scores) if scores else 0.0,
        "errors": sum(o == "error" for r in results for o in r.outcomes),
        "attempts": sum(len(r.outcomes) for r in results),
        "by_tag": {t: {"n": len(v), "score": sum(v) / len(v)} for t, v in by_tag.items()},
    }


# ----------------------------------------------------------------------------- milestone 3

def mean_se(xs):
    """Mean and standard error of the mean: (mean, s / sqrt(n)) with s the n-1 standard deviation."""
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(var / n)


def wilson(k, n, z=1.96):
    """Wilson score interval (lo, hi) for k successes in n independent trials."""
    raise NotImplementedError("TODO milestone 3: wilson")


def clustered_se(xs, groups):
    """Standard error of the mean when xs[i] belongs to cluster groups[i].

    Naive variance of the mean plus the covariance between every ordered pair of DIFFERENT items
    in the same cluster (Miller 2024, equation 4):
        SE^2 = SE_naive^2 + (1 / n^2) * sum over clusters, over i != j in the cluster, of (x_i - m)(x_j - m)
    """
    n = len(xs)
    m, se = mean_se(xs)
    members = {}
    for x, g in zip(xs, groups):
        members.setdefault(g, []).append(x - m)
    cross = 0.0
    for devs in members.values():
        total = sum(devs)
        cross += total * total - sum(d * d for d in devs)     # sum over i != j of d_i d_j
    return math.sqrt(max(0.0, se * se + cross / (n * n)))


def bootstrap_ci(values, groups=None, B=2000, alpha=0.05, seed=0):
    """Percentile bootstrap interval (lo, hi) for the mean of `values`.

    Without `groups`, resample the values themselves (with replacement, n draws).
    With `groups` (a list parallel to values), resample WHOLE groups: draw as many groups as there
    are distinct groups, with replacement, and pool all their values. The statistic of each of the
    B pseudo-evals is the mean of the pooled values. Use random.Random(seed).
    Sort the B means; lo = means[int(alpha / 2 * B)], hi = means[int((1 - alpha / 2) * B) - 1].
    """
    rng = random.Random(seed)
    if groups is None:
        n = len(values)
        means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(B))
    else:
        members = {}
        for v, g in zip(values, groups):
            members.setdefault(g, []).append(v)
        packs = [(sum(vs), len(vs)) for vs in members.values()]    # (sum, count) per cluster
        c = len(packs)
        means = []
        for _ in range(B):
            tot = cnt = 0
            for _ in range(c):
                s, m = packs[rng.randrange(c)]
                tot += s
                cnt += m
            means.append(tot / cnt)
        means.sort()
    return means[int(alpha / 2 * B)], means[int((1 - alpha / 2) * B) - 1]


# ----------------------------------------------------------------------------- milestone 4

def paired_stats(a, b):
    """Compare two systems scored on the SAME cases (a[i] and b[i] are case i's scores).

    Return a dict:
      diff         mean of (b - a)
      se_paired    standard error of the per-case differences (the n-1 standard deviation / sqrt(n))
      se_unpaired  sqrt(se_a^2 + se_b^2), treating the two score lists as independent
      z_paired, z_unpaired   diff divided by each standard error (0.0 if the standard error is 0)
      corr         Pearson correlation of a and b (0.0 if either has no spread)
      a_only, b_only   number of cases where a scored higher / b scored higher
    """
    n = len(a)
    d = [y - x for x, y in zip(a, b)]
    diff, se_p = mean_se(d)
    _, se_a = mean_se(a)
    _, se_b = mean_se(b)
    se_u = math.sqrt(se_a ** 2 + se_b ** 2)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return {
        "diff": diff, "se_paired": se_p, "se_unpaired": se_u,
        "z_paired": diff / se_p if se_p else 0.0,
        "z_unpaired": diff / se_u if se_u else 0.0,
        "corr": cov / math.sqrt(va * vb) if va > 0 and vb > 0 else 0.0,
        "a_only": sum(x > y for x, y in zip(a, b)),
        "b_only": sum(y > x for x, y in zip(a, b)),
    }


def diff_runs(res_a, res_b, min_change=0.5):
    """The diff between two runs of the same cases (matched by id, not by position).

    Return {"fixed": [...ids], "regressed": [...ids], "by_tag": {tag: change in mean score}}.
    A case is fixed when b.score - a.score >= min_change, regressed when it is <= -min_change.
    Ids come back sorted. Raise ValueError if the two runs do not cover the same ids.
    """
    A = {r.id: r for r in res_a}
    B = {r.id: r for r in res_b}
    if set(A) != set(B):
        raise ValueError("the two runs cover different cases; compare like with like")
    fixed = sorted(i for i in A if B[i].score - A[i].score >= min_change - 1e-12)
    regressed = sorted(i for i in A if B[i].score - A[i].score <= -min_change + 1e-12)
    tags = {}
    for i in A:
        for t in A[i].tags:
            tags.setdefault(t, []).append(B[i].score - A[i].score)
    return {"fixed": fixed, "regressed": regressed,
            "by_tag": {t: sum(v) / len(v) for t, v in tags.items()}}


# ----------------------------------------------------------------------------- milestone 5

def n_required(delta, omega2, s2a=0.0, s2b=0.0, ka=1, kb=1, alpha=0.05, beta=0.20):
    """Independent questions needed to detect a true gap `delta` (paired design, Miller 2024):
        n = (z_{alpha/2} + z_beta)^2 * (omega2 + s2a/ka + s2b/kb) / delta^2
    Return a float (the caller rounds up)."""
    return (z_for(alpha / 2) + z_for(beta)) ** 2 * (omega2 + s2a / ka + s2b / kb) / delta ** 2


def mde(n, omega2, s2a=0.0, s2b=0.0, ka=1, kb=1, alpha=0.05, beta=0.20):
    """Minimum detectable effect of an eval with n independent questions (the inverse of n_required)."""
    return (z_for(alpha / 2) + z_for(beta)) * math.sqrt((omega2 + s2a / ka + s2b / kb) / n)


def verdict(lo, hi):
    """Read a confidence interval for (B minus A): "B better" if it lies wholly above 0,
    "A better" if wholly below 0, otherwise "cannot tell". An interval touching 0 is "cannot tell"."""
    if lo > 0:
        return "B better"
    if hi < 0:
        return "A better"
    return "cannot tell"


def compare(system_a, system_b, cases, k=3, B=2000, seed=0):
    """The whole pipeline for two systems on the same cases.

    Run both (k attempts per case), then return a dict with:
      score_a, score_b    overall scores
      ci_a, ci_b          cluster-bootstrap 95% intervals for each score (groups = case groups)
      diff                mean of (b - a) per case
      diff_ci             cluster-bootstrap 95% interval of the per-case differences
      z_paired, z_unpaired   from paired_stats
      verdict             verdict(*diff_ci)
      fixed, regressed    from diff_runs
      by_tag              diff_runs' per-tag change
      errors_a, errors_b  error attempts in each run
    """
    res_a = run_suite(system_a, cases, k)
    res_b = run_suite(system_b, cases, k)
    a = [r.score for r in res_a]
    b = [r.score for r in res_b]
    groups = [r.group for r in res_a]
    ps = paired_stats(a, b)
    d = [y - x for x, y in zip(a, b)]
    diff_ci = bootstrap_ci(d, groups, B=B, seed=seed)
    dr = diff_runs(res_a, res_b)
    return {
        "score_a": sum(a) / len(a), "score_b": sum(b) / len(b),
        "ci_a": bootstrap_ci(a, groups, B=B, seed=seed), "ci_b": bootstrap_ci(b, groups, B=B, seed=seed),
        "diff": ps["diff"], "diff_ci": diff_ci,
        "z_paired": ps["z_paired"], "z_unpaired": ps["z_unpaired"],
        "verdict": verdict(*diff_ci),
        "fixed": dr["fixed"], "regressed": dr["regressed"], "by_tag": dr["by_tag"],
        "errors_a": summarise(res_a)["errors"], "errors_b": summarise(res_b)["errors"],
    }
