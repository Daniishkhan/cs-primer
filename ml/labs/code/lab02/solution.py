"""Lab 2 (reference solution): a CART tree, a random forest and gradient boosting, in plain Python.

Conventions (the same as chapters 8 and 9 of this course):

    X        list of rows, shape (n_samples, n_features); y is a list of length n_samples
    node     a tree is nested dicts. A leaf is {"n": rows, "value": mean of y}. A split node also has
             "feat" (column index), "thr" (rows with x[feat] <= thr go left), "gain" (the impurity
             decrease of the split) and "left" / "right" (child nodes)
    classes  labels are 0.0 or 1.0, so the mean of y in a leaf is the probability of class 1
    gini     2 p (1 - p) for a node whose fraction of positives is p
    mse      the variance of y in the node; a leaf predicts the mean

Everything is deterministic: every random number comes from a seeded random.Random.
"""
import math
import random
from dataclasses import dataclass, field


# =============================================================================
# GIVEN: synthetic data, containers and helpers that are not the lesson
# =============================================================================
def _poisson(rng, lam):
    limit, k, prod = math.exp(-lam), 0, rng.random()
    while prod > limit:
        k += 1
        prod *= rng.random()
    return k


FEATURES = ["tenure", "spend", "tickets", "basic_plan"]


def make_churn_rules(seed, n=1500):
    """Chapter 8's churn data: columns [tenure, spend, tickets, basic_plan], y = 1.0 if the customer churned.

    A customer is 'risky' if they have at least 3 tickets and under 24 months of tenure, or are on the basic
    plan with spend above 65 and under 40 months of tenure. Risky customers churn with probability 0.88 and the
    others with 0.12, so the best possible accuracy is 0.88.
    """
    rng = random.Random(seed)
    X, y = [], []
    for _ in range(n):
        tenure, spend = rng.uniform(1, 60), max(5.0, rng.gauss(50, 20))
        tickets, basic = float(_poisson(rng, 1.5)), float(rng.randint(0, 1))
        risky = (tickets >= 3 and tenure < 24) or (basic == 1 and spend > 65 and tenure < 40)
        X.append([tenure, spend, tickets, basic])
        y.append(1.0 if rng.random() < (0.88 if risky else 0.12) else 0.0)
    return X, y


def make_friedman(seed, n, noise=1.0, d=10):
    """Friedman's benchmark #1: d features uniform on [0, 1], only the first five matter.

    y = 10 sin(pi x0 x1) + 20 (x2 - 0.5)^2 + 10 x3 + 5 x4 + N(0, noise^2)

    Features 5 to d-1 are pure noise. The best possible RMSE is `noise`.
    """
    rng = random.Random(seed)
    X, y = [], []
    for _ in range(n):
        x = [rng.random() for _ in range(d)]
        X.append(x)
        y.append(10 * math.sin(math.pi * x[0] * x[1]) + 20 * (x[2] - 0.5) ** 2 + 10 * x[3] + 5 * x[4] + rng.gauss(0, noise))
    return X, y


def rmse(y, p):
    """Root mean squared error."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(y, p)) / len(y))


def accuracy(y, p, threshold=0.5):
    """Fraction of rows where (p >= threshold) matches the 0/1 label."""
    return sum((q >= threshold) == (t >= 0.5) for t, q in zip(y, p)) / len(y)


def show(node, names=None, indent=""):
    """The tree as indented if/else rules, one string (leaves print their mean and how many rows reached them)."""
    names = names or FEATURES
    if "feat" not in node:
        return f"{indent}-> {node['value']:.3f}  (n={node['n']})\n"
    out = f"{indent}if {names[node['feat']]} <= {node['thr']:.2f}:\n" + show(node["left"], names, indent + "    ")
    return out + f"{indent}else:\n" + show(node["right"], names, indent + "    ")


@dataclass
class Forest:
    """A random forest: its trees, and for each tree the list of row indices of its bootstrap sample."""
    trees: list = field(default_factory=list)
    bags: list = field(default_factory=list)


@dataclass
class GBM:
    """A gradient-boosted regressor: F(x) = f0 + lr * sum of the trees' predictions."""
    f0: float
    lr: float
    trees: list = field(default_factory=list)


# =============================================================================
# Milestone 1: impurity and the best split
# =============================================================================
def gini(y):
    """Gini impurity of a list of class labels: 1 - sum_k p_k^2 (0 for an empty or pure list)."""
    if not y:
        return 0.0
    n = len(y)
    counts = {}
    for label in y:
        counts[label] = counts.get(label, 0) + 1
    return 1.0 - sum((c / n) ** 2 for c in counts.values())


def variance(y):
    """Population variance of y (0 for an empty list): the regression impurity."""
    if not y:
        return 0.0
    m = sum(y) / len(y)
    return sum((v - m) ** 2 for v in y) / len(y)


def best_split(X, y, criterion="gini", min_leaf=1, features=None):
    """The split (gain, feature, threshold) with the largest impurity decrease, or None.

    criterion  "gini" (y is 0/1; impurity 2p(1-p)) or "mse" (impurity = variance of y)
    min_leaf   both children must have at least this many rows
    features   the column indices to search (default: all)

    Candidate thresholds are the midpoints between consecutive DISTINCT sorted values of a feature; rows with
    x <= threshold go left. gain = impurity(parent) - (n_left * impurity(left) + n_right * impurity(right)) / n.
    Sort each feature once and keep running sums, so a feature costs one pass.
    Ties go to the lowest feature index, then the lowest threshold. Return None unless the best gain is positive.
    """
    n = len(y)
    if n < 2 * min_leaf or n < 2:
        return None
    feats = range(len(X[0])) if features is None else features
    use_gini = criterion == "gini"
    total, total_sq = sum(y), sum(v * v for v in y)
    if use_gini:
        p = total / n
        parent = 2 * p * (1 - p)
    else:
        parent = total_sq / n - (total / n) ** 2
    best = (1e-12, None, None)
    for f in feats:
        col = [row[f] for row in X]
        order = sorted(range(n), key=col.__getitem__)
        ls = lq = 0.0                                   # running sum and sum of squares of the left side
        for i in range(n - 1):
            v = y[order[i]]
            ls += v
            lq += v * v
            nl = i + 1
            nr = n - nl
            if nl < min_leaf or nr < min_leaf:
                continue
            a, b = col[order[i]], col[order[i + 1]]
            if a == b:                                  # cannot cut between equal values
                continue
            if use_gini:
                pl, pr = ls / nl, (total - ls) / nr
                child = (nl * 2 * pl * (1 - pl) + nr * 2 * pr * (1 - pr)) / n
            else:
                rs, rq = total - ls, total_sq - lq
                child = ((lq - ls * ls / nl) + (rq - rs * rs / nr)) / n
            gain = parent - child
            if gain > best[0] + 1e-12:
                best = (gain, f, (a + b) / 2)
    return None if best[1] is None else best


# =============================================================================
# Milestone 2: growing and using a tree
# =============================================================================
def grow(X, y, criterion="gini", max_depth=3, min_leaf=1, max_features=None, rng=None, depth=0):
    """Grow a CART tree by greedy recursive splitting. Returns the root node (see the module docstring).

    Every node stores "n" and "value" (the mean of y). Stop and return a leaf when depth == max_depth, when y is
    constant, or when best_split finds nothing. A split node also stores "feat", "thr", "gain", "left", "right".
    If max_features is not None, each node searches only a random subset of that many features, drawn with
    rng.sample(range(n_features), max_features) (this is what milestone 3's forest uses).
    """
    node = {"n": len(y), "value": sum(y) / len(y)}
    if depth >= max_depth or min(y) == max(y):
        return node
    feats = None
    if max_features is not None and max_features < len(X[0]):
        feats = sorted(rng.sample(range(len(X[0])), max_features))
    s = best_split(X, y, criterion, min_leaf, feats)
    if s is None:
        return node
    gain, f, thr = s
    left = [i for i, row in enumerate(X) if row[f] <= thr]
    right = [i for i, row in enumerate(X) if row[f] > thr]
    node.update(feat=f, thr=thr, gain=gain,
                left=grow([X[i] for i in left], [y[i] for i in left], criterion, max_depth, min_leaf, max_features, rng, depth + 1),
                right=grow([X[i] for i in right], [y[i] for i in right], criterion, max_depth, min_leaf, max_features, rng, depth + 1))
    return node


def predict_one(node, x):
    """Walk one row down the tree and return the value of the leaf it lands in."""
    while "feat" in node:
        node = node["left"] if x[node["feat"]] <= node["thr"] else node["right"]
    return node["value"]


def predict_tree(node, X):
    """predict_one for every row."""
    return [predict_one(node, row) for row in X]


def depth_of(node):
    """Number of splits on the longest path from the root (a single leaf has depth 0)."""
    if "feat" not in node:
        return 0
    return 1 + max(depth_of(node["left"]), depth_of(node["right"]))


def n_leaves(node):
    """Number of leaves."""
    if "feat" not in node:
        return 1
    return n_leaves(node["left"]) + n_leaves(node["right"])


# =============================================================================
# Milestone 3: bagging and the random forest
# =============================================================================
def bootstrap_sample(n, rng):
    """n row indices drawn uniformly WITH replacement from range(n)."""
    return [rng.randrange(n) for _ in range(n)]


def fit_forest(X, y, n_trees=50, max_features=None, max_depth=8, min_leaf=3, criterion="mse", seed=0):
    """A random forest: n_trees trees, each grown on its own bootstrap sample.

    rng = random.Random(seed) is used for everything (bootstrap samples first, then each tree's feature subsets).
    Returns a Forest holding the trees and, for every tree, the list of indices of its bootstrap sample.
    max_features=None means every feature at every split (plain bagging).
    """
    rng = random.Random(seed)
    forest = Forest()
    for _ in range(n_trees):
        idx = bootstrap_sample(len(y), rng)
        tree = grow([X[i] for i in idx], [y[i] for i in idx], criterion, max_depth, min_leaf, max_features, rng)
        forest.trees.append(tree)
        forest.bags.append(idx)
    return forest


def forest_predict(forest, X):
    """The average of the trees' predictions, row by row (for 0/1 labels this is a probability)."""
    per_tree = [predict_tree(t, X) for t in forest.trees]
    return [sum(col) / len(col) for col in zip(*per_tree)]


def oob_predict(forest, X):
    """Out-of-bag prediction for every row of X, which must be the training rows the forest was fitted on.

    Row i is predicted by the average over only those trees whose bootstrap sample did not contain i.
    Rows that every tree saw get None.
    """
    in_bag = [set(b) for b in forest.bags]
    out = []
    for i, row in enumerate(X):
        votes = [predict_one(t, row) for t, bag in zip(forest.trees, in_bag) if i not in bag]
        out.append(sum(votes) / len(votes) if votes else None)
    return out


def oob_rmse(forest, X, y):
    """RMSE of the out-of-bag predictions, over the rows that have one."""
    pred = oob_predict(forest, X)
    pairs = [(t, p) for t, p in zip(y, pred) if p is not None]
    return rmse([t for t, _ in pairs], [p for _, p in pairs])


# =============================================================================
# Milestone 4: gradient boosting for regression
# =============================================================================
def fit_gbm(X, y, n_rounds=100, lr=0.1, max_depth=3, min_leaf=1):
    """Gradient boosting with squared error.

    Start from the constant f0 = mean(y). In each round compute the residuals y - F(x) (the negative gradient of
    the squared error), grow a regression tree ("mse" criterion, max_depth, min_leaf) on them, and add lr times
    that tree to the running predictions. Returns a GBM holding f0, lr and the n_rounds trees in order.
    """
    n = len(y)
    f0 = sum(y) / n
    F = [f0] * n
    model = GBM(f0, lr)
    for _ in range(n_rounds):
        resid = [yi - fi for yi, fi in zip(y, F)]
        tree = grow(X, resid, "mse", max_depth, min_leaf)
        model.trees.append(tree)
        F = [fi + lr * predict_one(tree, row) for fi, row in zip(F, X)]
    return model


def gbm_predict(model, X, n_rounds=None):
    """F(x) = f0 + lr * (sum of the first n_rounds trees' predictions); all rounds if n_rounds is None."""
    trees = model.trees if n_rounds is None else model.trees[:n_rounds]
    return [model.f0 + model.lr * sum(predict_one(t, row) for t in trees) for row in X]


def staged_rmse(model, X, y):
    """The RMSE on (X, y) after 1, 2, ..., M rounds, as a list of length M, in one pass over the trees."""
    F = [model.f0] * len(y)
    curve = []
    for tree in model.trees:
        F = [fi + model.lr * predict_one(tree, row) for fi, row in zip(F, X)]
        curve.append(rmse(y, F))
    return curve


def best_round(curve):
    """The 1-based round with the smallest value in the curve (the first one if there is a tie)."""
    return min(range(len(curve)), key=curve.__getitem__) + 1


# =============================================================================
# Milestone 5: importances, and the three models side by side
# =============================================================================
def tree_importance_raw(node, d):
    """Total weighted impurity decrease per feature: for every split node add n_node * gain to its feature.
    Returns a list of d floats (not normalised)."""
    imp = [0.0] * d

    def walk(nd):
        if "feat" in nd:
            imp[nd["feat"]] += nd["n"] * nd["gain"]
            walk(nd["left"])
            walk(nd["right"])

    walk(node)
    return imp


def normalise(v):
    """Scale a list of non-negative numbers to sum to 1 (all zeros stay all zeros)."""
    s = sum(v)
    return [x / s for x in v] if s > 0 else [0.0] * len(v)


def tree_importance(node, d):
    """Feature importances of one tree: tree_importance_raw, normalised to sum to 1."""
    return normalise(tree_importance_raw(node, d))


def forest_importance(forest, d):
    """The average of the trees' normalised importances."""
    per = [tree_importance(t, d) for t in forest.trees]
    return [sum(col) / len(per) for col in zip(*per)]


def gbm_importance(model, d):
    """Boosting importances: add up every tree's raw importance, then normalise."""
    total = [0.0] * d
    for t in model.trees:
        total = [a + b for a, b in zip(total, tree_importance_raw(t, d))]
    return normalise(total)
