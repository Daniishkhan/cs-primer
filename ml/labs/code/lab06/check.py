"""Self-check for Lab 6: Feature Pipelines & Stacking.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 2     # milestone 4, replaying ONLY seed 2

Every dataset is synthetic and drawn from a seeded random.Random, so every run gives identical numbers and the
whole check finishes in well under a minute. The oracles in this file are deliberately independent of the
functions you write: a brute-force target encoding that recounts every row's own fold-out statistics, a LEAK
TEST that flips one label and asks which encoded values moved (an out-of-fold value must never move when its own
fold's labels change), spy models that record exactly which rows they were trained on and asked to predict, and
scenarios in which a leaky pipeline looks wonderful and an honest one tells the truth. Prints a tick, a cross,
or "not implemented yet" for each milestone.
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
START = time.time()


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
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def brute_oof(cats, y, folds, m):
    """Independent oracle: recount every row's encoding from the rows outside its own fold."""
    out = [None] * len(y)
    for fold in folds:
        inside = set(fold)
        other = [i for i in range(len(y)) if i not in inside]
        prior = sum(y[i] for i in other) / len(other)
        for i in fold:
            rows = [j for j in other if cats[j] == cats[i]]
            n = len(rows)
            out[i] = (sum(y[j] for j in rows) + m * prior) / (n + m) if n + m > 0 else prior
    return out


def numeric_cv_auc(X, y, folds):
    """Cross-validated AUC of the logistic regression on the numeric columns alone."""
    aucs = []
    for fold in folds:
        held = set(fold)
        tr = [i for i in range(len(y)) if i not in held]
        s = mod.fit_logreg([X[i] for i in tr], [y[i] for i in tr])([X[i] for i in fold])
        aucs.append(mod.roc_auc(s, [y[i] for i in fold]))
    return sum(aucs) / len(aucs)


def leaky_cv_auc(X, cats, y, folds, m=10.0):
    """The classic mistake: encode every row with statistics from ALL rows (its own label included), then
    cross-validate. Written here with the learner's M1 functions so the comparison is fair."""
    table, prior = mod.smoothed_means(cats, y, m)
    enc = mod.encode(table, prior, cats)
    return numeric_cv_auc([list(r) + [e] for r, e in zip(X, enc)], y, folds)


# =============================================================================
# Milestone 1: smoothed target encoding
# =============================================================================
def m1():
    cats, y = ["a", "a", "a", "b"], [1, 1, 0, 0]
    table, prior = mod.smoothed_means(cats, y, 20)
    assert near(prior, 0.5), f"prior is the overall mean of y: 2 positives in 4 rows = 0.5; got {prior}"
    assert near(table["a"], 12 / 23) and near(table["b"], 10 / 21), \
        f"m = 20: level a has 3 rows and 2 positives, so (2 + 20 x 0.5) / (3 + 20) = 0.5217; level b has 1 row and 0 positives, (0 + 10) / 21 = 0.4762; got {table}"
    table, prior = mod.smoothed_means(cats, y, 0)
    assert near(table["a"], 2 / 3) and near(table["b"], 0.0), f"m = 0 is the raw level mean: a = 0.667, b = 0; got {table}"
    assert set(table) == {"a", "b"}, "the table has one entry per level seen"
    out = mod.encode({"a": 0.2, "b": 0.7}, 0.5, ["b", "a", "zzz", "b"])
    assert out == [0.7, 0.2, 0.5, 0.7], f"encode looks levels up in order and gives an unseen level the prior; expected [0.7, 0.2, 0.5, 0.7], got {out}"
    assert mod.encode({}, 0.3, []) == [], "no rows in, no values out"
    for seed in seeds(range(30)):
        rng = random.Random(seed)
        n = rng.randint(5, 60)
        cats = [rng.choice("abcdefg") for _ in range(n)]
        y = [1 if rng.random() < 0.3 else 0 for _ in range(n)]
        if sum(y) == 0:
            y[0] = 1
        m = rng.choice([0, 1, 5, 20, 100])
        table, prior = mod.smoothed_means(cats, y, m)
        for lvl in set(cats):
            rows = [t for c, t in zip(cats, y) if c == lvl]
            mu = sum(rows) / len(rows)
            want = (len(rows) * mu + m * prior) / (len(rows) + m)
            assert near(table[lvl], want), f"seed {seed}, level {lvl}: ({len(rows)} x {mu:.3f} + {m} x {prior:.3f}) / ({len(rows)} + {m}) = {want:.4f}; got {table[lvl]:.4f}"
            lo, hi = min(mu, prior), max(mu, prior)
            assert lo - 1e-12 <= table[lvl] <= hi + 1e-12, f"seed {seed}: a smoothed value lies between the level mean and the prior"
    return "hand values (m = 20: 0.5217 and 0.4762), m = 0 is the raw mean, unseen levels get the prior, and 30 seeded tables against a recount"


# =============================================================================
# Milestone 2: out-of-fold target encoding
# =============================================================================
def m2():
    cats = ["a", "a", "b", "b", "a", "b"]
    y = [1, 0, 1, 1, 0, 0]
    folds = [[0, 1], [2, 3], [4, 5]]
    got = mod.oof_encode(cats, y, folds, 0)
    want = [0.0, 0.0, 0.0, 0.0, 0.5, 1.0]
    assert len(got) == 6 and all(near(a, b) for a, b in zip(got, want)), \
        f"m = 0, three folds. Fold 0 (rows 0, 1, both a) learns from rows 2 to 5 where a has one row, label 0, so both get 0.0; fold 1 (b, b) learns a from rows 0, 1, 4, 5 where b is 0 of 1, so 0.0; fold 2: a is 1 of 2 = 0.5, b is 2 of 2 = 1.0. Expected {want}, got {[round(v, 4) for v in got]}"
    for seed in seeds(range(20)):
        rng = random.Random(seed)
        n = rng.randint(20, 80)
        cats = [rng.choice("abcdefghij") for _ in range(n)]
        y = [1 if rng.random() < 0.35 else 0 for _ in range(n)]
        k = rng.choice([2, 3, 5])
        folds = mod.kfold_folds(n, k, seed)
        m = rng.choice([0, 3, 20])
        got = mod.oof_encode(cats, y, folds, m)
        want = brute_oof(cats, y, folds, m)
        assert all(near(a, b) for a, b in zip(got, want)), \
            f"seed {seed} (k = {k}, m = {m}): row {next(i for i in range(n) if not near(got[i], want[i]))} should be encoded from the rows outside its fold only: expected {[round(v, 3) for v in want][:6]}..., got {[round(v, 3) for v in got][:6]}..."
    # the leak test: flip one label and see which encoded values move
    rng = random.Random(7)
    n = 120
    cats = [f"c{rng.randrange(12)}" for _ in range(n)]
    y = [1 if rng.random() < 0.4 else 0 for _ in range(n)]
    folds = mod.kfold_folds(n, 5, 3)
    fold_of = {i: j for j, f in enumerate(folds) for i in f}
    base = mod.oof_encode(cats, y, folds, 5)
    moved_elsewhere = 0
    for i in rng.sample(range(n), 12):
        y2 = list(y)
        y2[i] = 1 - y2[i]
        new = mod.oof_encode(cats, y2, folds, 5)
        for j in range(n):
            if fold_of[j] == fold_of[i]:
                assert near(new[j], base[j], 1e-12), \
                    f"LEAK: flipping the label of row {i} changed the encoding of row {j}, which is in the same fold. A row's encoding (and its fold-mates') must be built from the other folds only."
            elif not near(new[j], base[j], 1e-12):
                moved_elsewhere += 1
    assert moved_elsewhere > 0, "flipping labels changed nothing in the other folds either: the encoding should still learn from them"
    # the scenario: how much label does each encoding carry?
    lines = []
    for signal in (False, True):
        for seed in seeds(range(3)):
            X, cats, y = mod.make_applications(1500, seed, signal=signal)
            folds = mod.kfold_folds(len(y), 5, 0)
            table, prior = mod.smoothed_means(cats, y, 2.0)
            naive = mod.roc_auc(mod.encode(table, prior, cats), y)
            oof = mod.roc_auc(mod.oof_encode(cats, y, folds, 2.0), y)
            if not signal:
                assert naive > 0.68, f"seed {seed}: on 1,500 rows of PURE-NOISE postcodes the in-sample encoding should look informative (AUC about 0.75) because it contains the labels; got {naive:.3f}"
                assert abs(oof - 0.5) < 0.08, f"seed {seed}: the out-of-fold encoding of pure noise must score about 0.5; got {oof:.3f}"
            else:
                assert 0.56 < oof < naive, f"seed {seed}: with real postcode effects the honest encoding should find signal (about 0.62) and still score below the leaky one ({naive:.3f}); got {oof:.3f}"
            if seed == seeds(range(3))[0]:
                lines.append(f"{'noise postcodes' if not signal else 'real postcode effects':<22} AUC of the encoding alone: in-sample {naive:.3f}, out-of-fold {oof:.3f}")
    return ("hand folds, 20 seeded cases against a brute-force recount, and a label-flip leak test (12 flips, none moves a fold-mate)\n"
            + "\n".join(lines))


# =============================================================================
# Milestone 3: a leak-safe pipeline inside cross-validation
# =============================================================================
def m3():
    X, cats, y = mod.make_applications(900, 4, signal=True)
    Xtr, ctr, ytr = X[:700], cats[:700], y[:700]
    Xte, cte = X[700:], cats[700:]
    cte = list(cte)
    cte[0] = "pc999"                                           # a postcode the training rows never saw
    full = mod.pipeline_predict(Xtr, ctr, ytr, Xte, cte)
    assert len(full) == len(Xte) and all(0.0 < v < 1.0 for v in full), "one probability in (0, 1) per test row (an unseen postcode must not crash)"
    part = mod.pipeline_predict(Xtr, ctr, ytr, Xte[:40], cte[:40])
    assert all(near(a, b, 1e-12) for a, b in zip(full[:40], part)), \
        "a test row's prediction must not depend on the OTHER test rows: the first 40 predictions changed when 160 more rows were scored. Does something use statistics of the test set?"
    again = mod.pipeline_predict(Xtr, ctr, ytr, Xte, cte)
    assert all(near(a, b, 1e-12) for a, b in zip(full, again)), "same inputs must give the same predictions (fixed seed for the folds)"
    rows = []
    for seed in seeds(range(3)):
        X, cats, y = mod.make_applications(1500, 10 + seed, signal=False)
        folds = mod.kfold_folds(len(y), 5, 0)
        num = numeric_cv_auc(X, y, folds)
        honest = mod.cv_auc(X, cats, y, folds)
        leaky = leaky_cv_auc(X, cats, y, folds)
        assert abs(honest - num) < 0.03, f"seed {seed}, noise postcodes: an honest pipeline learns nothing from them, so its AUC should match the numeric-only {num:.3f}; got {honest:.3f}"
        assert leaky > honest + 0.05, f"seed {seed}: (checker) the leaky version should look at least 0.05 better than the truth; leaky {leaky:.3f}, honest {honest:.3f}"
        X2, cats2, y2 = mod.make_applications(1500, 20 + seed, signal=True)
        num2 = numeric_cv_auc(X2, y2, folds)
        honest2 = mod.cv_auc(X2, cats2, y2, folds)
        leaky2 = leaky_cv_auc(X2, cats2, y2, folds)
        assert honest2 > num2 + 0.02, f"seed {seed}, real postcode effects: the encoding should add at least 0.02 AUC over numeric-only {num2:.3f}; got {honest2:.3f}"
        assert leaky2 > honest2 + 0.04, f"seed {seed}: (checker) the leaky version overstates even a real signal; leaky {leaky2:.3f}, honest {honest2:.3f}"
        rows.append((num, honest, leaky, num2, honest2, leaky2))
    r = rows[0]
    return ("an unseen postcode, no dependence on the other test rows, determinism, and honest versus leaky cross-validation on 3 seeds each\n"
            f"cross-validated AUC            numeric only   honest pipeline   leaky pipeline\n"
            f"  noise postcodes                 {r[0]:.3f}          {r[1]:.3f}            {r[2]:.3f}\n"
            f"  real postcode effects           {r[3]:.3f}          {r[4]:.3f}            {r[5]:.3f}")


# =============================================================================
# Milestone 4: out-of-fold predictions
# =============================================================================
def m4():
    n = 23
    X = [[float(i)] for i in range(n)]
    y = [i % 2 for i in range(n)]
    folds = mod.kfold_folds(n, 4, 6)
    calls = []

    def spy(Xtr, ytr, Xnew):
        calls.append((sorted(int(r[0]) for r in Xtr), sorted(int(r[0]) for r in Xnew)))
        assert len(Xtr) == len(ytr), "fit_predict was handed X and y of different lengths"
        assert all(ytr[j] == int(Xtr[j][0]) % 2 for j in range(len(Xtr))), "labels must travel with their rows"
        mean = sum(ytr) / len(ytr)
        return [mean + int(r[0]) * 1e-3 for r in Xnew]       # a score that also says which row it was made for

    out = mod.oof_predictions(spy, X, y, folds)
    assert len(calls) == 4, f"fit_predict should be called once per fold (4 times); got {len(calls)}"
    for (tr, new), fold in zip(calls, folds):
        assert new == sorted(fold), f"each call predicts exactly the rows of one fold; expected {sorted(fold)}, got {new}"
        assert tr == [i for i in range(n) if i not in set(fold)], f"each call trains on every row OUTSIDE that fold; fold {sorted(fold)} was given training rows {tr}"
    for j, fold in enumerate(folds):
        for i in fold:
            tr = [t for t in range(n) if t not in set(fold)]
            want = sum(y[t] for t in tr) / len(tr) + i * 1e-3
            assert near(out[i], want), f"row {i} should hold the prediction made while its fold was held out ({want:.4f}); got {out[i]:.4f}. Are results in ROW order, not fold order?"
    lines = []
    for seed in seeds(range(3)):
        X, y = mod.make_stack_data(900, seed)
        folds = mod.kfold_folds(len(y), 5, 0)
        row = []
        for name, fp in zip(mod.BASE_NAMES, mod.BASE_MODELS):
            ins = mod.roc_auc(fp(X, y, X), y)
            oof = mod.roc_auc(mod.oof_predictions(fp, X, y, folds), y)
            row.append((name, ins, oof))
        mem = row[3]
        assert mem[1] > 0.98 and mem[2] < 0.70, f"seed {seed}: the memoriser should look perfect on its own rows (AUC {mem[1]:.3f}) and mediocre out of fold (about 0.63; got {mem[2]:.3f})"
        lg = row[0]
        assert abs(lg[1] - lg[2]) < 0.03, f"seed {seed}: a logistic regression barely overfits, so in-sample and out-of-fold AUC should be within 0.03 ({lg[1]:.3f} and {lg[2]:.3f})"
        if seed == seeds(range(3))[0]:
            lines = [f"  {name:<10} in-sample AUC {ins:.3f}   out-of-fold AUC {oof:.3f}" for name, ins, oof in row]
    return "a spy model proves each call trains on the other folds and predicts one fold, and results come back in row order\n900 rows, 10 features, 5 folds:\n" + "\n".join(lines)


# =============================================================================
# Milestone 5: stacking
# =============================================================================
def m5():
    P = [[0.9, 0.5], [0.8, 0.5], [0.2, 0.5], [0.1, 0.5], [0.7, 0.5], [0.3, 0.5]]
    y = [1, 1, 0, 0, 1, 0]
    predict, weights = mod.fit_stacker(P, y)
    assert len(weights) == 2, f"one weight per base model; got {weights}"
    assert weights[0] > 0.3 and abs(weights[1]) < 1e-9, f"column 0 separates the classes (positive weight) and column 1 is constant (weight 0); got {[round(w, 4) for w in weights]}"
    p = predict([[0.95, 0.5], [0.05, 0.5]])
    assert len(p) == 2 and p[0] > 0.5 > p[1] and all(0 < v < 1 for v in p), f"high base score in, high probability out; got {p}"
    p = predict([[0.0, 1.0], [1.0, 0.0]])
    assert all(math.isfinite(v) and 0 <= v <= 1 for v in p), "base scores of exactly 0 or 1 must be clipped (use the given logit), not turned into infinities"
    # spy on how the base models are fitted
    X, y = mod.make_stack_data(300, 5)
    Xnew, _ = mod.make_stack_data(37, 6)
    folds = mod.kfold_folds(300, 5, 0)
    for honest in (True, False):
        log = []

        def spy(Xtr, ytr, Xn, _log=log):
            _log.append((len(Xtr), len(Xn)))
            return mod.logreg_fit_predict(Xtr, ytr, Xn)

        out, w = mod.stack_fit_predict([spy, mod.knn_fit_predict], X, y, Xnew, folds, honest=honest)
        assert len(out) == 37 and len(w) == 2, "stack_fit_predict returns (scores for Xnew, one weight per base model)"
        if honest:
            want = sorted([(300 - len(f), len(f)) for f in folds] + [(300, 37)])
            assert sorted(log) == want, \
                f"honest stacking fits each base model k + 1 = 6 times: once per fold on the other folds (to predict that fold) and once on ALL 300 training rows (to predict the 37 new rows). Expected (rows trained on, rows predicted) {want}; got {sorted(log)}"
        else:
            assert sorted(log) == [(300, 37), (300, 300)], f"honest=False fits each base model twice, on all 300 rows: once to predict them, once to predict the new rows; got {sorted(log)}"
    # the scenario: the stack beats its parts, and only if it was trained honestly
    table, margins = [], []
    first = None
    for seed in seeds(range(3)):
        Xtr, ytr = mod.make_stack_data(1000, seed)
        Xte, yte = mod.make_stack_data(1500, seed + 50)
        folds = mod.kfold_folds(len(ytr), 5, 0)
        parts = [mod.roc_auc(fp(Xtr, ytr, Xte), yte) for fp in mod.BASE_MODELS]
        honest, w_h = mod.stack_fit_predict(mod.BASE_MODELS, Xtr, ytr, Xte, folds, honest=True)
        leaky, w_l = mod.stack_fit_predict(mod.BASE_MODELS, Xtr, ytr, Xte, folds, honest=False)
        a_h, a_l = mod.roc_auc(honest, yte), mod.roc_auc(leaky, yte)
        best = max(parts)
        assert a_h > best + 0.004, f"seed {seed}: the stacked ensemble (AUC {a_h:.3f}) should beat its best part ({mod.BASE_NAMES[parts.index(best)]} at {best:.3f}) by a clear margin"
        assert a_l < a_h - 0.02, f"seed {seed}: stacking on in-sample predictions should lose at least 0.02 AUC to the honest stack ({a_h:.3f}); got {a_l:.3f}"
        assert w_l[3] > 2 * max(w_l[:3]) and w_h[3] < 0.3, \
            f"seed {seed}: on in-sample predictions the memoriser looks perfect and should get the biggest meta-weight (by far); honest weights {[round(v, 2) for v in w_h]}, in-sample weights {[round(v, 2) for v in w_l]}"
        margins.append(a_h - best)
        if first is None:
            first = (parts, a_h, a_l, w_h, w_l)
    assert sum(margins) / len(margins) > 0.01, f"on average the stack should beat its best part by more than 0.01 AUC; got {sum(margins) / len(margins):.4f}"
    parts, a_h, a_l, w_h, w_l = first
    lines = ["spies prove the fit counts (k + 1 honest, 2 in-sample), constants and clipping, and a scenario on 3 seeds (1,000 training rows, 1,500 test rows)",
             "test AUC and meta-weights (logistic, kNN, tree, memoriser):"]
    for name, a in zip(mod.BASE_NAMES, parts):
        lines.append(f"  {name:<28}{a:.3f}")
    lines.append(f"  {'stack, out-of-fold':<28}{a_h:.3f}   weights {[round(v, 2) for v in w_h]}")
    lines.append(f"  {'stack, in-sample (leaky)':<28}{a_l:.3f}   weights {[round(v, 2) for v in w_l]}")
    return "\n".join(lines)


check(1, "Milestone 1: smoothed target encoding", m1)
check(2, "Milestone 2: out-of-fold target encoding", m2)
check(3, "Milestone 3: a leak-safe pipeline inside cross-validation", m3)
check(4, "Milestone 4: out-of-fold predictions", m4)
check(5, "Milestone 5: a stacked ensemble that beats its parts", m5)

print()
print(f"{sum(results)}/{len(results)} milestones passing  ({time.time() - START:.1f} s)")
