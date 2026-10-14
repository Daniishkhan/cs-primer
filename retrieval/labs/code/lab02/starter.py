"""Lab 2: a retrieval evaluation harness.

Judgements and runs in TREC text format -> per-query metrics -> macro means ->
confidence intervals and a paired comparison of two systems.

Notation is chapter 4's: a ranked list becomes a list of GRADES, one per rank
(0 = not relevant or unjudged), and the metrics take that list.

    qrels   {qid: {docid: grade}}      what the judges said (grade 0 to 3)
    run     {qid: [docid, ...]}        what a system returned, best first
    scores  {qid: float}               one metric, one number per query

What is GIVEN: `n_rel` and `make_metrics` (they use YOUR metric functions).
What YOU write is marked TODO:

    1  parse_qrels, parse_run, grades_for
    2  precision_at_k, recall_at_k, hit_rate_at_k, reciprocal_rank, average_precision
    3  dcg, ndcg_at_k
    4  evaluate_run, mean
    5  bootstrap_ci
    6  paired_diffs, sign_flip_p, paired_compare

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import itertools   # noqa: F401  (milestone 6: itertools.product enumerates sign patterns)
import math        # noqa: F401
import random      # noqa: F401


# =============================================================================
# Milestone 1: files -> data structures
# =============================================================================
def parse_qrels(text):
    """'qid iteration docid grade' lines -> {qid: {docid: grade}}.

    Blank lines and lines starting with '#' are skipped. Grades are ints. A line that does
    not have exactly 4 whitespace-separated fields raises ValueError naming the line number
    (counting from 1, including skipped lines).

        parse_qrels("q1 0 dA 2\\nq1 0 dB 0\\nq2 0 dC 1\\n")
        -> {'q1': {'dA': 2, 'dB': 0}, 'q2': {'dC': 1}}
    """
    raise NotImplementedError("TODO milestone 1: parse_qrels")


def parse_run(text):
    """'qid Q0 docid rank score tag' lines -> {qid: [docid, ...]} best first.

    Skip blank and '#' lines; exactly 6 fields or ValueError with the line number.
    IGNORE the rank column (the file is not in rank order). Order each query's documents by
    score descending, ties by docid ascending. A document listed twice for one query counts
    once, at its best score.
    """
    raise NotImplementedError("TODO milestone 1: parse_run")


def grades_for(ranking, qrel):
    """The grade of each ranked document, looked up in `qrel` ({docid: grade}).

    A document the judges never saw (not in qrel) counts as 0.
    """
    raise NotImplementedError("TODO milestone 1: grades_for")


# =============================================================================
# Milestone 2: binary metrics.  A result is relevant if its grade >= thr (default 1).
# =============================================================================
def precision_at_k(grades, k, thr=1):
    """Relevant results among the first k, divided by k.

    Divide by k even if fewer than k results were returned. k <= 0 raises ValueError.
    """
    raise NotImplementedError("TODO milestone 2: precision_at_k")


def recall_at_k(grades, k, n_relevant, thr=1):
    """Relevant results among the first k, divided by n_relevant (0.0 if n_relevant is 0)."""
    raise NotImplementedError("TODO milestone 2: recall_at_k")


def hit_rate_at_k(grades, k, thr=1):
    """1.0 if any of the first k results is relevant, else 0.0."""
    raise NotImplementedError("TODO milestone 2: hit_rate_at_k")


def reciprocal_rank(grades, thr=1):
    """1 / (rank of the first relevant result), or 0.0 if there is none."""
    raise NotImplementedError("TODO milestone 2: reciprocal_rank")


def average_precision(grades, n_relevant, thr=1):
    """Mean, over ALL n_relevant relevant documents, of the precision at each relevant rank.

    Walk down the list; at every relevant result record (relevant so far) / (rank). Sum and
    divide by n_relevant, so relevant documents never retrieved count as zeros.
    Return 0.0 when n_relevant is 0.
    """
    raise NotImplementedError("TODO milestone 2: average_precision")


# =============================================================================
# Milestone 3: graded metrics
# =============================================================================
def dcg(grades, k, exp_gain=False):
    """Sum over ranks i = 1..k of gain(grade_i) / log2(i + 1).

    gain is the grade itself, or 2**grade - 1 when exp_gain is True.
    """
    raise NotImplementedError("TODO milestone 3: dcg")


def ndcg_at_k(grades, k, all_grades, exp_gain=False):
    """DCG@k divided by the DCG@k of the ideal ordering.

    `all_grades` holds the grades of EVERY judged document for the query (retrieved or
    not); the ideal ordering sorts them highest first. Return 0.0 when the ideal DCG is 0.
    """
    raise NotImplementedError("TODO milestone 3: ndcg_at_k")


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

    `metric(grades, all_grades)` scores one query: `grades` is grades_for(run's ranking,
    that query's qrel) and `all_grades` is list(qrel.values()). Rules:
      * a query in qrels but missing from the run is scored on an empty ranking;
      * a query with no relevant document (n_rel(all_grades) == 0) is left out;
      * a query in the run but not in qrels is ignored.
    """
    raise NotImplementedError("TODO milestone 4: evaluate_run")


def mean(values):
    """Arithmetic mean of a list, or of a dict's values; 0.0 if empty."""
    raise NotImplementedError("TODO milestone 4: mean")


# =============================================================================
# Milestone 5: an error bar
# =============================================================================
def bootstrap_ci(values, n_boot=2000, alpha=0.05, seed=0):
    """Percentile bootstrap interval for the mean of `values`: (low, high).

    Make a random.Random(seed). Do n_boot times: draw len(values) values WITH replacement
    (rng.choices(values, k=n)) and take their mean. Sort the means and return the
    alpha/2 and 1 - alpha/2 quantiles: means[int(alpha / 2 * n_boot)] and
    means[int((1 - alpha / 2) * n_boot) - 1]. Empty `values` raises ValueError.
    """
    raise NotImplementedError("TODO milestone 5: bootstrap_ci")


# =============================================================================
# Milestone 6: comparing two systems on the same queries
# =============================================================================
def paired_diffs(a, b):
    """(qids, [b - a, ...]) over the queries that BOTH score dicts contain, sorted by qid."""
    raise NotImplementedError("TODO milestone 6: paired_diffs")


def sign_flip_p(diffs, n_perm=10000, seed=0):
    """Two-sided paired permutation (sign-flip) test of 'the mean difference is 0'.

    Statistic: abs(sum(diffs)). Under the null each difference is as likely to be +d as -d.
      * 12 or fewer differences: enumerate all 2**n sign patterns (itertools.product) and
        return (patterns with abs(sum) >= observed) / 2**n.
      * more: draw n_perm random sign patterns with random.Random(seed) and return
        (count + 1) / (n_perm + 1).
    Compare with a tiny tolerance (abs(sum(diffs)) - 1e-12) so equal sums count as equal.
    No differences at all: return 1.0.
    """
    raise NotImplementedError("TODO milestone 6: sign_flip_p")


def paired_compare(a, b, n_boot=2000, n_perm=10000, seed=0, alpha=0.05):
    """Compare system B with system A on the queries both were scored on.

    Return a dict with keys:
      n        number of shared queries
      mean_a, mean_b   their means over the shared queries
      diff     mean of (b - a)
      ci       (low, high) bootstrap interval of the mean difference
      p        sign-flip p-value
      verdict  "B better" if ci is entirely above 0, "A better" if entirely below,
               else "no clear difference"
    No shared queries raises ValueError.
    """
    raise NotImplementedError("TODO milestone 6: paired_compare")
