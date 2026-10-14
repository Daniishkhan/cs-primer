"""Lab 5: Thresholds & Calibration, your starter.

Conventions (the same as chapters 2 and 15 of this course):

    scores      one number per case; higher means more likely positive. When a function says "probabilities"
                the scores are meant to be honest probabilities in (0, 1).
    y           a list of 0/1 labels (1 = the rare positive class), the same length as scores
    flag        a case is flagged (acted on) when score >= threshold
    c_fp, c_fn  the cost of a false alarm and of a miss; a correct decision costs nothing

Everything is deterministic: every random number comes from a seeded random.Random.

What is GIVEN: sigmoid, logit, roc_auc, the case generator make_cases and the undersampling helper inflate.
What YOU write is marked TODO; each function has a docstring with its contract:

    1  precision_recall_points, average_precision
    2  cost_threshold, expected_cost, best_threshold, threshold_for_recall, threshold_for_capacity
    3  brier_score, log_loss, reliability_table, ece
    4  fit_platt, apply_platt
    5  fit_isotonic, apply_isotonic
    6  correct_undersampling, shift_prior, calibrated_flags

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import math
import random
from bisect import bisect_left

C_FP = 5.0      # a false alarm: an analyst spends ten minutes on a harmless case
C_FN = 100.0    # a miss: the loss we failed to prevent


# =============================================================================
# GIVEN: small maths helpers, the data generator and the scoring-model stand-in
# =============================================================================
def sigmoid(z):
    """The logistic function 1 / (1 + e^-z), safe for large |z|."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-min(z, 700.0)))
    e = math.exp(max(z, -700.0))
    return e / (1.0 + e)


def logit(p, eps=1e-9):
    """log(p / (1 - p)) with p clipped into [eps, 1 - eps] so that 0 and 1 stay finite."""
    p = min(max(p, eps), 1.0 - eps)
    return math.log(p / (1.0 - p))


def roc_auc(scores, y):
    """The probability that a random positive outscores a random negative (ties count one half).

    Computed from average ranks, in O(n log n).
    """
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for t in range(i, j + 1):
            ranks[order[t]] = (i + j) / 2.0 + 1.0
        i = j + 1
    n_pos = sum(y)
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        raise ValueError("roc_auc needs both classes in y")
    return (sum(r for r, t in zip(ranks, y) if t == 1) - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def make_cases(n, seed, stretch=1.0, shift=0.0, base_logit=-4.5, spread=1.6):
    """A synthetic screening problem with a known truth. Returns (scores, y, p_true).

    Each case has a true log-odds z = base_logit + spread * N(0, 1), so its true probability of being
    positive is p_true = sigmoid(z), and its label is drawn with exactly that probability. The model under
    test does not see z perfectly: it reports sigmoid(stretch * z + shift).

        stretch = 1, shift = 0   an honest model: scores are p_true
        stretch > 1              the log-odds are exaggerated, as in an overfitted model. For a rare event, whose
                                 log-odds are mostly very negative, that pushes most scores DOWN (towards 0)
        stretch < 1              the log-odds are shrunk (an underconfident model)
        shift != 0               biased (scores too high if positive)

    Whatever stretch and shift are (with stretch > 0), the ranking is that of p_true, so the AUC is the same;
    only the meaning of the numbers changes. With the defaults, about 3% of cases are positive.
    """
    rng = random.Random(seed)
    z = [base_logit + spread * rng.gauss(0.0, 1.0) for _ in range(n)]
    p_true = [sigmoid(v) for v in z]
    y = [1 if rng.random() < p else 0 for p in p_true]
    scores = [sigmoid(stretch * v + shift) for v in z]
    return scores, y, p_true


def inflate(p, beta):
    """What a model trained on data with a fraction beta of the negatives kept reports when the honest
    probability is p: odds are multiplied by 1/beta. (The inverse of correct_undersampling.)"""
    return p / (p + beta * (1.0 - p))


# =============================================================================
# Milestone 1: the precision-recall curve
# =============================================================================
def precision_recall_points(scores, y):
    """One (threshold, precision, recall) per DISTINCT score, from the highest threshold down.

    The point for threshold t describes the rule "flag every case with score >= t": precision is the share
    of flagged cases that are positive, recall the share of positives that are flagged. Cases with equal
    scores enter together, since no threshold can separate them. Raises ValueError if y has no positives.

        precision_recall_points([0.9, 0.8, 0.7, 0.6], [1, 0, 1, 0])
        -> [(0.9, 1.0, 0.5), (0.8, 0.5, 0.5), (0.7, 0.667, 1.0), (0.6, 0.5, 1.0)]   (rounded)
    """
    raise NotImplementedError("TODO milestone 1: precision_recall_points")


def average_precision(scores, y):
    """Average precision: the sum over curve points of (recall step) x (precision at that point).

        AP = sum_k (R_k - R_{k-1}) * P_k,   with R_0 = 0

    A step function under the precision-recall curve, with no interpolation between points. A perfect
    ranking scores 1.0; a random one scores about the base rate of positives.
    """
    raise NotImplementedError("TODO milestone 1: average_precision")


# =============================================================================
# Milestone 2: choosing a threshold from costs, a recall promise or a capacity
# =============================================================================
def cost_threshold(c_fp, c_fn):
    """The probability above which flagging is cheaper than not flagging: c_fp / (c_fp + c_fn).

    Flagging a case with true probability p costs (1 - p) * c_fp in expectation; leaving it costs p * c_fn.
    Flag when the first is smaller, which is when p > c_fp / (c_fp + c_fn).
    """
    raise NotImplementedError("TODO milestone 2: cost_threshold")


def expected_cost(scores, y, threshold, c_fp, c_fn):
    """Average cost per case of the rule "flag when score >= threshold"."""
    raise NotImplementedError("TODO milestone 2: expected_cost")


def best_threshold(scores, y, c_fp, c_fn):
    """The threshold with the lowest average cost on these cases, and that cost: (threshold, cost).

    Candidates are every distinct score, plus float("inf") for "flag nothing". Among equal costs return the
    HIGHEST threshold (fewest flags). Must run in O(n log n): sort once and sweep, do not call expected_cost
    for every candidate.
    """
    raise NotImplementedError("TODO milestone 2: best_threshold")


def threshold_for_recall(scores, y, target):
    """The HIGHEST threshold whose recall is at least `target` (a promise like "catch 90% of fraud").

    Raises ValueError if target is not in (0, 1].
    """
    raise NotImplementedError("TODO milestone 2: threshold_for_recall")


def threshold_for_capacity(scores, k):
    """The threshold that flags the k highest-scoring cases: the k-th largest score.

    If cases tie at that score, all of them are flagged, so more than k may be (a capacity cannot split a tie).
    """
    raise NotImplementedError("TODO milestone 2: threshold_for_capacity")


# =============================================================================
# Milestone 3: proper scores and the reliability diagram
# =============================================================================
def brier_score(p, y):
    """Mean squared difference between the predicted probability and the 0/1 outcome (lower is better)."""
    raise NotImplementedError("TODO milestone 3: brier_score")


def log_loss(p, y, eps=1e-12):
    """Mean of -log(probability given to what happened). Probabilities are clipped into [eps, 1 - eps]."""
    raise NotImplementedError("TODO milestone 3: log_loss")


def reliability_table(p, y, n_bins=10):
    """The numbers behind a reliability diagram, using equal-width bins of predicted probability.

    Case i goes into bin min(int(p[i] * n_bins), n_bins - 1) (so p = 1.0 joins the last bin). Returns a list
    of (bin_index, count, mean_predicted, observed_rate) for the NON-EMPTY bins, in bin order.
    """
    raise NotImplementedError("TODO milestone 3: reliability_table")


def ece(p, y, n_bins=10):
    """Expected calibration error: the bin-size-weighted average of |mean predicted - observed rate|."""
    raise NotImplementedError("TODO milestone 3: ece")


# =============================================================================
# Milestone 4: Platt scaling
# =============================================================================
def fit_platt(scores, y, iters=100):
    """Fit P(y = 1 | score) = sigmoid(a * logit(score) + b) by maximum likelihood. Returns (a, b).

    Newton's method (iteratively reweighted least squares) on the two parameters. With z = logit(score) and
    p = sigmoid(a z + b), the gradient is (sum (p - y) z, sum (p - y)) and the Hessian is
    [[sum w z^2, sum w z], [sum w z, sum w]] with w = p (1 - p). Start from a = 0 and b = logit(base rate),
    the best constant model: a start at (1, 0) can sit where every w is tiny and the first step is enormous.
    Halve a step that does not lower the log loss. Stop when the step is below 1e-10.
    """
    raise NotImplementedError("TODO milestone 4: fit_platt")


def apply_platt(params, scores):
    """Calibrated probabilities sigmoid(a * logit(score) + b) for each score."""
    raise NotImplementedError("TODO milestone 4: apply_platt")


# =============================================================================
# Milestone 5: isotonic regression by pool-adjacent-violators
# =============================================================================
def fit_isotonic(scores, y):
    """The best non-decreasing step function through the (score, label) pairs, by least squares.

    Returns (xs, vals): block i covers the scores greater than xs[i-1] and up to xs[i], and its value is
    vals[i], the mean label in the block. xs is strictly increasing and vals strictly increasing.

    Pool adjacent violators: sort by score, put equal scores together first (no function can separate
    them), then push groups one at a time onto a stack of blocks; while the top block's mean is not above the
    one beneath it, merge the two.
    """
    raise NotImplementedError("TODO milestone 5: fit_isotonic")


def apply_isotonic(model, scores):
    """Value of the block containing each score: the first block whose upper edge xs[i] is >= the score.

    Scores above every edge get the last block's value.
    """
    raise NotImplementedError("TODO milestone 5: apply_isotonic")


# =============================================================================
# Milestone 6: undersampling, prior shift and the whole decision pipeline
# =============================================================================
def correct_undersampling(ps, beta):
    """Undo training on a sample that kept a fraction beta of the negatives (and all positives).

    p = beta * ps / (beta * ps - ps + 1)    (Dal Pozzolo et al., 2015; chapter 15)
    """
    raise NotImplementedError("TODO milestone 6: correct_undersampling")


def shift_prior(p, train_rate, new_rate):
    """Rescale a probability when the positive rate moves from train_rate to new_rate (label shift).

    Multiply the odds p / (1 - p) by [new_rate / (1 - new_rate)] / [train_rate / (1 - train_rate)].
    """
    raise NotImplementedError("TODO milestone 6: shift_prior")


def calibrated_flags(cal_scores, cal_y, test_scores, c_fp, c_fn, method):
    """The whole pipeline: recalibrate on held-out data, then apply the cost rule. Returns 0/1 flags.

    method is "none" (use test_scores as they are), "platt" or "isotonic": fit on (cal_scores, cal_y), apply to
    test_scores. Flag a test case when its probability is at least cost_threshold(c_fp, c_fn).
    """
    raise NotImplementedError("TODO milestone 6: calibrated_flags")
