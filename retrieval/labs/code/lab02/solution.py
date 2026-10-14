"""Lab 2: a retrieval evaluation harness (reference solution).

Judgements and runs in TREC text format -> per-query metrics -> macro means ->
confidence intervals and a paired comparison of two systems.

Notation is chapter 4's: a ranked list becomes a list of GRADES, one per rank
(0 = not relevant or unjudged), and the metrics take that list.

    1  parse_qrels, parse_run, grades_for
    2  precision_at_k, recall_at_k, hit_rate_at_k, reciprocal_rank, average_precision
    3  dcg, ndcg_at_k
    4  evaluate_run, mean
    5  bootstrap_ci
    6  paired_diffs, sign_flip_p, paired_compare
"""
import itertools
import math
import random


# =============================================================================
# Milestone 1: files -> data structures
# =============================================================================
def parse_qrels(text):
    """'qid iteration docid grade' lines -> {qid: {docid: grade}}."""
    qrels = {}
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 4:
            raise ValueError(f"qrels line {n}: expected 4 fields, got {len(parts)}: {line!r}")
        qid, _, docid, grade = parts
        qrels.setdefault(qid, {})[docid] = int(grade)
    return qrels


def parse_run(text):
    """'qid Q0 docid rank score tag' lines -> {qid: [docid, ...]} best first.

    The rank column is ignored: documents are ordered by score (descending), ties by
    docid (ascending). A document listed twice for one query counts once, at its best score.
    """
    scored = {}
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 6:
            raise ValueError(f"run line {n}: expected 6 fields, got {len(parts)}: {line!r}")
        qid, _, docid, _, score, _ = parts
        best = scored.setdefault(qid, {})
        best[docid] = max(float(score), best.get(docid, float("-inf")))
    return {qid: [d for d, _ in sorted(docs.items(), key=lambda kv: (-kv[1], kv[0]))]
            for qid, docs in scored.items()}


def grades_for(ranking, qrel):
    """Grade of each ranked document; unjudged documents count as 0."""
    return [qrel.get(d, 0) for d in ranking]


# =============================================================================
# Milestone 2: binary metrics
# =============================================================================
def precision_at_k(grades, k, thr=1):
    """Relevant results in the first k, divided by k (even if fewer than k were returned)."""
    if k <= 0:
        raise ValueError("k must be positive")
    return sum(g >= thr for g in grades[:k]) / k


def recall_at_k(grades, k, n_relevant, thr=1):
    """Relevant results in the first k, divided by the number of relevant documents."""
    if n_relevant == 0:
        return 0.0
    return sum(g >= thr for g in grades[:k]) / n_relevant


def hit_rate_at_k(grades, k, thr=1):
    """1.0 if any of the first k is relevant, else 0.0."""
    return 1.0 if any(g >= thr for g in grades[:k]) else 0.0


def reciprocal_rank(grades, thr=1):
    """1 / rank of the first relevant result, 0.0 if there is none."""
    for i, g in enumerate(grades, 1):
        if g >= thr:
            return 1.0 / i
    return 0.0


def average_precision(grades, n_relevant, thr=1):
    """Mean of the precision at each relevant rank, over ALL relevant documents."""
    if n_relevant == 0:
        return 0.0
    hits, total = 0, 0.0
    for i, g in enumerate(grades, 1):
        if g >= thr:
            hits += 1
            total += hits / i
    return total / n_relevant          # relevant documents never retrieved add zeros


# =============================================================================
# Milestone 3: graded metrics
# =============================================================================
def dcg(grades, k, exp_gain=False):
    """sum over ranks i = 1..k of gain(g_i) / log2(i + 1); gain is g, or 2**g - 1."""
    gain = (lambda g: 2 ** g - 1) if exp_gain else (lambda g: g)
    return sum(gain(g) / math.log2(i + 1) for i, g in enumerate(grades[:k], 1))


def ndcg_at_k(grades, k, all_grades, exp_gain=False):
    """DCG@k divided by the DCG@k of the ideal order of ALL judged documents' grades."""
    ideal = dcg(sorted(all_grades, reverse=True), k, exp_gain)
    return dcg(grades, k, exp_gain) / ideal if ideal > 0 else 0.0


# =============================================================================
# GIVEN: the standard metric bundle used by the harness
# =============================================================================
def n_rel(all_grades, thr=1):
    return sum(g >= thr for g in all_grades)


def make_metrics(k=10):
    """name -> function(grades, all_grades). Built from YOUR milestone 2 and 3 functions."""
    return {
        f"P@{k}": lambda g, a: precision_at_k(g, k),
        f"R@{k}": lambda g, a: recall_at_k(g, k, n_rel(a)),
        f"MRR@{k}": lambda g, a: reciprocal_rank(g[:k]),
        "MAP": lambda g, a: average_precision(g, n_rel(a)),
        f"nDCG@{k}": lambda g, a: ndcg_at_k(g, k, a),
    }


# =============================================================================
# Milestone 4: scoring a whole run
# =============================================================================
def evaluate_run(run, qrels, metric):
    """{qid: score} for every query that has at least one relevant document in qrels.

    `metric(grades, all_grades)` scores one query. A query missing from the run is scored
    on an empty ranking (all zeros). Queries with no relevant document are left out.
    """
    scores = {}
    for qid, qrel in qrels.items():
        all_grades = list(qrel.values())
        if n_rel(all_grades) == 0:
            continue
        scores[qid] = metric(grades_for(run.get(qid, []), qrel), all_grades)
    return scores


def mean(values):
    """Arithmetic mean of a list or dict's values; 0.0 if empty."""
    vals = list(values.values()) if isinstance(values, dict) else list(values)
    return sum(vals) / len(vals) if vals else 0.0


# =============================================================================
# Milestone 5: an error bar
# =============================================================================
def bootstrap_ci(values, n_boot=2000, alpha=0.05, seed=0):
    """Percentile bootstrap interval for the mean: (low, high).

    Resample `values` with replacement n_boot times (same size), take each resample's mean,
    sort, and return the alpha/2 and 1 - alpha/2 quantiles.
    """
    values = list(values)
    if not values:
        raise ValueError("bootstrap_ci needs at least one value")
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(n_boot))
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot) - 1]
    return lo, hi


# =============================================================================
# Milestone 6: comparing two systems on the same queries
# =============================================================================
def paired_diffs(a, b):
    """(qids, [b - a, ...]) over the queries both dicts score, in sorted qid order."""
    qids = sorted(set(a) & set(b))
    return qids, [b[q] - a[q] for q in qids]


def sign_flip_p(diffs, n_perm=10000, seed=0):
    """Two-sided paired permutation (sign-flip) test p-value for 'the mean difference is 0'.

    Under the null, each paired difference is as likely to be +d as -d. Statistic: |sum|.
    With 12 or fewer differences, enumerate all 2**n sign patterns exactly. Otherwise
    sample n_perm random patterns and return (count + 1) / (n_perm + 1).
    """
    n = len(diffs)
    if n == 0:
        return 1.0
    observed = abs(sum(diffs)) - 1e-12
    if n <= 12:
        hits = sum(abs(sum(s * d for s, d in zip(signs, diffs))) >= observed
                   for signs in itertools.product((1, -1), repeat=n))
        return hits / 2 ** n
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        total = sum(d if rng.random() < 0.5 else -d for d in diffs)
        hits += abs(total) >= observed
    return (hits + 1) / (n_perm + 1)


def paired_compare(a, b, n_boot=2000, n_perm=10000, seed=0, alpha=0.05):
    """Compare system B with system A on the queries both were scored on.

    Returns a dict: n, mean_a, mean_b, diff (mean of b - a), ci (bootstrap interval of the
    mean difference), p (sign-flip p-value) and verdict: "B better" or "A better" if the
    interval excludes 0, else "no clear difference".
    """
    qids, diffs = paired_diffs(a, b)
    if not qids:
        raise ValueError("the two systems share no scored queries")
    lo, hi = bootstrap_ci(diffs, n_boot, alpha, seed)
    verdict = "B better" if lo > 0 else "A better" if hi < 0 else "no clear difference"
    return {"n": len(qids), "mean_a": mean([a[q] for q in qids]), "mean_b": mean([b[q] for q in qids]),
            "diff": mean(diffs), "ci": (lo, hi), "p": sign_flip_p(diffs, n_perm, seed), "verdict": verdict}
