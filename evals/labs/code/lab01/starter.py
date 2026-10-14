"""Lab 1: an eval harness with error bars (starter: your file).

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
    raise NotImplementedError("TODO milestone 1: load_cases")


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
    raise NotImplementedError("TODO milestone 1: run_check")


def grade(output, checks):
    """Run every check. Return the list of failure reasons ([] means the case passed)."""
    raise NotImplementedError("TODO milestone 1: grade")


# ----------------------------------------------------------------------------- milestone 2

def run_suite(system, cases, k=1):
    """Run every case k times against `system` and return one Result per case, in order.

    system(case["input"], sample) returns the reply text for attempt number `sample` (0..k-1).
    If the call raises ANY exception, that attempt's outcome is "error" (reasons []): the run
    carries on. A reply that fails a check is "fail"; one that passes them all is "pass".
    """
    raise NotImplementedError("TODO milestone 2: run_suite")


def summarise(results):
    """Roll results up into {"n", "score", "errors", "attempts", "by_tag"}.

    n          number of cases
    score      mean of the per-case scores (errors count as not passing)
    errors     total number of "error" attempts, over all cases
    attempts   total number of attempts
    by_tag     {tag: {"n": cases with the tag, "score": their mean score}}
    """
    raise NotImplementedError("TODO milestone 2: summarise")


# ----------------------------------------------------------------------------- milestone 3

def mean_se(xs):
    """Mean and standard error of the mean: (mean, s / sqrt(n)) with s the n-1 standard deviation."""
    raise NotImplementedError("TODO milestone 3: mean_se")


def wilson(k, n, z=1.96):
    """Wilson score interval (lo, hi) for k successes in n independent trials."""
    raise NotImplementedError("TODO milestone 3: wilson")


def clustered_se(xs, groups):
    """Standard error of the mean when xs[i] belongs to cluster groups[i].

    Naive variance of the mean plus the covariance between every ordered pair of DIFFERENT items
    in the same cluster (Miller 2024, equation 4):
        SE^2 = SE_naive^2 + (1 / n^2) * sum over clusters, over i != j in the cluster, of (x_i - m)(x_j - m)
    """
    raise NotImplementedError("TODO milestone 3: clustered_se")


def bootstrap_ci(values, groups=None, B=2000, alpha=0.05, seed=0):
    """Percentile bootstrap interval (lo, hi) for the mean of `values`.

    Without `groups`, resample the values themselves (with replacement, n draws).
    With `groups` (a list parallel to values), resample WHOLE groups: draw as many groups as there
    are distinct groups, with replacement, and pool all their values. The statistic of each of the
    B pseudo-evals is the mean of the pooled values. Use random.Random(seed).
    Sort the B means; lo = means[int(alpha / 2 * B)], hi = means[int((1 - alpha / 2) * B) - 1].
    """
    raise NotImplementedError("TODO milestone 3: bootstrap_ci")


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
    raise NotImplementedError("TODO milestone 4: paired_stats")


def diff_runs(res_a, res_b, min_change=0.5):
    """The diff between two runs of the same cases (matched by id, not by position).

    Return {"fixed": [...ids], "regressed": [...ids], "by_tag": {tag: change in mean score}}.
    A case is fixed when b.score - a.score >= min_change, regressed when it is <= -min_change.
    Ids come back sorted. Raise ValueError if the two runs do not cover the same ids.
    """
    raise NotImplementedError("TODO milestone 4: diff_runs")


# ----------------------------------------------------------------------------- milestone 5

def n_required(delta, omega2, s2a=0.0, s2b=0.0, ka=1, kb=1, alpha=0.05, beta=0.20):
    """Independent questions needed to detect a true gap `delta` (paired design, Miller 2024):
        n = (z_{alpha/2} + z_beta)^2 * (omega2 + s2a/ka + s2b/kb) / delta^2
    Return a float (the caller rounds up)."""
    raise NotImplementedError("TODO milestone 5: n_required")


def mde(n, omega2, s2a=0.0, s2b=0.0, ka=1, kb=1, alpha=0.05, beta=0.20):
    """Minimum detectable effect of an eval with n independent questions (the inverse of n_required)."""
    raise NotImplementedError("TODO milestone 5: mde")


def verdict(lo, hi):
    """Read a confidence interval for (B minus A): "B better" if it lies wholly above 0,
    "A better" if wholly below 0, otherwise "cannot tell". An interval touching 0 is "cannot tell"."""
    raise NotImplementedError("TODO milestone 5: verdict")


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
    raise NotImplementedError("TODO milestone 5: compare")
