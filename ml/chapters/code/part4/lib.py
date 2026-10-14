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
