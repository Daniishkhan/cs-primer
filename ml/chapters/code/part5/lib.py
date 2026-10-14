import numpy as np

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))

def fit_logreg(X, y, l2=1.0, iters=25, w=None):
    """L2-penalised logistic regression by Newton steps. Returns (b, coef)."""
    n, d = X.shape
    A = np.c_[np.ones(n), X]
    beta = np.zeros(d + 1)
    sw = np.ones(n) if w is None else w
    pen = np.r_[0.0, np.full(d, l2)]
    for _ in range(iters):
        p = sigmoid(A @ beta)
        g = A.T @ (sw * (p - y)) + pen * beta
        H = (A * (sw * p * (1 - p))[:, None]).T @ A + np.diag(pen) + 1e-9 * np.eye(d + 1)
        beta -= np.linalg.solve(H, g)
    return beta

def predict_proba(beta, X):
    return sigmoid(np.c_[np.ones(len(X)), X] @ beta)

def roc_auc(s, y):
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s) + 1)
    # average ranks for ties
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=ranks)
    ranks = (sums / cnt)[inv]
    n1 = y.sum(); n0 = len(y) - n1
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

def average_precision(s, y):
    ys = y[np.argsort(-s, kind="mergesort")]
    tp = np.cumsum(ys)
    return (tp / np.arange(1, len(y) + 1))[ys == 1].mean()

# ---- small least-squares boosted trees (used as the "tree model" in chapter 17 and 18 experiments) ----
def _build(X, y, depth, min_leaf):
    if depth == 0 or len(y) < 2 * min_leaf:
        return y.mean()
    best = (np.inf, None, None)
    for j in range(X.shape[1]):
        o = np.argsort(X[:, j], kind="mergesort"); xs, ys = X[o, j], y[o]
        cs, cs2 = np.cumsum(ys), np.cumsum(ys ** 2)
        k = np.arange(min_leaf, len(y) - min_leaf + 1)
        sse = (cs2[k-1] - cs[k-1]**2 / k) + ((cs2[-1]-cs2[k-1]) - (cs[-1]-cs[k-1])**2 / (len(y)-k))
        sse[xs[k - 1] == xs[k]] = np.inf
        i = sse.argmin()
        if sse[i] < best[0]:
            best = (sse[i], j, (xs[k[i] - 1] + xs[k[i]]) / 2)
    _, j, t = best
    if j is None:
        return y.mean()
    m = X[:, j] <= t
    return (j, t, _build(X[m], y[m], depth - 1, min_leaf), _build(X[~m], y[~m], depth - 1, min_leaf))

def _predict(tree, X):
    if not isinstance(tree, tuple):
        return np.full(len(X), tree)
    j, t, l, r = tree
    out = np.empty(len(X)); m = X[:, j] <= t
    out[m] = _predict(l, X[m]); out[~m] = _predict(r, X[~m])
    return out

class Boost:
    """Least-squares gradient boosting with depth-limited trees: fit(X, y), predict(X)."""
    def __init__(self, rounds=150, lr=0.1, depth=3, min_leaf=20):
        self.rounds, self.lr, self.depth, self.min_leaf = rounds, lr, depth, min_leaf
    def fit(self, X, y):
        self.f0 = y.mean(); F = np.full(len(y), self.f0); self.trees = []
        for _ in range(self.rounds):
            t = _build(X, y - F, self.depth, self.min_leaf)
            F += self.lr * _predict(t, X); self.trees.append(t)
        return self
    def predict(self, X):
        F = np.full(len(X), self.f0)
        for t in self.trees:
            F += self.lr * _predict(t, X)
        return F
