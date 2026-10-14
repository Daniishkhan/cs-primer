"""The same models in scikit-learn: run the ml labs' own data and code
beside scikit-learn's, and compare number by number.

    python lab_vs_sklearn.py
    python lab_vs_sklearn.py --labs /path/to/ml/labs/code

Needs: numpy, scikit-learn (workbench/requirements.txt) and the course
folder, because it imports ml/labs/code/lab01/solution.py and lab02."""
import argparse
import importlib.util
import math
import time
import warnings
from pathlib import Path

import numpy as np
from sklearn.ensemble import (GradientBoostingRegressor,
                              HistGradientBoostingRegressor)
from sklearn.linear_model import (Lasso, LinearRegression,
                                  LogisticRegression, Ridge)
from sklearn.model_selection import GridSearchCV, KFold, PredefinedSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import sklearn

# ── 1. Load the labs' reference solutions ────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--labs", default=None)        # folder holding lab01, lab02
args, _ = ap.parse_known_args()        # notebooks pass their own flags


def find_labs():
    if args.labs:
        return Path(args.labs)
    try:
        here = Path(__file__).resolve()
    except NameError:                  # inside a notebook
        here = Path.cwd().resolve()
    for base in [here, *here.parents]:
        if (base / "ml/labs/code").is_dir():
            return base / "ml/labs/code"
        if (base / "labs/code").is_dir():
            return base / "labs/code"
    raise SystemExit("cannot find ml/labs/code; pass --labs")


def load(name):
    path = find_labs() / name / "solution.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lab1, lab2 = load("lab01"), load("lab02")
print(f"scikit-learn {sklearn.__version__}, numpy {np.__version__}")


def worst(a, b):
    """Largest absolute difference between two lists of numbers."""
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))


# ── 2. Ordinary least squares (chapter 5) ────────────────────────────────
# Predict: both solve the same normal equations, so the numbers agree to
# rounding error (about 1e-9 or better), not just to two decimals.
Xl, yl = lab1.make_rent(seed=1, n=200)
X, y = np.array(Xl), np.array(yl)
theta = lab1.fit_ols(Xl, yl)                    # [b, w_area, w_dist, w_age]
sk = LinearRegression().fit(X, y)
print("\nOLS on the rent data (true: 300, 11, -25, -2)")
print(f"  lab      b={theta[0]:9.4f}  w={np.round(theta[1:], 4)}")
print(f"  sklearn  b={sk.intercept_:9.4f}  w={np.round(sk.coef_, 4)}")
print(f"  largest difference: "
      f"{worst(theta, [sk.intercept_, *sk.coef_]):.2e}")

# ── 3. Ridge and lasso: what alpha means (chapter 6) ─────────────────────
# Lab ridge:  sum of squares + alpha * sum w^2           (standardised X)
# sklearn Ridge: the same expression. Predict: same alpha, same answer.
# Lab lasso:  1/(2n) * sum of squares + alpha * sum |w|  (standardised X)
# sklearn Lasso: the same 1/(2n) convention. Predict: same alpha, same.
# The trap is the features. sklearn does not standardise for you; on raw
# columns the penalty falls unevenly, and the answer is a different model.
Xs, ys, support = lab1.make_sparse(seed=2, n=60, d=20, sigma=3.0)
Xs, ys = np.array(Xs), np.array(ys)
Z = StandardScaler().fit_transform(Xs)         # divides by the population sd
alpha = 3.0
m = lab1.ridge_fit(Xs.tolist(), ys.tolist(), alpha)
r = Ridge(alpha=alpha).fit(Z, ys)
print("\nridge, alpha=3, 20 features, 60 rows")
print(f"  lab vs sklearn on standardised X: "
      f"{worst(m.w, r.coef_):.2e} apart")

# The same alpha on the rent data, whose columns have very different
# scales (area 25 to 120 m2, distance 0.5 to 15 km, age 0 to 80 years).
# Predict: sklearn Ridge on the raw columns shrinks the small-scale
# column (distance) far less than the lab does, so the two models differ.
BIG = 20000.0
lab_r = lab1.ridge_fit(Xl, yl, BIG).to_original()
pipe = make_pipeline(StandardScaler(), Ridge(alpha=BIG)).fit(X, y)
sc, rg = pipe[0], pipe[-1]
pipe_w = rg.coef_ / sc.scale_              # back to the original units
pipe_b = rg.intercept_ - float(np.sum(pipe_w * sc.mean_))
raw_r = Ridge(alpha=BIG).fit(X, y)
print(f"\nridge, alpha={BIG:g}, rent data, weights in original units")
print(f"  lab                  w={np.round(lab_r[1:], 3)}")
print(f"  sklearn + scaler     w={np.round(pipe_w, 3)}"
      f"  ({worst(lab_r[1:], pipe_w):.1e} from the lab)")
print(f"  sklearn, raw columns w={np.round(raw_r.coef_, 3)}")

a_max = lab1.alpha_max(Xs.tolist(), ys.tolist())
print(f"\nlasso: lab alpha_max = {a_max:.4f}")
print("  alpha   kept(lab) kept(sklearn)  largest difference in w")
for frac in (0.5, 0.2, 0.05):
    a = frac * a_max
    lm = lab1.lasso_fit(Xs.tolist(), ys.tolist(), a)
    sl = Lasso(alpha=a, tol=1e-12, max_iter=100000).fit(Z, ys)
    kl = sum(abs(w) > 1e-12 for w in lm.w)
    ks = int(np.sum(np.abs(sl.coef_) > 1e-12))
    print(f"  {a:6.3f}  {kl:8d}  {ks:12d}   {worst(lm.w, sl.coef_):.2e}")

# ── 4. Logistic regression: C is not l2 (chapter 5 and 6) ────────────────
# Lab:     mean log-loss + (l2 / 2) * sum w^2
# sklearn: C * sum log-loss + (1 / 2) * sum w^2
# Divide sklearn's by C * n: mean log-loss + (1 / (2 C n)) * sum w^2.
# Predict: the two agree when l2 = 1 / (C n), that is C = 1 / (n * l2).
Xc, yc = lab1.make_churn(seed=3, n=700)
Xc, yc = np.array(Xc), np.array(yc)
n = len(yc)
Zc = StandardScaler().fit_transform(Xc)
print("\nlogistic regression on the churn data (n=700)")
print("  l2    lab steps   C used by sklearn     largest |w| difference")
for l2 in (0.0, 0.01, 0.1):
    lm = lab1.fit_logistic(Xc.tolist(), yc.tolist(), l2=l2, steps=400)
    if l2 == 0.0:
        sk = LogisticRegression(C=np.inf, tol=1e-12, max_iter=10000)
        c_txt = "infinity (no penalty)"
    else:
        c = 1.0 / (n * l2)
        sk = LogisticRegression(C=c, tol=1e-12, max_iter=10000)
        c_txt = f"1/(n*l2) = {c:.4f}"
    sk.fit(Zc, yc)
    w_lab = lm.theta[1:]
    print(f"  {l2:<5} {400:9d}   {c_txt:21} "
          f"{worst(w_lab, sk.coef_[0]):.2e}")
wrong = LogisticRegression(C=1 / 0.1, tol=1e-12).fit(Zc, yc)
lm = lab1.fit_logistic(Xc.tolist(), yc.tolist(), l2=0.1)
print(f"  with the wrong guess C = 1/l2 = 10: "
      f"{worst(lm.theta[1:], wrong.coef_[0]):.2e} apart")
more = lab1.fit_logistic(Xc.tolist(), yc.tolist(), l2=0.0, steps=5000)
sk0 = LogisticRegression(C=np.inf, tol=1e-12, max_iter=10000)
sk0.fit(Zc, yc)
print(f"  l2=0 with 5,000 lab steps instead of 400: "
      f"{worst(more.theta[1:], sk0.coef_[0]):.2e} apart")

# ── 5. Cross-validation (chapter 6) ──────────────────────────────────────
# Lab: row i is in fold i % 5, the scaler is refitted inside every fold,
# and the score is the MEAN OF THE FOLD RMSEs. sklearn's KFold cuts
# contiguous blocks. Predict: a pipeline (scaler inside the fold) with the
# lab's own folds matches the lab to rounding; KFold blocks differ a
# little; and a scaler fitted on all rows before cross-validating (the
# leak of chapter 14) gives yet another set of numbers.
alphas = [0.01, 0.1, 1, 10, 100, 1000]
folds = np.arange(len(ys)) % 5
lab_best = lab1.select_alpha(Xs.tolist(), ys.tolist(), alphas, k=5)
pipe = make_pipeline(StandardScaler(), Ridge())
score = "neg_root_mean_squared_error"
grid = {"ridge__alpha": alphas}
same = GridSearchCV(pipe, grid, cv=PredefinedSplit(folds),
                    scoring=score).fit(Xs, ys)
blocks = GridSearchCV(pipe, grid, cv=KFold(5), scoring=score).fit(Xs, ys)
leaky = GridSearchCV(Ridge(), {"alpha": alphas},
                     cv=PredefinedSplit(folds), scoring=score).fit(Z, ys)
print("\n5-fold CV RMSE for ridge (lab folds: row i in fold i % 5)")
print("  alpha   lab        sklearn, same folds  KFold blocks"
      "  scaler outside")
for i, a in enumerate(alphas):
    cv = lab1.kfold_rmse(lambda Xt, yt, a=a: lab1.ridge_fit(Xt, yt, a),
                         Xs.tolist(), ys.tolist(), k=5)
    cells = [-g.cv_results_["mean_test_score"][i]
             for g in (same, blocks, leaky)]
    print(f"  {a:<7g} {cv:.6f}   {cells[0]:.6f}           "
          f"{cells[1]:.6f}      {cells[2]:.6f}")
print(f"  best alpha: lab {lab_best[0]}, same folds "
      f"{same.best_params_['ridge__alpha']}, KFold "
      f"{blocks.best_params_['ridge__alpha']}, scaler outside "
      f"{leaky.best_params_['alpha']}")

# ── 6. Gradient boosting (chapter 9) ─────────────────────────────────────
# Same recipe: start at mean(y), fit a depth-3 tree to the residuals,
# add lr times its predictions. Predict: the two agree closely, at the
# start exactly, but not to the last digit: when two splits have equal
# gain the lab takes the lowest feature index and sklearn takes whichever
# it meets first. HistGradientBoosting bins every feature into at most
# 255 buckets first, so it is a different algorithm and will differ more.
Xtr, ytr = lab2.make_friedman(seed=4, n=600)
Xte, yte = lab2.make_friedman(seed=5, n=2000)
Rounds, LR = 100, 0.1
t0 = time.perf_counter()
gb = lab2.fit_gbm(Xtr, ytr, n_rounds=Rounds, lr=LR, max_depth=3)
t_lab = time.perf_counter() - t0
p_lab = np.array(lab2.gbm_predict(gb, Xte))
t0 = time.perf_counter()
sk = GradientBoostingRegressor(
    n_estimators=Rounds, learning_rate=LR, max_depth=3,
    random_state=0).fit(Xtr, ytr)
t_sk = time.perf_counter() - t0
p_sk = sk.predict(Xte)
hist = HistGradientBoostingRegressor(
    max_iter=Rounds, learning_rate=LR, max_depth=3, max_leaf_nodes=None,
    min_samples_leaf=1, early_stopping=False, random_state=0)
hist.fit(Xtr, ytr)
p_hist = hist.predict(Xte)


def rm(p):
    return math.sqrt(float(np.mean((np.asarray(p) - yte) ** 2)))


print(f"\ngradient boosting on Friedman #1 (600 train, 2000 test, "
      f"noise floor 1.0)")
print(f"  {'model':26}{'test RMSE':>10}{'fit time':>10}")
print(f"  {'lab fit_gbm':26}{rm(p_lab):>10.4f}{t_lab:>9.2f}s")
print(f"  {'sklearn GradientBoosting':26}{rm(p_sk):>10.4f}{t_sk:>9.2f}s")
print(f"  {'sklearn HistGradientBoost':26}{rm(p_hist):>10.4f}")
print(f"  largest prediction difference, lab vs sklearn GB: "
      f"{worst(p_lab, p_sk):.2e}")
print(f"  largest prediction difference, lab vs Hist:       "
      f"{worst(p_lab, p_hist):.2e}")
f0 = gb.f0
print(f"  starting value: lab f0 = {f0:.6f}, "
      f"sklearn init mean = {float(np.mean(ytr)):.6f}")
stage = list(sk.staged_predict(Xte))
curve = lab2.staged_rmse(gb, Xte, yte)
print("  test RMSE after n rounds (lab / sklearn):")
for k in (1, 10, 50, 100):
    print(f"    {k:4d}  {curve[k - 1]:.4f} / {rm(stage[k - 1]):.4f}")
first = None
for i, t in enumerate(gb.trees):               # compare tree by tree
    tr = max(abs(lab2.predict_one(t, r) - v) for r, v in
             zip(Xtr, sk.estimators_[i, 0].predict(np.array(Xtr))))
    te = np.array([lab2.predict_one(t, r) for r in Xte])
    d = np.abs(te - sk.estimators_[i, 0].predict(np.array(Xte)))
    if d.max() > 1e-6 and first is None:
        first = (i + 1, tr, int((d > 1e-6).sum()), float(d.max()))
if first:
    print(f"  first tree that differs: number {first[0]}. On the "
          f"training rows the two trees agree to {first[1]:.1e}; on the "
          f"test rows they disagree on {first[2]} of {len(Xte)} "
          f"(by up to {first[3]:.2f})")
