"""Lab 5: Thresholds & Calibration, the reference solution.

Conventions (the same as chapters 2 and 15 of this course):

    scores      one number per case; higher means more likely positive. When a function says "probabilities"
                the scores are meant to be honest probabilities in (0, 1).
    y           a list of 0/1 labels (1 = the rare positive class), the same length as scores
    flag        a case is flagged (acted on) when score >= threshold
    c_fp, c_fn  the cost of a false alarm and of a miss; a correct decision costs nothing

Everything is deterministic: every random number comes from a seeded random.Random.

What is GIVEN: sigmoid, logit, roc_auc, the case generator make_cases and the undersampling helper inflate.
What YOU write is marked TODO (the reference solution below fills them all in):

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
    n_pos = sum(y)
    if n_pos == 0:
        raise ValueError("precision_recall_points needs at least one positive in y")
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    points = []
    tp = flagged = 0
    i = 0
    while i < len(order):
        t = scores[order[i]]
        while i < len(order) and scores[order[i]] == t:    # take the whole tie group
            tp += y[order[i]]
            flagged += 1
            i += 1
        points.append((t, tp / flagged, tp / n_pos))
    return points


def average_precision(scores, y):
    """Average precision: the sum over curve points of (recall step) x (precision at that point).

        AP = sum_k (R_k - R_{k-1}) * P_k,   with R_0 = 0

    A step function under the precision-recall curve, with no interpolation between points. A perfect
    ranking scores 1.0; a random one scores about the base rate of positives.
    """
    ap, prev_recall = 0.0, 0.0
    for _, precision, recall in precision_recall_points(scores, y):
        ap += (recall - prev_recall) * precision
        prev_recall = recall
    return ap


# =============================================================================
# Milestone 2: choosing a threshold from costs, a recall promise or a capacity
# =============================================================================
def cost_threshold(c_fp, c_fn):
    """The probability above which flagging is cheaper than not flagging: c_fp / (c_fp + c_fn).

    Flagging a case with true probability p costs (1 - p) * c_fp in expectation; leaving it costs p * c_fn.
    Flag when the first is smaller, which is when p > c_fp / (c_fp + c_fn).
    """
    return c_fp / (c_fp + c_fn)


def expected_cost(scores, y, threshold, c_fp, c_fn):
    """Average cost per case of the rule "flag when score >= threshold"."""
    cost = 0.0
    for s, t in zip(scores, y):
        if s >= threshold:
            if t == 0:
                cost += c_fp
        elif t == 1:
            cost += c_fn
    return cost / len(scores)


def best_threshold(scores, y, c_fp, c_fn):
    """The threshold with the lowest average cost on these cases, and that cost: (threshold, cost).

    Candidates are every distinct score, plus float("inf") for "flag nothing". Among equal costs return the
    HIGHEST threshold (fewest flags). Must run in O(n log n): sort once and sweep, do not call expected_cost
    for every candidate.
    """
    n = len(scores)
    n_pos = sum(y)
    best_t, best_cost = float("inf"), n_pos * c_fn / n
    order = sorted(range(n), key=lambda i: -scores[i])
    tp = fp = 0
    i = 0
    while i < n:
        t = scores[order[i]]
        while i < n and scores[order[i]] == t:
            if y[order[i]] == 1:
                tp += 1
            else:
                fp += 1
            i += 1
        cost = (fp * c_fp + (n_pos - tp) * c_fn) / n
        if cost < best_cost:               # strict: an equal cost at a lower threshold flags more, so keep the higher
            best_t, best_cost = t, cost
    return best_t, best_cost


def threshold_for_recall(scores, y, target):
    """The HIGHEST threshold whose recall is at least `target` (a promise like "catch 90% of fraud").

    Raises ValueError if target is not in (0, 1].
    """
    if not 0.0 < target <= 1.0:
        raise ValueError("target recall must be in (0, 1]")
    for t, _, recall in precision_recall_points(scores, y):
        if recall >= target - 1e-12:
            return t
    raise ValueError("unreachable: the lowest threshold has recall 1")


def threshold_for_capacity(scores, k):
    """The threshold that flags the k highest-scoring cases: the k-th largest score.

    If cases tie at that score, all of them are flagged, so more than k may be (a capacity cannot split a tie).
    """
    if not 1 <= k <= len(scores):
        raise ValueError("k must be between 1 and the number of cases")
    return sorted(scores, reverse=True)[k - 1]


# =============================================================================
# Milestone 3: proper scores and the reliability diagram
# =============================================================================
def brier_score(p, y):
    """Mean squared difference between the predicted probability and the 0/1 outcome (lower is better)."""
    return sum((a - t) ** 2 for a, t in zip(p, y)) / len(p)


def log_loss(p, y, eps=1e-12):
    """Mean of -log(probability given to what happened). Probabilities are clipped into [eps, 1 - eps]."""
    total = 0.0
    for a, t in zip(p, y):
        a = min(max(a, eps), 1.0 - eps)
        total -= math.log(a) if t == 1 else math.log(1.0 - a)
    return total / len(p)


def reliability_table(p, y, n_bins=10):
    """The numbers behind a reliability diagram, using equal-width bins of predicted probability.

    Case i goes into bin min(int(p[i] * n_bins), n_bins - 1) (so p = 1.0 joins the last bin). Returns a list
    of (bin_index, count, mean_predicted, observed_rate) for the NON-EMPTY bins, in bin order.
    """
    count = [0] * n_bins
    sum_p = [0.0] * n_bins
    sum_y = [0] * n_bins
    for a, t in zip(p, y):
        b = min(int(a * n_bins), n_bins - 1)
        count[b] += 1
        sum_p[b] += a
        sum_y[b] += t
    return [(b, count[b], sum_p[b] / count[b], sum_y[b] / count[b]) for b in range(n_bins) if count[b]]


def ece(p, y, n_bins=10):
    """Expected calibration error: the bin-size-weighted average of |mean predicted - observed rate|."""
    n = len(p)
    return sum(c / n * abs(mp - rate) for _, c, mp, rate in reliability_table(p, y, n_bins))


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
    z = [logit(s) for s in scores]
    n = len(z)

    def loss(a, b):
        return sum(math.log1p(math.exp(-abs(a * zi + b))) + max(a * zi + b, 0.0) - t * (a * zi + b)
                   for zi, t in zip(z, y)) / n

    a, b = 0.0, logit(sum(y) / n)
    for _ in range(iters):
        ga = gb = haa = hab = hbb = 0.0
        for zi, t in zip(z, y):
            p = sigmoid(a * zi + b)
            e = p - t
            w = max(p * (1.0 - p), 1e-12)
            ga += e * zi
            gb += e
            haa += w * zi * zi
            hab += w * zi
            hbb += w
        det = haa * hbb - hab * hab
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        step, base = 1.0, loss(a, b)
        while step > 1e-6 and loss(a - step * da, b - step * db) > base + 1e-15:
            step /= 2.0
        a, b = a - step * da, b - step * db
        if abs(step * da) < 1e-10 and abs(step * db) < 1e-10:
            break
    return a, b


def apply_platt(params, scores):
    """Calibrated probabilities sigmoid(a * logit(score) + b) for each score."""
    a, b = params
    return [sigmoid(a * logit(s) + b) for s in scores]


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
    pairs = sorted(zip(scores, y))
    groups = []                                     # [x, sum of labels, count], one per distinct score
    for s, t in pairs:
        if groups and groups[-1][0] == s:
            groups[-1][1] += t
            groups[-1][2] += 1
        else:
            groups.append([s, t, 1])
    blocks = []                                     # [x_max, sum, count]
    for g in groups:
        blocks.append(g)
        while len(blocks) > 1 and blocks[-2][1] / blocks[-2][2] >= blocks[-1][1] / blocks[-1][2]:
            top = blocks.pop()
            blocks[-1] = [top[0], blocks[-1][1] + top[1], blocks[-1][2] + top[2]]
    return [b[0] for b in blocks], [b[1] / b[2] for b in blocks]


def apply_isotonic(model, scores):
    """Value of the block containing each score: the first block whose upper edge xs[i] is >= the score.

    Scores above every edge get the last block's value.
    """
    xs, vals = model
    return [vals[min(bisect_left(xs, s), len(xs) - 1)] for s in scores]


# =============================================================================
# Milestone 6: undersampling, prior shift and the whole decision pipeline
# =============================================================================
def correct_undersampling(ps, beta):
    """Undo training on a sample that kept a fraction beta of the negatives (and all positives).

    p = beta * ps / (beta * ps - ps + 1)    (Dal Pozzolo et al., 2015; chapter 15)
    """
    return beta * ps / (beta * ps - ps + 1.0)


def shift_prior(p, train_rate, new_rate):
    """Rescale a probability when the positive rate moves from train_rate to new_rate (label shift).

    Multiply the odds p / (1 - p) by [new_rate / (1 - new_rate)] / [train_rate / (1 - train_rate)].
    """
    odds = p / (1.0 - p)
    odds *= (new_rate / (1.0 - new_rate)) / (train_rate / (1.0 - train_rate))
    return odds / (1.0 + odds)


def calibrated_flags(cal_scores, cal_y, test_scores, c_fp, c_fn, method):
    """The whole pipeline: recalibrate on held-out data, then apply the cost rule. Returns 0/1 flags.

    method is "none" (use test_scores as they are), "platt" or "isotonic": fit on (cal_scores, cal_y), apply to
    test_scores. Flag a test case when its probability is at least cost_threshold(c_fp, c_fn).
    """
    if method == "none":
        probs = list(test_scores)
    elif method == "platt":
        probs = apply_platt(fit_platt(cal_scores, cal_y), test_scores)
    elif method == "isotonic":
        probs = apply_isotonic(fit_isotonic(cal_scores, cal_y), test_scores)
    else:
        raise ValueError(f"unknown method {method!r}")
    t = cost_threshold(c_fp, c_fn)
    return [1 if p >= t else 0 for p in probs]
