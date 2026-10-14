import numpy as np
from lib import roc_auc, sigmoid

def mlp_fit_predict(Xtr, ytr, Xte, rng, hidden=64, epochs=120, lr=2e-3, wd=1e-4):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9; A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    k = len(A) * 4 // 5; Atr, ytr2, Aval, yval = A[:k], ytr[:k], A[k:], ytr[k:]      # last 20% for early stopping
    P = {"W1": rng.normal(0, np.sqrt(2 / A.shape[1]), (A.shape[1], hidden)), "b1": np.zeros(hidden),
         "W2": rng.normal(0, np.sqrt(2 / hidden), (hidden, hidden)), "b2": np.zeros(hidden),
         "W3": rng.normal(0, np.sqrt(1 / hidden), (hidden, 1)), "b3": np.zeros(1)}
    M = {k_: np.zeros_like(v) for k_, v in P.items()}; V = {k_: np.zeros_like(v) for k_, v in P.items()}
    def fwd(X):
        h1 = np.maximum(X @ P["W1"] + P["b1"], 0); h2 = np.maximum(h1 @ P["W2"] + P["b2"], 0)
        return h1, h2, (h2 @ P["W3"] + P["b3"]).ravel()
    best, best_P, step = -1, None, 0
    for ep in range(epochs):
        order = rng.permutation(len(Atr))
        for i in range(0, len(order), 64):
            idx = order[i:i + 64]; x, t = Atr[idx], ytr2[idx]
            h1, h2, z = fwd(x); g = ((sigmoid(z) - t) / len(idx))[:, None]            # d(loss)/d(logit) for cross-entropy
            G = {"W3": h2.T @ g, "b3": g.sum(0)}; d2 = (g @ P["W3"].T) * (h2 > 0)
            G["W2"], G["b2"] = h1.T @ d2, d2.sum(0); d1 = (d2 @ P["W2"].T) * (h1 > 0)
            G["W1"], G["b1"] = x.T @ d1, d1.sum(0); step += 1
            for k_ in P:                                                               # Adam update
                M[k_] = 0.9 * M[k_] + 0.1 * G[k_]; V[k_] = 0.999 * V[k_] + 0.001 * G[k_] ** 2
                P[k_] -= lr * (M[k_] / (1 - 0.9 ** step)) / (np.sqrt(V[k_] / (1 - 0.999 ** step)) + 1e-8) + lr * wd * P[k_]
        a = roc_auc(fwd(Aval)[2], yval.astype(int))
        if a > best: best, best_P = a, {k_: v.copy() for k_, v in P.items()}
    P.update(best_P)
    return fwd(B)[2]

