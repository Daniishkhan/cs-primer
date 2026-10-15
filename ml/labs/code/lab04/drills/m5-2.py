# Drill: A1 Lab 4, milestone 5 of 6: the future inside a feature (step 2 of 3)
# Everything else in this file is already written. Fill in:
#     perturbation_test
# Check it with: python3 check.py 5

"""Lab 4 (reference solution): The Leakage Hunt, a validation harness that catches four planted leaks.

Conventions (the same as chapters 13 and 14 of this course):

    X          list of rows, shape (n_samples, n_features); y is a list of 0/1 labels of length n_samples
    model      a function fit(X_train, y_train) -> predict, where predict(X) returns one score per row
               (higher means more likely class 1). Every learned step lives INSIDE fit.
    splits     a list of (train_idx, val_idx) pairs of row indices, one pair per fold
    AUC        the probability that a random positive row outscores a random negative one (0.5 = chance)
    lag_days   per column: the day, relative to the prediction time T, on which the value is written.
               -1 means "known the day before T"; +9 means "written nine days AFTER T"
    case       one dataset plus everything the harness needs to know about how it was built and validated

Everything is deterministic: every random number comes from a seeded random.Random.

What is GIVEN: the five cases (make_case), the models, the windowed features and the Case container.
What YOU write is marked TODO:

    1  roc_auc, kfold_splits, cross_val_auc
    2  column_auc_scan, suspects, audit_register
    3  select_top_k, cv_with_selection, shuffle_test
    4  group_kfold, twin_share, contamination_gap
    5  time_splits, perturbation_test, temporal_leaks
    6  hunt

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import math
import random
from dataclasses import dataclass, field


# =============================================================================
# GIVEN: models, windowed features and the Case container
# =============================================================================
def _sigmoid(z):
    return 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, z))))


def logreg_model(Xtr, ytr, l2=1.0, iters=40, lr=0.5):
    """Regularised logistic regression by batch gradient descent, with standardisation fitted on Xtr.

    Returns predict(X) -> list of probabilities. The mean and standard deviation of each column are learned
    here, from Xtr only, which is exactly what keeps this model leak-free inside a cross-validation fold.
    """
    n, p = len(Xtr), len(Xtr[0])
    mu = [sum(r[c] for r in Xtr) / n for c in range(p)]
    sd = [math.sqrt(sum((r[c] - mu[c]) ** 2 for r in Xtr) / n) or 1.0 for c in range(p)]
    Z = [[(r[c] - mu[c]) / sd[c] for c in range(p)] for r in Xtr]
    w, b = [0.0] * p, 0.0
    for _ in range(iters):
        gw, gb = [l2 * wc / n for wc in w], 0.0
        for z, t in zip(Z, ytr):
            e = _sigmoid(b + sum(wc * zc for wc, zc in zip(w, z))) - t
            gb += e / n
            for c in range(p):
                gw[c] += e * z[c] / n
        b -= lr * gb
        w = [wc - lr * g for wc, g in zip(w, gw)]

    def predict(X):
        return [_sigmoid(b + sum(w[c] * (r[c] - mu[c]) / sd[c] for c in range(p))) for r in X]
    return predict


def knn1_model(Xtr, ytr):
    """1-nearest-neighbour: copy the label of the closest training row (Euclidean). A pure memoriser."""
    def predict(X):
        out = []
        for r in X:
            best, best_d = 0, float("inf")
            for j, t in enumerate(Xtr):
                d = sum((a - c) ** 2 for a, c in zip(r, t))
                if d < best_d:
                    best, best_d = j, d
            out.append(float(ytr[best]))
        return out
    return predict


def trailing_mean(series, w=7):
    """Feature for day t: the mean of days t-w .. t-1 (strictly before t). Day 0 has no history: 0.0."""
    return [sum(series[max(0, t - w):t]) / len(series[max(0, t - w):t]) if t > 0 else 0.0 for t in range(len(series))]


def centred_mean(series, w=7):
    """Feature for day t: the mean of days t-3 .. t+3. It looks three days into the future (and at day t)."""
    h = w // 2
    return [sum(series[max(0, t - h):t + h + 1]) / len(series[max(0, t - h):t + h + 1]) for t in range(len(series))]


def lag1(series):
    """Feature for day t: yesterday's value (day 0 has none: 0.0)."""
    return [0.0] + list(series[:-1])


@dataclass
class Case:
    """One dataset to audit, with everything the harness is allowed to know about it.

    names      column names                     lag_days   per column, days after T that the value is written
    groups     one entity id per row (rows with the same id are the same customer, patient, ...)
    fit        the model the team uses          cv_fn      how the team validated: cv_fn(X, y, splits) -> mean AUC
    series     for time-ordered cases, the raw daily series the features were computed from (else None)
    feature_fns   for time-ordered cases, {column name: function(series) -> list of one value per day}
    """
    name: str
    names: list
    X: list
    y: list
    lag_days: list
    groups: list
    fit: object
    cv_fn: object = None
    series: object = None
    feature_fns: dict = field(default_factory=dict)


def _poisson(rng, lam):
    limit, k, prod = math.exp(-lam), 0, rng.random()
    while prod > limit:
        k += 1
        prod *= rng.random()
    return k


def make_case(kind, seed=0):
    """Build one of five cases: "target", "preproc", "twins", "temporal" or "clean".

    target    subscription churn, 600 customers; a retention_offer_sent column is written during the
              cancellation call, 9 days after the prediction time
    preproc   100 patients x 300 noise measurements and coin-flip labels; the team picks the 10 "best" columns
              on ALL rows and then cross-validates (the wrong way round)
    twins     about 390 scans of 150 patients (1 to 4 scans each); the label belongs to the patient, scans of one
              patient look alike, and the team uses a 1-nearest-neighbour model with ordinary random folds
    temporal  daily sales; predict "high day" (sales[t] above the mean of the previous 28 days) from yesterday,
              a trailing 7-day mean and a 7-day mean centred on the day being predicted
    clean     loan default, 500 applicants; one strong but legitimate feature; nothing is wrong
    """
    rng = random.Random(f"{kind}-{seed}")
    if kind == "target":
        n = 600
        X, y = [], []
        for _ in range(n):
            tenure, spend = rng.expovariate(1 / 24), rng.gammavariate(4, 15)
            tickets, logins = _poisson(rng, 1.2), _poisson(rng, 8)
            z = -1.2 - 0.03 * tenure + 0.35 * tickets - 0.08 * logins + 0.004 * spend
            churn = 1 if rng.random() < _sigmoid(z) else 0
            offer = 1.0 if rng.random() < (0.92 if churn else 0.02) else 0.0
            X.append([tenure, spend, float(tickets), float(logins), offer])
            y.append(churn)
        return Case("target", ["tenure", "spend", "tickets_30d", "logins_30d", "retention_offer_sent"], X, y,
                    [-1, -1, -1, -1, 9], list(range(n)), logreg_model,
                    lambda X, y, s: cross_val_auc(logreg_model, X, y, s))
    if kind == "preproc":
        n, p = 100, 300
        X = [[rng.gauss(0, 1) for _ in range(p)] for _ in range(n)]
        y = [rng.randrange(2) for _ in range(n)]
        return Case("preproc", [f"gene{j:03d}" for j in range(p)], X, y, [-1] * p, list(range(n)), logreg_model,
                    lambda X, y, s: cv_with_selection(logreg_model, X, y, s, 10, inside=False))
    if kind == "twins":
        rows = []
        for pid in range(150):
            finger = [rng.gauss(0, 1) for _ in range(5)]
            label = rng.randrange(2)
            for _ in range(rng.choice([1, 2, 2, 3, 3, 4])):
                rows.append(([f + rng.gauss(0, 0.15) for f in finger], label, pid))
        rng.shuffle(rows)
        return Case("twins", [f"feature{j}" for j in range(5)], [r[0] for r in rows], [r[1] for r in rows],
                    [-1] * 5, [r[2] for r in rows], knn1_model,
                    lambda X, y, s: cross_val_auc(knn1_model, X, y, s))
    if kind == "temporal":
        T = 420
        level, series = 100.0, []
        for _ in range(T):
            level += rng.gauss(0, 1.0)
            series.append(level + rng.gauss(0, 8.0))
        fns = {"lag1": lag1, "trail7": trailing_mean, "centred7": centred_mean}
        cols = {name: fn(series) for name, fn in fns.items()}
        days = range(28, T)
        X = [[cols["lag1"][t], cols["trail7"][t], cols["centred7"][t]] for t in days]
        y = [1 if series[t] > sum(series[t - 28:t]) / 28 else 0 for t in days]
        return Case("temporal", ["lag1", "trail7", "centred7"], X, y, [-1, -1, -1], list(range(len(y))), logreg_model,
                    lambda X, y, s: cross_val_auc(logreg_model, X, y, s), series=series, feature_fns=fns)
    if kind == "clean":
        n = 500
        X, y = [], []
        for _ in range(n):
            income, age = rng.gauss(0, 1), rng.gauss(0, 1)
            late, util = float(_poisson(rng, 1.0)), rng.random()
            z = -1.3 - 0.4 * income + 0.9 * late + 1.2 * util - 0.1 * age
            X.append([income, age, late, util])
            y.append(1 if rng.random() < _sigmoid(z) else 0)
        return Case("clean", ["income_z", "age_z", "late_payments_12m", "card_utilisation"], X, y, [-1, -1, -1, -1],
                    list(range(n)), logreg_model, lambda X, y, s: cross_val_auc(logreg_model, X, y, s))
    raise ValueError(f"unknown case {kind!r}")


CASES = ["target", "preproc", "twins", "temporal", "clean"]


# =============================================================================
# Milestone 1: the harness's measuring tools
# =============================================================================
def roc_auc(scores, y):
    """ROC AUC: the probability that a random positive row has a higher score than a random negative one,
    counting ties as one half. Computed from ranks (tied scores share the average of their ranks).

    Raises ValueError if y does not contain both classes.
    """
    n1 = sum(1 for t in y if t == 1)
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        raise ValueError("roc_auc needs both classes in y")
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for t in range(i, j + 1):
            ranks[order[t]] = (i + j) / 2 + 1          # 1-based average rank of the tie group
        i = j + 1
    return (sum(r for r, t in zip(ranks, y) if t == 1) - n1 * (n1 + 1) / 2) / (n1 * n0)


def kfold_splits(n, k, seed):
    """Plain k-fold: shuffle the row indices with random.Random(seed), then deal them round-robin into k folds
    (fold i gets shuffled[i::k]). Returns [(train_idx, val_idx), ...], both sorted ascending."""
    perm = list(range(n))
    random.Random(seed).shuffle(perm)
    folds = [sorted(perm[i::k]) for i in range(k)]
    out = []
    for i in range(k):
        held = set(folds[i])
        out.append((sorted(j for j in range(n) if j not in held), folds[i]))
    return out


def cross_val_auc(fit, X, y, splits):
    """Mean validation AUC over the folds. For each (train_idx, val_idx): fit on the training rows only, score the
    validation rows, compute the fold's AUC. `fit` is a model as defined in the header (it learns inside)."""
    aucs = []
    for tr, va in splits:
        predict = fit([X[i] for i in tr], [y[i] for i in tr])
        aucs.append(roc_auc(predict([X[i] for i in va]), [y[i] for i in va]))
    return sum(aucs) / len(aucs)


# =============================================================================
# Milestone 2: the column scan and the timeline audit (catching target leakage)
# =============================================================================
def column_auc_scan(X, y, names):
    """Score every column alone by how well it ranks the target.

    Returns a list of (name, auc, distance) in column order, where auc = roc_auc(column, y) and
    distance = abs(auc - 0.5): how far from useless, in either direction.
    """
    out = []
    for c, name in enumerate(names):
        a = roc_auc([row[c] for row in X], y)
        out.append((name, a, abs(a - 0.5)))
    return out


def suspects(scan, flag_at=0.30):
    """Names of the columns whose distance is at least flag_at, in column order."""
    return [name for name, _, d in scan if d >= flag_at]


def audit_register(names, lag_days):
    """The feature register's timeline check: names of the columns written AFTER the prediction time
    (lag_days > 0), in column order."""
    return [n for n, lag in zip(names, lag_days) if lag > 0]


# =============================================================================
# Milestone 3: preprocessing inside the fold, and the shuffled-label test
# =============================================================================
def select_top_k(X, y, k):
    """The k columns whose Pearson correlation with y has the largest absolute value.

    Returns the column indices sorted ascending. Ties in |correlation| go to the lower index; a constant
    column has correlation 0.
    """
    n, p = len(X), len(X[0])
    my = sum(y) / n
    sy = math.sqrt(sum((t - my) ** 2 for t in y))
    scores = []
    for c in range(p):
        col = [r[c] for r in X]
        mc = sum(col) / n
        sc = math.sqrt(sum((v - mc) ** 2 for v in col))
        scores.append(abs(sum((v - mc) * (t - my) for v, t in zip(col, y)) / (sc * sy)) if sc > 0 and sy > 0 else 0.0)
    best = sorted(range(p), key=lambda c: (-scores[c], c))[:k]
    return sorted(best)


def cv_with_selection(fit, X, y, splits, k, inside):
    """Mean validation AUC when the model only sees the k best columns (by select_top_k).

    inside=False: choose the columns ONCE, using every row (the wrong way round), then cross-validate on
    those columns. inside=True: for each fold choose the columns using that fold's training rows only,
    then fit and score on those columns.
    """
    if not inside:
        cols = select_top_k(X, y, k)
        Xs = [[r[c] for c in cols] for r in X]
        return cross_val_auc(fit, Xs, y, splits)
    aucs = []
    for tr, va in splits:
        Xtr, ytr = [X[i] for i in tr], [y[i] for i in tr]
        cols = select_top_k(Xtr, ytr, k)
        predict = fit([[r[c] for c in cols] for r in Xtr], ytr)
        aucs.append(roc_auc(predict([[X[i][c] for c in cols] for i in va]), [y[i] for i in va]))
    return sum(aucs) / len(aucs)


def shuffle_test(cv_fn, X, y, splits, n_shuffles=6, seed=0):
    """Run the team's whole validation, cv_fn(X, y_shuffled, splits), on randomly permuted labels and return
    the mean AUC over n_shuffles shuffles.

    One random.Random(seed) does all the shuffling: for each shuffle copy y and call rng.shuffle on the copy.
    Shuffled labels carry no signal, so an honest procedure scores about 0.5. Do not modify y.
    """
    rng = random.Random(seed)
    total = 0.0
    for _ in range(n_shuffles):
        yy = list(y)
        rng.shuffle(yy)
        total += cv_fn(X, yy, splits)
    return total / n_shuffles


# =============================================================================
# Milestone 4: twins across the wall (catching train-test contamination)
# =============================================================================
def group_kfold(groups, k, seed):
    """k folds in which no group is ever split between training and validation.

    Take the distinct groups in order of first appearance, shuffle that list with random.Random(seed), sort it by
    group size descending (a stable sort, so ties keep the shuffled order), then give each group in turn to the
    fold that currently holds the fewest rows (the lowest fold number on a tie).
    Returns [(train_idx, val_idx), ...] with both lists sorted ascending.
    """
    order = list(dict.fromkeys(groups))
    random.Random(seed).shuffle(order)
    size = {g: 0 for g in order}
    for g in groups:
        size[g] += 1
    order.sort(key=lambda g: -size[g])
    fold_of, load = {}, [0] * k
    for g in order:
        f = min(range(k), key=lambda i: (load[i], i))
        fold_of[g] = f
        load[f] += size[g]
    out = []
    for f in range(k):
        out.append(([i for i, g in enumerate(groups) if fold_of[g] != f], [i for i, g in enumerate(groups) if fold_of[g] == f]))
    return out


def twin_share(splits, groups):
    """The fraction of validation rows (counted over all folds) whose group also appears in that fold's training rows."""
    twins = total = 0
    for tr, va in splits:
        seen = {groups[i] for i in tr}
        twins += sum(1 for i in va if groups[i] in seen)
        total += len(va)
    return twins / total


def contamination_gap(case, k=5, seed=0):
    """Compare ordinary folds with group folds for the case's own model.

    Returns (random_auc, grouped_auc, share) where random_auc = cross_val_auc on kfold_splits(n, k, seed),
    grouped_auc = cross_val_auc on group_kfold(case.groups, k, seed), and share = twin_share of the ordinary folds.
    """
    n = len(case.y)
    rand = kfold_splits(n, k, seed)
    grp = group_kfold(case.groups, k, seed)
    return (cross_val_auc(case.fit, case.X, case.y, rand), cross_val_auc(case.fit, case.X, case.y, grp),
            twin_share(rand, case.groups))


# =============================================================================
# Milestone 5: the future inside a feature (catching temporal leakage)
# =============================================================================
def time_splits(n, k):
    """Forward-chaining folds for time-ordered rows. With b = n // (k + 1), fold i (i = 1..k) trains on rows
    [0, i*b) and validates on rows [i*b, (i+1)*b); the last fold validates on everything from k*b to n.
    Returns [(train_idx, val_idx), ...]; every validation row is later than every training row."""
    b = n // (k + 1)
    out = []
    for i in range(1, k + 1):
        end = (i + 1) * b if i < k else n
        out.append((list(range(0, i * b)), list(range(i * b, end))))
    return out


def perturbation_test(feature_fn, series, positions, bump=1000.0):
    """Find the days on which a feature peeks at day t or later.

    For each t in positions: copy the series, add `bump` to every value from index t onwards, recompute
    feature_fn on the copy and compare the feature's value AT DAY t with the original. A feature that is
    legitimately known before day t cannot move. Return the sorted list of positions where it moved
    (by more than 1e-9). Never modify `series`.
    """
    raise NotImplementedError("TODO milestone 5: perturbation_test")


def temporal_leaks(case, step=37):
    """Names of the case's features (in case.feature_fns order) that fail the perturbation test at the days
    range(10, len(series), step). A case without a series has none."""
    if case.series is None:
        return []
    positions = list(range(10, len(case.series), step))
    return [name for name, fn in case.feature_fns.items() if perturbation_test(fn, case.series, positions)]


# =============================================================================
# Milestone 6: the whole hunt
# =============================================================================
KINDS = ["target", "preprocessing", "contamination", "temporal"]


def hunt(case, seed=0):
    """Run every detector on a case and return {kind: evidence} for each leak found (an empty dict if none).

    kind "target": column_auc_scan flags a column at flag_at 0.30, or audit_register finds a column written after T.
    kind "preprocessing": shuffle_test of case.cv_fn on kfold_splits(n, 5, seed) averages above 0.60.
    kind "contamination": contamination_gap gives share >= 0.05 AND random_auc - grouped_auc >= 0.10.
    kind "temporal": temporal_leaks finds at least one feature (add the forward-chaining AUC to the evidence).
    The evidence is a short string with the numbers that convinced you. Do not modify the case.
    """
    found = {}
    n = len(case.y)
    splits = kfold_splits(n, 5, seed)
    flagged = suspects(column_auc_scan(case.X, case.y, case.names))
    late = audit_register(case.names, case.lag_days)
    if flagged or late:
        found["target"] = f"scan flags {flagged or 'nothing'}; register says written after T: {late or 'nothing'}"
    shuffled = shuffle_test(case.cv_fn, case.X, case.y, splits, 6, seed)
    if shuffled > 0.60:
        found["preprocessing"] = f"the team's validation scores {shuffled:.3f} on shuffled labels (honest: 0.5)"
    rand, grp, share = contamination_gap(case, 5, seed)
    if share >= 0.05 and rand - grp >= 0.10:
        found["contamination"] = f"{share:.0%} of validation rows have a twin in training; AUC {rand:.3f} random folds, {grp:.3f} grouped folds"
    bad = temporal_leaks(case)
    if bad:
        fc = cross_val_auc(case.fit, case.X, case.y, time_splits(n, 4))
        found["temporal"] = f"features {bad} change when day t or later is perturbed (forward-chaining AUC with them: {fc:.3f})"
    return found
