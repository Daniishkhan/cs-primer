"""Self-check for Lab 1: Linear & Logistic Regression from Scratch.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY the dataset of seed 7

Every dataset is synthetic and generated from a seeded random.Random, so every run gives
identical numbers, and the whole check finishes in a couple of seconds. The oracles in this
file are deliberately independent of the functions you write: they test properties the
answer must have (the residuals are orthogonal to the columns, the lasso satisfies its
optimality conditions, a finite-difference gradient agrees) rather than comparing your code
with another copy of itself.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


def all_near(a, b, tol=1e-9):
    return len(a) == len(b) and all(near(x, y, tol) for x, y in zip(a, b))


def raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False


# ----- independent reference helpers (plain, and not the lesson) --------------------------------
def ref_mse(y, p):
    return sum((a - b) ** 2 for a, b in zip(y, p)) / len(y)


def ref_pred(X, th):
    return [th[0] + sum(t * v for t, v in zip(th[1:], row)) for row in X]


def ref_sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z)) if z > -700 else 0.0


def ref_logloss(y, p):
    return -sum(t * math.log(q) + (1 - t) * math.log(1 - q) for t, q in zip(y, p)) / len(y)


def ref_std(X):
    n = len(X)
    mu = [sum(c) / n for c in zip(*X)]
    sd = [math.sqrt(sum((v - m) ** 2 for v in c) / n) for c, m in zip(zip(*X), mu)]
    return mu, sd


def ref_z(X, mu, sd):
    return [[(v - m) / s for v, m, s in zip(r, mu, sd)] for r in X]


def norm(v):
    return math.sqrt(sum(x * x for x in v))


# =============================================================================
# Milestone 1: the closed form, from nothing
# =============================================================================
def m1():
    assert mod.dot([1, 2, 3], [4, 5, 6]) == 32, "dot([1,2,3],[4,5,6]) should be 32"
    M = [[1, 2, 3], [4, 5, 6]]
    assert mod.transpose(M) == [[1, 4], [2, 5], [3, 6]], f"transpose of a 2x3 matrix should be 3x2; got {mod.transpose(M)!r}"
    assert M == [[1, 2, 3], [4, 5, 6]], "transpose must not modify its input"
    assert mod.matmul([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[19, 22], [43, 50]], "matmul([[1,2],[3,4]],[[5,6],[7,8]]) should be [[19,22],[43,50]]"
    assert mod.matmul([[1, 2, 3], [4, 5, 6]], [[1], [0], [2]]) == [[7], [16]], "a (2,3) @ (3,1) product has shape (2,1)"

    x = mod.solve([[2, 1], [1, 3]], [3, 5])
    assert all_near(x, [0.8, 1.4]), f"solve([[2,1],[1,3]],[3,5]) should be [0.8, 1.4]; got {x}"
    x = mod.solve([[0, 1], [1, 0]], [2, 3])
    assert all_near(x, [3.0, 2.0]), ("solve([[0,1],[1,0]],[2,3]) has a zero in the first pivot position; swap rows first "
                                     f"(partial pivoting). Expected [3, 2], got {x}")
    A0, b0 = [[2.0, 1.0], [1.0, 3.0]], [3.0, 5.0]
    mod.solve(A0, b0)
    assert A0 == [[2.0, 1.0], [1.0, 3.0]] and b0 == [3.0, 5.0], "solve must not modify A or b (work on a copy)"
    assert raises(lambda: mod.solve([[1, 2], [2, 4]], [1, 2])), "a singular matrix ([[1,2],[2,4]]) must raise ValueError"
    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        n = rng.randint(2, 7)
        A = [[rng.uniform(-3, 3) for _ in range(n)] for _ in range(n)]
        b = [rng.uniform(-5, 5) for _ in range(n)]
        try:
            x = mod.solve(A, b)
        except ValueError:
            raise AssertionError(f"seed {s}: solve refused a random {n}x{n} matrix as singular; the pivot tolerance is too strict")
        res = max(abs(sum(a * v for a, v in zip(row, x)) - bi) for row, bi in zip(A, b))
        assert res < 1e-8, f"seed {s}: A x - b has an entry of size {res:.2e} for a {n}x{n} system; check the elimination"

    assert mod.add_intercept([[2, 3], [4, 5]]) == [[1.0, 2, 3], [1.0, 4, 5]], "add_intercept puts a 1.0 in front of every row"
    # the hand example of chapter 5: (1,2), (2,3), (3,5) -> slope 1.5, intercept 1/3
    th = mod.fit_ols([[1], [2], [3]], [2, 3, 5])
    assert all_near(th, [1 / 3, 1.5], 1e-9), f"the points (1,2),(2,3),(3,5) have intercept 1/3 and slope 1.5; got {th}"
    # a noiseless plane is recovered exactly
    rng = random.Random(3)
    Xp = [[rng.uniform(0, 5), rng.uniform(-2, 2), rng.uniform(10, 20)] for _ in range(12)]
    yp = [2 + 3 * a - b + 0.5 * c for a, b, c in Xp]
    th = mod.fit_ols(Xp, yp)
    assert all_near(th, [2, 3, -1, 0.5], 1e-7), f"noiseless y = 2 + 3a - b + 0.5c should be recovered exactly; got {[round(t, 6) for t in th]}"
    # ... and on noisy data the residuals are orthogonal to every column (that IS the normal equations)
    X, y = mod.make_rent(5)
    Xtr, ytr, Xte, yte = X[:150], y[:150], X[150:], y[150:]
    th = mod.fit_ols(Xtr, ytr)
    pred = mod.predict_linear(Xtr, th)
    assert all_near(pred, ref_pred(Xtr, th), 1e-9), "predict_linear should return theta[0] + theta[1:] . x for every row"
    res = [a - b for a, b in zip(ytr, pred)]
    scale = max(abs(r) for r in res)
    assert abs(sum(res)) < 1e-6 * scale * len(res), f"the residuals of a model with an intercept must sum to zero; got {sum(res):.3g}"
    for j, col in enumerate(zip(*Xtr)):
        c = sum(a * b for a, b in zip(col, res))
        assert abs(c) < 1e-6 * sum(abs(a * b) for a, b in zip(col, res)), (
            f"the residuals should be orthogonal to column {j}; their dot product is {c:.3g}. "
            "If this fails but the hand examples pass, check that A^T y uses the same A (with the ones column).")
    # metrics
    assert near(mod.mse([1, 2, 3], [1, 2, 5]), 4 / 3), "mse([1,2,3],[1,2,5]) should be 4/3"
    assert near(mod.r2([1, 2, 3], [1, 2, 3]), 1.0), "a perfect fit has R^2 = 1"
    assert near(mod.r2([1, 2, 3], [2, 2, 2]), 0.0), "predicting the mean has R^2 = 0"
    assert mod.r2([1, 2, 3], [3, 2, 1]) < 0, "a model worse than the mean has negative R^2"
    # the scenario: chapter 5's lettings data
    ybar = sum(ytr) / len(ytr)
    base = mod.rmse(yte, [ybar] * len(yte))
    test = mod.rmse(yte, mod.predict_linear(Xte, th))
    r2_te = mod.r2(yte, mod.predict_linear(Xte, th))
    assert test < 75 and base > 200, f"test RMSE should be near the noise level of 60 (got {test:.1f}); the baseline is {base:.1f}"
    assert r2_te > 0.9, f"test R^2 should exceed 0.9, got {r2_te:.3f}"
    assert abs(th[1] - 11) < 2 and abs(th[2] + 25) < 4 and abs(th[3] + 2) < 0.8, (
        f"the fitted weights should be near the truth (11, -25, -2); got {[round(t, 2) for t in th[1:]]}")
    # collinearity makes A^T A singular
    Xd = [[a, a] for a in (1.0, 2.0, 3.0, 4.0, 5.0)]
    assert raises(lambda: mod.fit_ols(Xd, [1, 3, 2, 5, 4])), (
        "two identical columns make A^T A singular, so fit_ols must raise ValueError (milestone 3's ridge repairs exactly this)")
    return (f"intercept/slope of the 3-point example: {mod.fit_ols([[1], [2], [3]], [2, 3, 5])[0]:.4f}, 1.5; solve() holds on 30 random systems\n"
            f"rent data (seed 5): weights {[round(t, 1) for t in th]}  (truth 300, 11, -25, -2)\n"
            f"test RMSE {test:.1f} against {base:.1f} for predicting the mean; R^2 {r2_te:.3f}")


# =============================================================================
# Milestone 2: gradient descent, and why feature scale matters
# =============================================================================
def m2():
    mu, sd = mod.column_stats([[1, 10], [3, 10], [5, 10]])
    assert all_near(mu, [3.0, 10.0]) and near(sd[0], math.sqrt(8 / 3)) and near(sd[1], 1.0), (
        f"column_stats([[1,10],[3,10],[5,10]]) should give means [3,10] and sds [sqrt(8/3), 1.0] "
        f"(population sd, and a constant column gets sd 1.0); got {mu}, {sd}")
    for s in seeds(range(1, 6)):
        rng = random.Random(s)
        X = [[rng.uniform(0, 100), rng.gauss(5, 0.01), rng.uniform(-1, 1)] for _ in range(40)]
        mu, sd = mod.column_stats(X)
        Z = mod.standardise(X, mu, sd)
        for j, col in enumerate(zip(*Z)):
            assert abs(sum(col) / 40) < 1e-9 and abs(sum(v * v for v in col) / 40 - 1) < 1e-9, (
                f"seed {s}: standardised column {j} should have mean 0 and mean square 1")
        assert mod.standardise([mu], mu, sd) == [[0.0, 0.0, 0.0]], "a row equal to the training mean standardises to zeros"

    X1, y1 = [[1.0], [2.0], [3.0]], [2.0, 3.0, 5.0]
    g = mod.mse_gradient(X1, y1, [0.0, 0.0])
    assert all_near(g, [-20 / 3, -46 / 3], 1e-9), (
        f"at theta = [0, 0] on (1,2),(2,3),(3,5) the MSE gradient is [-20/3, -46/3] = [-6.667, -15.333]; got {g}")
    for s in seeds(range(1, 21)):
        rng = random.Random(s)
        n, d = rng.randint(5, 30), rng.randint(1, 4)
        X = [[rng.gauss(0, 2) for _ in range(d)] for _ in range(n)]
        y = [rng.gauss(0, 3) for _ in range(n)]
        th = [rng.gauss(0, 1) for _ in range(d + 1)]
        num = mod.numeric_gradient(lambda t: ref_mse(y, ref_pred(X, t)), th)
        got = mod.mse_gradient(X, y, th)
        assert all_near(got, num, 1e-5), (f"seed {s}: the analytic gradient {[round(v, 5) for v in got]} disagrees with finite differences "
                                           f"{[round(v, 5) for v in num]} (the gradient is (2/n) A^T (A theta - y); did you drop the 2, the 1/n, or the intercept entry?)")

    th, hist = mod.gradient_descent(lambda t: (t[0] - 3) ** 2, lambda t: [2 * (t[0] - 3)], [0.0], 0.25, 4)
    assert len(hist) == 4 and near(hist[0], 9.0) and near(hist[1], 2.25) and near(th[0], 2.8125), (
        f"minimising (t-3)^2 from 0 with lr 0.25: history should start [9, 2.25, ...] and have one entry per step, theta after 4 steps 2.8125; "
        f"got history {hist}, theta {th}")
    t0 = [1.0, 2.0]
    mod.gradient_descent(lambda t: 0.0, lambda t: [1.0, 1.0], t0, 0.1, 3)
    assert t0 == [1.0, 2.0], "gradient_descent must not modify theta0"

    # chapter 5's experiment: the same problem, with and without standardising
    X, y = mod.make_rent(5)
    mu, sd = mod.column_stats(X)
    Z = mod.standardise(X, mu, sd)
    best = ref_mse(y, mod.predict_linear(Z, mod.fit_ols(Z, y)))     # the closed form from milestone 1
    th_s, h_s = mod.gd_linear(Z, y, 0.1, 400)
    assert len(h_s) == 400, "gd_linear should return one history entry per step"
    assert ref_mse(y, ref_pred(Z, th_s)) < best * 1.001, (
        f"on standardised features, lr 0.1 and 400 steps should reach the closed-form loss {best:.1f} (within 0.1%); "
        f"got {ref_mse(y, ref_pred(Z, th_s)):.1f}")
    assert all(b <= a + 1e-9 for a, b in zip(h_s, h_s[1:])), "with a stable step size the loss must never go up"
    first = next(i for i, v in enumerate(h_s) if v < best * 1.01)
    th_r, h_r = mod.gd_linear(X, y, 1e-4, 2000)
    assert h_r[-1] > 2 * best, (f"on raw features the same loss needs many more steps: after 2000 steps at lr 1e-4 the loss should "
                                f"still be above twice the minimum ({best:.0f}); got {h_r[-1]:.0f}")
    th_b, h_b = mod.gd_linear(X, y, 1e-3, 8)
    assert h_b[7] > 1e3 * h_b[0], (f"a step size of 1e-3 on raw features is past the stability limit, so the loss must explode; "
                                   f"got {[f'{v:.3g}' for v in h_b]}")
    return (f"standardised, lr 0.1: within 1% of the closed-form loss {best:.0f} after {first + 1} steps, within 0.1% by step 400\n"
            f"raw features, lr 1e-4: loss after 10/100/2000 steps = {h_r[9]:.0f} / {h_r[99]:.0f} / {h_r[-1]:.0f}\n"
            f"raw features, lr 1e-3: first losses {', '.join(f'{v:.3g}' for v in h_b[:4])}, ...  (diverges)")


# =============================================================================
# Milestone 3: ridge regression and choosing alpha by cross-validation
# =============================================================================
def m3():
    X1, y1 = [[1.0], [2.0], [3.0]], [2.0, 3.0, 5.0]
    m0 = mod.ridge_fit(X1, y1, 0.0)
    p = m0.predict([[4.0]])[0]
    assert near(p, 1 / 3 + 1.5 * 4, 1e-9), f"alpha = 0 is ordinary least squares: the line 1/3 + 1.5 x predicts 6.333 at x=4; got {p}"
    m3_ = mod.ridge_fit(X1, y1, 3.0)
    assert near(m3_.y_mean, 10 / 3) and near(m3_.w[0], 3.674234614174767 / 6, 1e-9), (
        "one feature, alpha = 3: w = (z . (y - ybar)) / (z . z + alpha) = 3.6742 / 6 = 0.6124 on the standardised column; "
        f"got w = {m3_.w}")
    assert near(mod.ridge_fit(X1, y1, 1e12).predict([[7.0]])[0], 10 / 3, 1e-6), "a huge alpha shrinks every weight to zero, so the model predicts mean(y)"

    for s in seeds(range(1, 5)):
        X, y = mod.make_rent(s, 80)
        mu, sd = ref_std(X)
        Z = ref_z(X, mu, sd)
        ybar = sum(y) / len(y)
        yc = [v - ybar for v in y]
        norms = []
        for a in (0.0, 1.0, 10.0, 100.0, 1000.0):
            m = mod.ridge_fit(X, y, a)
            # the penalised normal equations, checked from the outside
            for j in range(3):
                lhs = sum(sum(Z[i][j] * Z[i][k] * m.w[k] for k in range(3)) for i in range(80)) + a * m.w[j]
                rhs = sum(Z[i][j] * yc[i] for i in range(80))
                assert abs(lhs - rhs) < 1e-6 * (1 + abs(rhs)), (
                    f"seed {s}, alpha {a}: (Z^T Z + alpha I) w should equal Z^T (y - mean y); entry {j} is {lhs:.4f} against {rhs:.4f}")
            tp = m.predict(X)
            assert abs(sum(tp) / len(tp) - ybar) < 1e-6 * (1 + abs(ybar)), (
                f"seed {s}, alpha {a}: the mean prediction on the training rows should equal mean(y) (the intercept is not penalised)")
            norms.append(norm(m.w))
        assert all(b < a for a, b in zip(norms, norms[1:])), (
            f"seed {s}: the weight vector must shrink strictly as alpha grows; its norms at alpha 0, 1, 10, 100, 1000 were {[round(v, 2) for v in norms]}")
        # units must not matter once the columns are standardised
        scaled = [[r[0] * 1000.0, r[1], r[2] / 10.0] for r in X]
        pa = mod.ridge_fit(X, y, 50.0).predict(X)
        pb = mod.ridge_fit(scaled, y, 50.0).predict(scaled)
        assert all_near(pa, pb, 1e-6), (f"seed {s}: measuring area in different units must not change a ridge model's predictions; "
                                        "you probably forgot to standardise before penalising")
    # to_original agrees with predict
    m = mod.ridge_fit(*mod.make_rent(2, 60), 5.0)
    Xq = mod.make_rent(9, 10)[0]
    assert all_near(m.predict(Xq), ref_pred(Xq, m.to_original()), 1e-6), "to_original() must describe the same model in raw units"

    # collinearity: OLS breaks, ridge splits the weight equally
    rng = random.Random(4)
    base = [rng.gauss(0, 1) for _ in range(30)]
    Xd = [[v, v, rng.gauss(0, 1)] for v in base]
    yd = [2 * r[0] + r[2] + rng.gauss(0, 0.1) for r in Xd]
    assert raises(lambda: mod.ridge_fit(Xd, yd, 0.0)), "alpha = 0 with two identical columns is singular: raise ValueError (via solve)"
    md = mod.ridge_fit(Xd, yd, 1.0)
    assert near(md.w[0], md.w[1], 1e-9) and md.w[0] > 0.5, (
        f"with alpha > 0 the duplicated columns are fine, and ridge shares the weight equally between them; got {md.w[:2]}")

    # k-fold: the folds are i % k, and each fold trains on the rest
    seen = []

    class Spy:
        def __init__(self, ytr):
            self.m = sum(ytr) / len(ytr)

        def predict(self, X):
            return [self.m] * len(X)

    def spy_fit(Xt, yt):
        seen.append(len(yt))
        return Spy(yt)

    Xk = [[float(i)] for i in range(10)]
    yk = [float(i) for i in range(10)]
    score = mod.kfold_rmse(spy_fit, Xk, yk, 5)
    exp = 0.0
    for f in range(5):
        tr = [yk[i] for i in range(10) if i % 5 != f]
        va = [yk[i] for i in range(10) if i % 5 == f]
        mm = sum(tr) / len(tr)
        exp += math.sqrt(sum((v - mm) ** 2 for v in va) / len(va))
    assert seen == [8] * 5, f"5-fold CV on 10 rows should fit 5 times on 8 rows each; fit sizes were {seen}"
    assert near(score, exp / 5, 1e-9), f"kfold_rmse is the mean of the five per-fold RMSEs ({exp / 5:.4f}); got {score:.4f}"

    # the scenario: degree-12 polynomial on 18 noisy sine points
    alphas = [1e-4, 1e-3, 1e-2, 0.1, 0.3, 1, 3, 10, 30, 100]
    note = []
    for s in seeds((1, 2, 3)):
        Xtr, ytr = mod.make_sine(s, 18)
        Xte, yte = mod.make_sine(500 + s, 1000)
        ols = mod.rmse(yte, mod.ridge_fit(Xtr, ytr, 0.0).predict(Xte))
        a, cv = mod.select_alpha(Xtr, ytr, alphas)
        rid = mod.rmse(yte, mod.ridge_fit(Xtr, ytr, a).predict(Xte))
        trn = mod.rmse(ytr, mod.ridge_fit(Xtr, ytr, 0.0).predict(Xtr))
        assert trn < 0.3, f"seed {s}: unpenalised, 13 parameters on 18 points should fit the training rows to below the noise level 0.3; got {trn:.3f}"
        assert ols > 3, f"seed {s}: unpenalised test RMSE should explode (above 3); got {ols:.3f}. Is alpha=0 really unpenalised?"
        assert a < alphas[-1] and a > alphas[0] and rid < 0.8, (
            f"seed {s}: cross-validation should choose a middling alpha with a test RMSE under 0.8; chose {a} with test RMSE {rid:.3f}")
        note.append(f"seed {s}: OLS test RMSE {ols:8.2f}   ridge (CV picks alpha {a:g}) test RMSE {rid:.3f}   (noise floor 0.30)")
    assert mod.select_alpha(Xtr, ytr, [1.0, 1.0, 1.0])[0] == 1.0
    return "\n".join(note)


# =============================================================================
# Milestone 4: the lasso, by coordinate descent
# =============================================================================
def m4():
    st = mod.soft_threshold
    for r, t, want in [(3, 1, 2), (-3, 1, -2), (0.5, 1, 0), (-0.5, 1, 0), (1, 1, 0), (2, 0, 2), (-2, 0, -2), (0, 0.3, 0)]:
        assert near(st(r, t), want), f"soft_threshold({r}, {t}) should be {want}; got {st(r, t)}"

    X1, y1 = [[1.0], [2.0], [3.0]], [2.0, 3.0, 5.0]
    rho = 3.674234614174767 / 3                      # (1/n) z . (y - ybar) for the standardised column
    assert near(mod.alpha_max(X1, y1), rho, 1e-9), f"alpha_max for the 3-point example is {rho:.4f}; got {mod.alpha_max(X1, y1)}"
    w = mod.lasso_fit(X1, y1, 0.5).w[0]
    assert near(w, rho - 0.5, 1e-7), f"one feature: w = soft_threshold(rho, alpha) = {rho:.4f} - 0.5 = {rho - 0.5:.4f}; got {w}"
    assert mod.lasso_fit(X1, y1, 2.0).w == [0.0], "alpha above alpha_max must give exactly zero (not 1e-17)"

    note = []
    for s in seeds((3, 4, 5)):
        X, y, support = mod.make_sparse(s)
        n = len(y)
        mu, sd = ref_std(X)
        Z = ref_z(X, mu, sd)
        ybar = sum(y) / n
        amax = mod.alpha_max(X, y)
        mu_ok = max(abs(sum(c) / n) for c in zip(*Z))
        assert mu_ok < 1e-9
        assert all(abs(v) == 0.0 for v in mod.lasso_fit(X, y, amax * 1.0001).w), f"seed {s}: just above alpha_max every weight must be exactly 0"
        assert any(abs(v) > 0 for v in mod.lasso_fit(X, y, amax * 0.999).w), f"seed {s}: just below alpha_max one weight must switch on"
        l1 = []
        for a in (0.05, 0.2, 0.5, 1.0, 2.0):
            m = mod.lasso_fit(X, y, a)
            resid = [yi - ybar - sum(wj * zij for wj, zij in zip(m.w, zi)) for yi, zi in zip(y, Z)]
            for j in range(len(m.w)):
                grad = sum(Z[i][j] * resid[i] for i in range(n)) / n          # = -d/dw_j of the smooth part
                if m.w[j] != 0:
                    assert abs(grad - a * (1 if m.w[j] > 0 else -1)) < 1e-5, (
                        f"seed {s}, alpha {a}: feature {j} has weight {m.w[j]:.4f}, so its correlation with the residual should "
                        f"equal alpha = {a} (optimality); it is {grad:.5f}. Keep sweeping until no weight moves, and use "
                        "rho = (1/n) z.r + w_j before the soft-threshold")
                else:
                    assert abs(grad) <= a + 1e-5, (
                        f"seed {s}, alpha {a}: feature {j} is held at zero but its correlation with the residual is {grad:.4f}, "
                        f"above alpha; the weight should have switched on")
            l1.append(sum(abs(v) for v in m.w))
        assert all(b <= a + 1e-9 for a, b in zip(l1, l1[1:])), f"seed {s}: the L1 norm of the solution must not grow with alpha; {[round(v, 3) for v in l1]}"
        ols = mod.lasso_fit(X, y, 0.0)
        ref = mod.fit_ols(X, y)
        assert all_near(ols.predict(X), ref_pred(X, ref), 2e-3), f"seed {s}: lasso with alpha = 0 should converge to ordinary least squares"
        Xt, yt, _ = mod.make_sparse(900 + s)
        las = mod.lasso_fit(X, y, 0.3)
        keep = [j for j, v in enumerate(las.w) if v != 0]
        err_l, err_o = mod.rmse(yt, las.predict(Xt)), mod.rmse(yt, ols.predict(Xt))
        rid = mod.ridge_fit(X, y, 60.0)
        assert all(v != 0 for v in rid.w), "ridge never produces exact zeros"
        assert set(support) <= set(keep) and len(keep) <= 14, (
            f"seed {s}: at alpha 0.3 the lasso should keep all five real signals {support} and drop at least six noise columns; kept {keep}")
        assert err_l < err_o, f"seed {s}: the sparse model should beat plain least squares on fresh data ({err_l:.2f} vs {err_o:.2f})"
        note.append(f"seed {s}: alpha_max {amax:.2f}; at alpha 0.3 kept {len(keep)} of 20 features {keep[:8]}{'...' if len(keep) > 8 else ''}"
                    f"  test RMSE {err_l:.2f} (OLS {err_o:.2f}, noise floor 3.00)")
    return "\n".join(note)


# =============================================================================
# Milestone 5: the sigmoid, log-loss and the logistic gradient
# =============================================================================
def m5():
    sg = mod.sigmoid
    assert near(sg(0), 0.5) and near(sg(2), 0.8807970779778823) and near(sg(-2), 0.11920292202211755), "sigmoid(0)=0.5, sigmoid(2)=0.8808, sigmoid(-2)=0.1192"
    for z in (0.3, 1.7, 5.0, 12.0, 30.0):
        assert near(sg(-z), 1 - sg(z), 1e-12), f"sigmoid(-{z}) should equal 1 - sigmoid({z})"
    try:
        lo, hi, mid = sg(-1000.0), sg(1000.0), sg(-745.0)
    except OverflowError:
        raise AssertionError("sigmoid overflowed: math.exp(1000) is too big. Use e^z/(1+e^z) for negative z and 1/(1+e^-z) otherwise")
    assert lo == 0.0 and hi == 1.0 and mid >= 0.0, f"sigmoid(-1000) should be 0.0 and sigmoid(1000) should be 1.0; got {lo}, {hi}"

    ll = mod.log_loss
    assert near(ll([1, 0], [0.9, 0.1]), -math.log(0.9), 1e-12), "log_loss([1,0],[0.9,0.1]) is -ln 0.9 = 0.10536"
    assert near(ll([1], [0.01]), -math.log(0.01), 1e-12), "predicting 0.01 for something that happens costs -ln 0.01 = 4.605"
    assert near(ll([1], [0.4]), 0.916290731874155, 1e-9) and near(ll([0], [0.4]), 0.5108256237659907, 1e-9), "p = 0.4: -ln 0.4 = 0.916 if y=1, -ln 0.6 = 0.511 if y=0"
    base = ll([1, 1, 0, 0, 0], [0.4] * 5)
    assert near(base, -(0.4 * math.log(0.4) + 0.6 * math.log(0.6)), 1e-12), f"the base-rate model on a 40% rate costs the entropy 0.673; got {base}"
    clipped = ll([1], [0.0])
    assert near(clipped, -math.log(1e-12), 1e-3) and near(ll([0], [1.0]), -math.log(1e-12), 1e-3), (
        "p = 0 or 1 must be clipped into [1e-12, 1 - 1e-12] so a confident mistake costs about 27.6, not infinity or a crash")
    assert ll([1, 0], [1.0, 0.0]) < 1e-11, "perfect, confident predictions cost almost nothing"

    assert all_near(mod.predict_proba([[5.0]], [math.log(3), 0.0]), [0.75]), "theta = [ln 3, 0]: log-odds ln 3 means odds 3 to 1, probability 0.75"
    assert all_near(mod.predict_proba([[2.0, 2.0]], [0.0, 1.0, -1.0]), [0.5]), "x = [2, 2] with weights [1, -1] has z = 0"

    g = mod.logistic_gradient([[0.0], [1.0]], [0.0, 1.0], [0.0, 0.0])
    assert all_near(g, [0.0, -0.25]), f"at theta = [0,0] on x=(0,1), y=(0,1): p = 0.5, errors (0.5, -0.5): gradient [0, -0.25]; got {g}"
    g = mod.logistic_gradient([[0.0], [1.0]], [0.0, 1.0], [0.0, 2.0], l2=1.0)
    want = [(0.5 + (sg(2) - 1)) / 2, (sg(2) - 1) / 2 + 2.0]
    assert all_near(g, want, 1e-9), f"with l2 = 1 the slope entry gains l2 * w = 2 but the intercept entry gains nothing: expected {want}; got {g}"
    for s in seeds(range(1, 21)):
        rng = random.Random(s)
        n, d = rng.randint(6, 40), rng.randint(1, 4)
        X = [[rng.gauss(0, 1.5) for _ in range(d)] for _ in range(n)]
        y = [float(rng.random() < 0.5) for _ in range(n)]
        th = [rng.gauss(0, 1) for _ in range(d + 1)]
        l2 = rng.choice([0.0, 0.3])

        def loss(t):
            return ref_logloss(y, [ref_sigmoid(t[0] + sum(a * b for a, b in zip(t[1:], r))) for r in X]) + 0.5 * l2 * sum(v * v for v in t[1:])

        num = mod.numeric_gradient(loss, th)
        got = mod.logistic_gradient(X, y, th, l2)
        assert all_near(got, num, 1e-5), (f"seed {s}, l2={l2}: analytic {[round(v, 5) for v in got]} vs finite differences {[round(v, 5) for v in num]}. "
                                           "The gradient of log-loss is (1/n) A^T (p - y): no factor 2, and (p - y) not (y - p)")
    assert near(mod.odds_ratio(0.0), 1.0) and near(mod.odds_ratio(math.log(2)), 2.0), "odds_ratio(w) = e^w: w = 0 changes nothing, w = ln 2 doubles the odds"
    return (f"sigmoid, log-loss ({-math.log(0.9):.4f} for p = 0.9), the clipped cost of a confident mistake ({clipped:.1f}) and the gradient "
            "agree with hand values and with finite differences on 20 random problems")


# =============================================================================
# Milestone 6: fitting logistic regression, with and without a penalty
# =============================================================================
def m6():
    note = []
    for k, s in enumerate(seeds((11, 12, 13))):
        X, y = mod.make_churn(s, 700)
        Xtr, ytr, Xte, yte = X[:500], y[:500], X[500:], y[500:]
        m = mod.fit_logistic(Xtr, ytr)
        p_tr, p_te = m.predict_proba(Xtr), m.predict_proba(Xte)
        rate = sum(ytr) / len(ytr)
        mu, sd = ref_std(Xtr)
        Z = ref_z(Xtr, mu, sd)
        # converged: the gradient of the mean log-loss is (almost) zero at the answer
        n = len(ytr)
        err = [p - t for p, t in zip(p_tr, ytr)]
        gmax = max([abs(sum(err) / n)] + [abs(sum(c * e for c, e in zip(col, err)) / n) for col in zip(*Z)])
        assert gmax < 2e-3, f"seed {s}: not converged: the log-loss gradient at your answer has an entry of size {gmax:.4f} (expected below 0.002 after 400 steps at lr 0.5)"
        # a property of the intercept: at the optimum the average predicted probability equals the base rate
        assert abs(sum(p_tr) / n - rate) < 1e-3, f"seed {s}: mean predicted probability {sum(p_tr) / n:.4f} should equal the training churn rate {rate:.4f}"
        ll_m, ll_b = ref_logloss(yte, p_te), ref_logloss(yte, [rate] * len(yte))
        assert ll_m < ll_b - 0.04, f"seed {s}: test log-loss {ll_m:.3f} should beat the base-rate model's {ll_b:.3f} by a clear margin"
        o = m.to_original()
        assert all_near(mod.predict_proba(Xte, o), p_te, 1e-9), "to_original() must describe the same model in raw units"
        w = m.theta[1:]
        assert w[0] < 0 < w[1] and w[2] > 0, f"seed {s}: churn should fall with tenure and rise with spend and tickets; weights per SD: {[round(v, 2) for v in w]}"
        acc = sum((p >= 0.5) == (t == 1.0) for p, t in zip(p_te, yte)) / len(yte)
        norms = [norm(mod.fit_logistic(Xtr, ytr, l2=l).theta[1:]) for l in (0.0, 0.01, 0.1, 1.0)]
        assert all(b < a for a, b in zip(norms, norms[1:])), f"seed {s}: a larger l2 must shrink the weights; norms {[round(v, 3) for v in norms]}"
        big = mod.fit_logistic(Xtr, ytr, l2=5.0, lr=0.2)
        assert norm(big.theta[1:]) < 0.1 and abs(sum(big.predict_proba(Xte)) / len(yte) - rate) < 0.05, (
            f"with a heavy penalty (l2 = 5) the model should be nearly the base rate for everyone; weight norm {norm(big.theta[1:]):.3f}")
        if k == 0:
            tn = ["tenure", "spend", "tickets"]
            note.append(f"seed {s}: log-loss on 200 test rows: base rate {ll_b:.3f}, logistic {ll_m:.3f};  accuracy at 0.5: {acc:.3f} (always 'stays': {sum(1 for t in yte if t == 0) / len(yte):.3f})")
            note.append("          " + "   ".join(f"{k}: weight/SD {v:+.2f} (odds x{mod.odds_ratio(v):.2f})" for k, v in zip(tn, w)))
        else:
            note.append(f"seed {s}: log-loss base {ll_b:.3f} -> logistic {ll_m:.3f}; weights/SD {[round(v, 2) for v in w]}")

    # perfect separation: the penalty-free optimum is at infinity
    Xs, ys = mod.make_separable(2)
    a400, a2000 = mod.fit_logistic(Xs, ys, 0.0, 0.5, 400), mod.fit_logistic(Xs, ys, 0.0, 0.5, 2000)
    n400, n2000 = norm(a400.theta[1:]), norm(a2000.theta[1:])
    acc = sum((p >= 0.5) == (t == 1.0) for p, t in zip(a2000.predict_proba(Xs), ys)) / len(ys)
    assert acc == 1.0, "separable data should be classified perfectly"
    assert n2000 > 1.3 * n400, (f"unpenalised, the weights on separable data should keep growing (norm {n400:.2f} at 400 steps, "
                                f"{n2000:.2f} at 2000: it should grow by more than 30%)")
    r400, r2000 = mod.fit_logistic(Xs, ys, 0.1, 0.5, 400), mod.fit_logistic(Xs, ys, 0.1, 0.5, 2000)
    assert abs(norm(r400.theta[1:]) - norm(r2000.theta[1:])) < 1e-3, "with l2 = 0.1 the weights should settle: 400 and 2000 steps agree"
    mu, sd = ref_std(Xs)
    Zs = ref_z(Xs, mu, sd)
    gp = mod.logistic_gradient(Zs, ys, r2000.theta, 0.1)
    assert max(abs(v) for v in gp) < 1e-4, f"the penalised gradient should be zero at the penalised optimum; largest entry {max(abs(v) for v in gp):.2e}"
    assert all((p >= 0.5) == (t == 1.0) for p, t in zip(r2000.predict_proba(Xs), ys)), "the penalised model still separates the classes"
    pr = r2000.predict_proba(Xs)
    note.append(f"separable data: weight norm without a penalty {n400:.2f} (400 steps) -> {n2000:.2f} (2000 steps), still growing;")
    note.append(f"                with l2 = 0.1 it settles at {norm(r2000.theta[1:]):.3f}; most confident probability {max(max(pr), 1 - min(pr)):.3f}")
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: the closed form, from nothing", m1),
    (2, "Milestone 2: gradient descent, and why feature scale matters", m2),
    (3, "Milestone 3: ridge regression and choosing alpha by cross-validation", m3),
    (4, "Milestone 4: the lasso, by coordinate descent", m4),
    (5, "Milestone 5: the sigmoid, log-loss and the logistic gradient", m5),
    (6, "Milestone 6: fitting logistic regression, with and without a penalty", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
