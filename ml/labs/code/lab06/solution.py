"""Lab 6: Feature Pipelines & Stacking, the reference solution.

Conventions (the same as chapters 13, 14, 17 and 20 of this course):

    X          list of rows, shape (n_samples, n_features): numeric features only
    cats       a list of category labels, one per row (a postcode, a merchant): the high-cardinality column
    y          a list of 0/1 labels, one per row
    folds      a list of k lists of row indices; folds[j] holds the rows of validation fold j, and together they
               cover every row exactly once (see kfold_folds)
    fit_predict   a function (X_train, y_train, X_new) -> one score per row of X_new. Every learned step lives
               INSIDE it, so a call can only know what it was handed. "A base model" means one of these.

Everything is deterministic: every random number comes from a seeded random.Random.

What is GIVEN: sigmoid, logit, roc_auc, kfold_folds, fit_logreg (a small regularised logistic regression), the
four base models (logreg_fit_predict, knn_fit_predict, tree_fit_predict, memoriser_fit_predict) and the two data
generators.
What YOU write is marked TODO (the reference solution below fills them all in):

    1  smoothed_means, encode
    2  oof_encode
    3  pipeline_predict, cv_auc
    4  oof_predictions
    5  fit_stacker, stack_fit_predict

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import heapq
import math
import random


# =============================================================================
# GIVEN: maths helpers, folds, the logistic regression and two more base models
# =============================================================================
def sigmoid(z):
    """The logistic function 1 / (1 + e^-z), safe for large |z|."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-min(z, 700.0)))
    e = math.exp(max(z, -700.0))
    return e / (1.0 + e)


def logit(p, lo=0.02):
    """log(p / (1 - p)) with p clipped into [lo, 1 - lo]. The clip keeps a base model that says 0 or 1 from
    becoming an infinite input to the meta-model (chapter 20 clips at 0.02 and 0.98 too)."""
    p = min(max(p, lo), 1.0 - lo)
    return math.log(p / (1.0 - p))


def roc_auc(scores, y):
    """The probability that a random positive outscores a random negative (ties count one half), from
    average ranks."""
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


def kfold_folds(n, k, seed):
    """Shuffle range(n) with random.Random(seed) and deal the rows round-robin into k folds.

    Returns k sorted lists of row indices (the validation rows of each fold). Every row appears exactly once.
    """
    perm = list(range(n))
    random.Random(seed).shuffle(perm)
    return [sorted(perm[j::k]) for j in range(k)]


class LogReg:
    """A fitted logistic regression. Call it on rows to get probabilities.

    `weights` are the coefficients on the STANDARDISED inputs (each column minus its training mean, divided by
    its training standard deviation), so their sizes are comparable across columns; `bias` is the intercept.
    """

    def __init__(self, mu, sd, weights, bias):
        self.mu, self.sd, self.weights, self.bias = mu, sd, weights, bias

    def __call__(self, X):
        return [sigmoid(self.bias + sum(w * (v - m) / s for w, v, m, s in zip(self.weights, r, self.mu, self.sd)))
                for r in X]


def fit_logreg(X, y, l2=1.0, iters=60, lr=0.5):
    """Logistic regression with an L2 penalty by batch gradient descent, standardising columns on X itself.

    Returns a LogReg. Everything it learns (means, spreads, weights) comes from the rows it is given.
    """
    n, p = len(X), len(X[0])
    mu = [sum(r[c] for r in X) / n for c in range(p)]
    sd = [math.sqrt(sum((r[c] - mu[c]) ** 2 for r in X) / n) or 1.0 for c in range(p)]
    Z = [[(r[c] - mu[c]) / sd[c] for c in range(p)] for r in X]
    w, b = [0.0] * p, 0.0
    for _ in range(iters):
        gw, gb = [l2 * wc / n for wc in w], 0.0
        for z, t in zip(Z, y):
            e = sigmoid(b + sum(wc * zc for wc, zc in zip(w, z))) - t
            gb += e / n
            for c in range(p):
                gw[c] += e * z[c] / n
        b -= lr * gb
        w = [wc - lr * g for wc, g in zip(w, gw)]
    return LogReg(mu, sd, w, b)


def logreg_fit_predict(Xtr, ytr, Xnew):
    """Base model 1: logistic regression."""
    return fit_logreg(Xtr, ytr)(Xnew)


def knn_fit_predict(Xtr, ytr, Xnew, k=25):
    """Base model 2: the share of positives among the k nearest training rows (Euclidean, standardised)."""
    n, p = len(Xtr), len(Xtr[0])
    mu = [sum(r[c] for r in Xtr) / n for c in range(p)]
    sd = [math.sqrt(sum((r[c] - mu[c]) ** 2 for r in Xtr) / n) or 1.0 for c in range(p)]
    A = [[(r[c] - mu[c]) / sd[c] for c in range(p)] for r in Xtr]
    out = []
    for r in Xnew:
        q = [(r[c] - mu[c]) / sd[c] for c in range(p)]
        near = heapq.nsmallest(k, range(n), key=lambda j: math.dist(q, A[j]))
        out.append(sum(ytr[j] for j in near) / len(near))
    return out


def tree_fit_predict(Xtr, ytr, Xnew, max_depth=5, min_leaf=8):
    """Base model 3: a decision tree (Gini splits, at most 5 levels deep, at least 8 rows in a leaf). Leaves hold
    the share of positives among their training rows."""
    p = len(Xtr[0])

    def build(idx, depth):
        pos = sum(ytr[i] for i in idx)
        if depth == max_depth or pos in (0, len(idx)) or len(idx) < 2 * min_leaf:
            return pos / len(idx)
        best = None
        for c in range(p):
            order = sorted(idx, key=lambda i: Xtr[i][c])
            left_pos = 0
            for t in range(1, len(order)):
                left_pos += ytr[order[t - 1]]
                if t < min_leaf or len(order) - t < min_leaf or Xtr[order[t]][c] == Xtr[order[t - 1]][c]:
                    continue
                nl, nr = t, len(order) - t
                pl, pr = left_pos / nl, (pos - left_pos) / nr
                gini = nl * pl * (1 - pl) + nr * pr * (1 - pr)
                if best is None or gini < best[0]:
                    best = (gini, c, (Xtr[order[t]][c] + Xtr[order[t - 1]][c]) / 2)
        if best is None:
            return pos / len(idx)
        _, c, thr = best
        left = [i for i in idx if Xtr[i][c] <= thr]
        right = [i for i in idx if Xtr[i][c] > thr]
        return (c, thr, build(left, depth + 1), build(right, depth + 1))

    root = build(list(range(len(Xtr))), 0)

    def walk(node, r):
        while isinstance(node, tuple):
            node = node[2] if r[node[0]] <= node[1] else node[3]
        return node

    return [walk(root, r) for r in Xnew]


def memoriser_fit_predict(Xtr, ytr, Xnew):
    """Base model 4: the same tree with no brakes (12 levels, leaves of one row). It memorises: its predictions
    on rows it was trained on are nearly perfect, far better than anything it does on new rows."""
    return tree_fit_predict(Xtr, ytr, Xnew, max_depth=12, min_leaf=1)


BASE_MODELS = [logreg_fit_predict, knn_fit_predict, tree_fit_predict, memoriser_fit_predict]
BASE_NAMES = ["logistic", "kNN", "tree", "memoriser"]


# =============================================================================
# GIVEN: the data
# =============================================================================
def make_applications(n, seed, signal=True, n_levels=300):
    """Loan applications with a high-cardinality category. Returns (X, cats, y).

    X     two numeric columns per row: income-like and age-like, standard normals
    cats  a postcode label such as "pc017", one of n_levels; a few postcodes are common and most are rare
    y     1 = defaulted. The numeric columns carry a modest signal. If signal is True each postcode also has its
          own effect on the log-odds (standard deviation 1.0), so the category really matters; if False the
          postcodes are PURE NOISE and any apparent predictive power in them is a leak.
    """
    rng = random.Random(f"apps-{seed}-{signal}")
    effect = [rng.gauss(0.0, 1.0) if signal else 0.0 for _ in range(n_levels)]
    X, cats, y = [], [], []
    for _ in range(n):
        level = int(n_levels * rng.random() ** 2)          # skewed: low numbers are common
        x = [rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)]
        z = -0.8 + 0.7 * x[0] - 0.4 * x[1] + effect[level]
        X.append(x)
        cats.append(f"pc{level:03d}")
        y.append(1 if rng.random() < sigmoid(z) else 0)
    return X, cats, y


def make_stack_data(n, seed):
    """Ten numeric features and a label that mixes three kinds of structure. Returns (X, y).

    log-odds = 1.3 x0 - 0.8 x1          a linear part: logistic regression sees it
             + 1.3 sign(x2) sign(x3)    a quadrant effect: a tree sees it, a linear model cannot
             + 1.6 sin(2.5 x4)          a wavy local effect: neighbours see it, a line cannot
    Columns x5 to x9 are noise. No single model captures all three parts, and each is distracted by the others.
    """
    rng = random.Random(f"stack-{seed}")
    X, y = [], []
    for _ in range(n):
        r = [rng.gauss(0.0, 1.0) for _ in range(10)]
        z = (1.3 * r[0] - 0.8 * r[1] + 1.3 * (1 if r[2] > 0 else -1) * (1 if r[3] > 0 else -1)
             + 1.6 * math.sin(2.5 * r[4]))
        X.append(r)
        y.append(1 if rng.random() < sigmoid(z) else 0)
    return X, y


# =============================================================================
# Milestone 1: smoothed target encoding
# =============================================================================
def smoothed_means(cats, y, m):
    """Learn a target encoding. Returns (table, prior).

    prior is the overall mean of y. For each level seen in cats, with n rows and level mean mu:

        table[level] = (n * mu + m * prior) / (n + m)

    m is the smoothing weight: "the number of imaginary average rows added to every level". m = 0 gives the
    raw level mean; a level with few rows is pulled towards the prior, a level with many hardly moves.
    """
    prior = sum(y) / len(y)
    count, total = {}, {}
    for c, t in zip(cats, y):
        count[c] = count.get(c, 0) + 1
        total[c] = total.get(c, 0) + t
    table = {c: (total[c] + m * prior) / (count[c] + m) for c in count}     # n * mu is the sum of the labels
    return table, prior


def encode(table, prior, cats):
    """Look each level up in the table. A level the table has never seen gets the prior."""
    return [table.get(c, prior) for c in cats]


# =============================================================================
# Milestone 2: out-of-fold target encoding
# =============================================================================
def oof_encode(cats, y, folds, m):
    """Encode the training rows without any row's own label (or any label of its fold) reaching it.

    For each fold: learn smoothed_means from the rows NOT in the fold, then encode the fold's rows with it
    (levels unseen outside the fold get that table's prior). Returns one value per row, in row order.
    """
    out = [0.0] * len(cats)
    for fold in folds:
        held = set(fold)
        rest = [i for i in range(len(cats)) if i not in held]
        table, prior = smoothed_means([cats[i] for i in rest], [y[i] for i in rest], m)
        for i, v in zip(fold, encode(table, prior, [cats[i] for i in fold])):
            out[i] = v
    return out


# =============================================================================
# Milestone 3: a leak-safe feature pipeline inside cross-validation
# =============================================================================
def pipeline_predict(Xtr, cats_tr, ytr, Xte, cats_te, k=5, m=10.0, seed=0):
    """Train the whole pipeline on the training rows and score the test rows. Returns one probability per test row.

    1. Encode the training categories out of fold (k folds from kfold_folds(len(ytr), k, seed), smoothing m).
    2. Learn the table on ALL the training rows and encode the test categories with it.
    3. Append the encoding to the numeric columns as one extra column; fit_logreg on the training rows; predict.

    Nothing about the test rows' labels is available here, and the test rows play no part in any step.
    """
    folds = kfold_folds(len(ytr), k, seed)
    enc_tr = oof_encode(cats_tr, ytr, folds, m)
    table, prior = smoothed_means(cats_tr, ytr, m)
    enc_te = encode(table, prior, cats_te)
    A = [list(r) + [e] for r, e in zip(Xtr, enc_tr)]
    B = [list(r) + [e] for r, e in zip(Xte, enc_te)]
    return fit_logreg(A, ytr)(B)


def cv_auc(X, cats, y, folds, k=5, m=10.0, seed=0):
    """Honest cross-validated AUC of the pipeline: for each outer fold, run pipeline_predict on the other rows,
    score the fold, and average the fold AUCs."""
    aucs = []
    for fold in folds:
        held = set(fold)
        tr = [i for i in range(len(y)) if i not in held]
        scores = pipeline_predict([X[i] for i in tr], [cats[i] for i in tr], [y[i] for i in tr],
                                  [X[i] for i in fold], [cats[i] for i in fold], k, m, seed)
        aucs.append(roc_auc(scores, [y[i] for i in fold]))
    return sum(aucs) / len(aucs)


# =============================================================================
# Milestone 4: out-of-fold predictions
# =============================================================================
def oof_predictions(fit_predict, X, y, folds):
    """Predict every row with a model that never saw it.

    For each fold: call fit_predict(X_train, y_train, X_fold) with the rows OUTSIDE the fold as training data
    and the fold's rows as the rows to predict. Returns one score per row, in row order.
    """
    out = [0.0] * len(y)
    for fold in folds:
        held = set(fold)
        tr = [i for i in range(len(y)) if i not in held]
        preds = fit_predict([X[i] for i in tr], [y[i] for i in tr], [X[i] for i in fold])
        for i, s in zip(fold, preds):
            out[i] = s
    return out


# =============================================================================
# Milestone 5: stacking
# =============================================================================
def fit_stacker(P, y):
    """The meta-model. P is a list of rows, one per case, holding the base models' predictions for that case.

    Replace every prediction by its logit (the given logit clips at 0.02 and 0.98), then fit_logreg on those
    columns. Returns (predict, weights): predict(P_new) gives one probability per row, and weights are the
    meta-model's coefficients on the standardised logit columns, one per base model.
    """
    model = fit_logreg([[logit(v) for v in row] for row in P], y)

    def predict(P_new):
        return model([[logit(v) for v in row] for row in P_new])

    return predict, list(model.weights)


def stack_fit_predict(base_models, Xtr, ytr, Xnew, folds, honest=True):
    """A stacked ensemble. base_models is a list of fit_predict functions. Returns (scores, weights).

    honest=True  (the recipe): build the meta-model's training matrix from OUT-OF-FOLD predictions, one column
                 per base model (oof_predictions with `folds`).
    honest=False (the mistake, kept to measure it): use each base model's predictions on its OWN training rows.

    Either way: fit_stacker on that matrix and ytr; refit every base model on ALL the training rows to predict
    Xnew; give those predictions to the meta-model. `weights` is what fit_stacker returned.
    """
    if honest:
        cols = [oof_predictions(fp, Xtr, ytr, folds) for fp in base_models]
    else:
        cols = [fp(Xtr, ytr, Xtr) for fp in base_models]
    predict, weights = fit_stacker([list(r) for r in zip(*cols)], ytr)
    new_cols = [fp(Xtr, ytr, Xnew) for fp in base_models]
    return predict([list(r) for r in zip(*new_cols)]), weights
