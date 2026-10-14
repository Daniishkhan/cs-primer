"""Self-check for Lab 2: Trees & Gradient Boosting from Scratch.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 2     # milestone 4, replaying ONLY the dataset of seed 2

Every dataset is synthetic and generated from a seeded random.Random, so every run gives
identical numbers, and the whole check finishes in a few seconds. The oracles in this file
are deliberately independent of the functions you write: a brute-force search for the best
split, hand values from chapters 8 and 9, and properties the answer must have (boosting
never raises the training error, an out-of-bag prediction never uses a tree that saw the row).
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


# ----- independent reference helpers -------------------------------------------------------------
def ref_gini01(y):
    p = sum(y) / len(y)
    return 2 * p * (1 - p)


def ref_var(y):
    m = sum(y) / len(y)
    return sum((v - m) ** 2 for v in y) / len(y)


def brute_best(X, y, criterion, min_leaf, features=None):
    """Try every feature and every midpoint, scoring each split from scratch (O(n^2), fine for tiny inputs)."""
    imp = ref_gini01 if criterion == "gini" else ref_var
    n = len(y)
    parent = imp(y)
    best = []
    for f in (range(len(X[0])) if features is None else features):
        vals = sorted(set(r[f] for r in X))
        for a, b in zip(vals, vals[1:]):
            t = (a + b) / 2
            L = [yy for r, yy in zip(X, y) if r[f] <= t]
            R = [yy for r, yy in zip(X, y) if r[f] > t]
            if len(L) < min_leaf or len(R) < min_leaf:
                continue
            best.append((parent - (len(L) * imp(L) + len(R) * imp(R)) / n, f, t))
    best = [b for b in best if b[0] > 1e-12]
    return max(best, key=lambda b: b[0]) if best else None


def walk(node):
    yield node
    if "feat" in node:
        yield from walk(node["left"])
        yield from walk(node["right"])


def leaves_of(node):
    return [nd for nd in walk(node) if "feat" not in nd]


def structure(node):
    if "feat" not in node:
        return ("leaf", round(node["value"], 9), node["n"])
    return (node["feat"], round(node["thr"], 9), structure(node["left"]), structure(node["right"]))


def ref_rmse(y, p):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(y, p)) / len(y))


# =============================================================================
# Milestone 1: impurity and the best split
# =============================================================================
def m1():
    assert mod.gini([]) == 0 and mod.gini([1, 1, 1]) == 0, "an empty or pure node has gini 0"
    assert near(mod.gini([0, 1]), 0.5) and near(mod.gini([0, 0, 0, 1]), 0.375), "gini([0,1]) = 0.5 and gini([0,0,0,1]) = 1 - 0.75^2 - 0.25^2 = 0.375"
    assert near(mod.gini([0, 1, 2]), 2 / 3), "three equally likely classes: 1 - 3 (1/3)^2 = 2/3"
    assert mod.variance([]) == 0 and mod.variance([5.0]) == 0 and near(mod.variance([1, 2, 3]), 2 / 3), "variance([1,2,3]) is 2/3 (divide by n)"

    # chapter 8's ten customers: tenure and churn
    ten = [[2.0], [3.0], [5.0], [7.0], [9.0], [12.0], [15.0], [20.0], [26.0], [34.0]]
    ch = [1.0, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    s = mod.best_split(ten, ch)
    assert s is not None and s[1] == 0 and near(s[2], 6.0) and near(s[0], 0.2142857142857143, 1e-9), (
        f"chapter 8's toy problem: the best cut is tenure <= 6.0 with gain 0.214 (gini 0.5 falls to a weighted 0.286); got {s}")
    s = mod.best_split(ten, ch, min_leaf=5)
    assert s is not None and near(s[2], 10.5) and near(s[0], 0.18, 1e-9), f"with min_leaf=5 only the 5/5 cut remains: tenure <= 10.5, gain 0.18; got {s}"
    s = mod.best_split(ten, ch, "mse")
    assert s is not None and near(s[2], 6.0) and near(s[0], 0.10714285714285715, 1e-9), (
        f"for 0/1 labels the variance is half the gini, so the 'mse' criterion picks the same cut with half the gain (0.107); got {s}")
    s = mod.best_split([[float(i)] for i in range(1, 7)], [1.0, 1.0, 1.0, 5.0, 5.0, 5.0], "mse")
    assert s is not None and near(s[2], 3.5) and near(s[0], 4.0), f"a perfect cut of [1,1,1,5,5,5] has gain = the parent variance 4.0 at 3.5; got {s}"

    # thresholds and ties
    s = mod.best_split([[1.0], [1.0], [2.0], [2.0]], [0.0, 0.0, 1.0, 1.0])
    assert s is not None and near(s[2], 1.5), "the threshold is the midpoint of consecutive DISTINCT values: 1.5"
    s = mod.best_split([[1.0], [1.0], [1.0], [2.0]], [0.0, 1.0, 0.0, 1.0])
    assert s is not None and near(s[2], 1.5), "equal feature values can never be separated: the only legal cut is between 1 and 2"
    two = [[0.3, 1.0], [0.9, 2.0], [0.1, 3.0], [0.7, 4.0], [0.5, 5.0], [0.2, 6.0]]
    s = mod.best_split(two, [0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
    assert s is not None and s[1] == 1 and near(s[2], 3.5), f"feature 1 separates the classes perfectly; got {s}"
    s = mod.best_split(two, [0.0, 0.0, 0.0, 1.0, 1.0, 1.0], features=[0])
    assert s is None or s[1] == 0, "features=[0] must restrict the search to column 0"
    assert mod.best_split([[1.0], [1.0], [1.0]], [0.0, 1.0, 1.0]) is None, "a constant feature offers no cut"
    assert mod.best_split([[1.0], [2.0], [3.0]], [1.0, 1.0, 1.0]) is None, "a pure node has no positive gain: return None"
    xor = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
    assert mod.best_split(xor, [0.0, 1.0, 1.0, 0.0]) is None, "XOR: every single cut has zero gain, so a greedy split finds none (return None)"
    assert mod.best_split([[1.0], [2.0], [3.0]], [0.0, 1.0, 1.0], min_leaf=2) is None, "3 rows cannot be cut into two leaves of at least 2"
    X0 = [[1.0], [2.0]]
    mod.best_split(X0, [0.0, 1.0])
    assert X0 == [[1.0], [2.0]], "best_split must not reorder or modify X"

    # a brute-force oracle on random problems
    for s_ in seeds(range(1, 41)):
        rng = random.Random(s_)
        n, d = rng.randint(4, 24), rng.randint(1, 4)
        X = [[float(rng.randint(0, 6)) if rng.random() < 0.5 else rng.random() for _ in range(d)] for _ in range(n)]
        crit = rng.choice(["gini", "mse"])
        y = [float(rng.random() < 0.5) for _ in range(n)] if crit == "gini" else [rng.gauss(0, 2) for _ in range(n)]
        ml = rng.choice([1, 1, 2, 3])
        want, got = brute_best(X, y, crit, ml), mod.best_split(X, y, crit, ml)
        if want is None:
            assert got is None, f"seed {s_}: no split has positive gain here, but best_split returned {got}"
            continue
        assert got is not None, f"seed {s_}: a split with gain {want[0]:.4f} exists ({crit}, min_leaf {ml}) but best_split returned None"
        assert near(got[0], want[0], 1e-9), (f"seed {s_} ({crit}, min_leaf {ml}, n={n}): best gain should be {want[0]:.6f} "
                                             f"(feature {want[1]}, threshold {want[2]:.4f}); got {got[0]:.6f} (feature {got[1]}, threshold {got[2]:.4f})")
        imp = ref_gini01 if crit == "gini" else ref_var
        L = [yy for r, yy in zip(X, y) if r[got[1]] <= got[2]]
        R = [yy for r, yy in zip(X, y) if r[got[1]] > got[2]]
        real = imp(y) - (len(L) * imp(L) + len(R) * imp(R)) / n
        assert L and R and min(len(L), len(R)) >= ml and near(real, got[0], 1e-9), (
            f"seed {s_}: cutting feature {got[1]} at {got[2]} gives gain {real:.6f} with leaves of {len(L)} and {len(R)} rows, not the {got[0]:.6f} you report")

    # speed: the scan must use running sums, not rescore every cut from scratch
    Xf, yf = mod.make_friedman(1, 3000)
    t0 = time.time()
    r = mod.best_split(Xf, yf, "mse")
    dt = time.time() - t0
    assert dt < 1.5, (f"best_split took {dt:.1f} s on 3000 rows x 10 features. Sort each feature once and update the left/right "
                      "counts with running sums instead of recomputing impurity for every cut (that is O(n^2))")
    return (f"chapter 8's toy: cut tenure <= 6.0 with gain 0.214 (gini); the same cut with gain 0.107 under 'mse'\n"
            f"matches a brute-force search on 40 random problems; 3000 rows x 10 features searched in {dt * 1000:.0f} ms (best cut: x{r[1]} <= {r[2]:.3f})")


# =============================================================================
# Milestone 2: growing and using a tree
# =============================================================================
def m2():
    X1 = [[float(i)] for i in range(1, 9)]
    y1 = [1.0, 1.6, 1.3, 3.0, 3.6, 3.1, 5.4, 4.9]
    t0_ = mod.grow(X1, y1, "mse", 0)
    assert "feat" not in t0_ and near(t0_["value"], 2.9875) and t0_["n"] == 8, f"max_depth=0 is a single leaf holding the mean 2.9875 of 8 rows; got {t0_}"
    t1 = mod.grow(X1, y1, "mse", 1)
    assert t1["feat"] == 0 and near(t1["thr"], 3.5) and t1["n"] == 8, f"one split on eight points: x <= 3.5; got {t1}"
    assert near(t1["left"]["value"], 1.3) and near(t1["right"]["value"], 20.0 / 5) and t1["left"]["n"] == 3 and t1["right"]["n"] == 5, (
        f"the leaves hold the means of their rows (1.3 for 3 rows, 4.0 for 5); got {t1['left']['value']}, {t1['right']['value']}")
    assert near(t1["gain"], 1.70859375, 1e-6), f"a split node stores its impurity decrease under 'gain' (here the variance falls from 2.3236 to 0.6150: 1.7086); got {t1.get('gain')}"
    assert mod.predict_one(t1, [2.0]) == t1["left"]["value"] and mod.predict_one(t1, [3.5]) == t1["left"]["value"] and mod.predict_one(t1, [3.51]) == t1["right"]["value"], (
        "rows with x <= threshold go left, including a row exactly on the threshold")
    assert all_near(mod.predict_tree(t1, [[1.0], [8.0]]), [t1["left"]["value"], t1["right"]["value"]])
    assert mod.depth_of(t0_) == 0 and mod.depth_of(t1) == 1 and mod.n_leaves(t0_) == 1 and mod.n_leaves(t1) == 2

    # a rule with an AND needs depth 2 and is then learned exactly
    rng = random.Random(1)
    Xa = [[rng.random(), rng.random()] for _ in range(200)]
    ya = [1.0 if a > 0.5 and b > 0.5 else 0.0 for a, b in Xa]
    ta = mod.grow(Xa, ya, "gini", 10)
    assert mod.accuracy(ya, mod.predict_tree(ta, Xa)) == 1.0 and mod.depth_of(ta) <= 3, (
        f"x0>0.5 AND x1>0.5 is learnable exactly with 2 or 3 splits; got depth {mod.depth_of(ta)} and accuracy {mod.accuracy(ya, mod.predict_tree(ta, Xa)):.3f}")
    xor = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]] * 5
    tx = mod.grow(xor, [0.0, 1.0, 1.0, 0.0] * 5, "gini", 5)
    assert mod.n_leaves(tx) == 1, "greedy CART cannot see XOR: no first split has any gain, so the tree is a single leaf"

    # the churn data of chapter 8
    note = []
    for k, s in enumerate(seeds((8, 9, 10))):
        X, y = mod.make_churn_rules(s)
        Xtr, ytr, Xte, yte = X[:1000], y[:1000], X[1000:], y[1000:]
        rows = []
        for depth in (1, 2, 3, 4, 6, 8, 12, 20):
            t = mod.grow(Xtr, ytr, "gini", depth, 1)
            assert mod.depth_of(t) <= depth, f"seed {s}: max_depth={depth} but the tree has depth {mod.depth_of(t)}"
            assert sum(l["n"] for l in leaves_of(t)) == 1000, f"seed {s}: the leaves' row counts must add up to 1000"
            for nd in walk(t):
                if "feat" in nd:
                    assert nd["left"]["n"] + nd["right"]["n"] == nd["n"], f"seed {s}: a node's children must share exactly its rows"
            rows.append((depth, mod.n_leaves(t), mod.accuracy(ytr, mod.predict_tree(t, Xtr)), mod.accuracy(yte, mod.predict_tree(t, Xte))))
        trs = [r[2] for r in rows]
        assert all(b >= a - 1e-12 for a, b in zip(trs, trs[1:])), f"seed {s}: training accuracy must never fall as the tree gets deeper; {[round(v, 3) for v in trs]}"
        best = max(rows, key=lambda r: r[3])
        assert rows[-1][2] > 0.99, f"seed {s}: an unlimited tree memorises the training rows (accuracy near 1.0); got {rows[-1][2]:.3f}"
        assert best[3] - rows[-1][3] > 0.04 and best[0] <= 6, (
            f"seed {s}: test accuracy should peak at a shallow depth and fall when the tree is allowed to memorise noise; "
            f"best depth {best[0]} ({best[3]:.3f}), depth 20: {rows[-1][3]:.3f}")
        for ml in (5, 25):
            t = mod.grow(Xtr, ytr, "gini", 20, ml)
            assert min(l["n"] for l in leaves_of(t)) >= ml, f"seed {s}: min_leaf={ml} but a leaf has only {min(l['n'] for l in leaves_of(t))} rows"
        # gini and mse choose identical trees on 0/1 labels
        ta, tb = mod.grow(Xtr, ytr, "gini", 4, 10), mod.grow(Xtr, ytr, "mse", 4, 10)
        assert structure(ta) == structure(tb), f"seed {s}: for 0/1 labels the variance is half the gini, so both criteria must grow the same tree"
        if k == 0:
            note.append(f"seed {s}  depth leaves train  test    (best possible accuracy about 0.88; the base rate is {1 - sum(yte) / len(yte):.3f})")
            note += [f"        {d:>3} {nl:>6} {a:6.3f} {b:6.3f}" for d, nl, a, b in rows]
    return "\n".join(note)


# =============================================================================
# Milestone 3: bagging and the random forest
# =============================================================================
def m3():
    rng = random.Random(0)
    fr = []
    for _ in range(200):
        idx = mod.bootstrap_sample(100, rng)
        assert len(idx) == 100 and all(0 <= i < 100 for i in idx), "a bootstrap sample of n has n indices in range(n)"
        fr.append(len(set(idx)) / 100)
    mean_unique = sum(fr) / len(fr)
    assert abs(mean_unique - (1 - math.exp(-1))) < 0.02, (
        f"a bootstrap sample (with replacement) contains about 1 - 1/e = 63.2% distinct rows; yours contains {mean_unique:.3f}")
    assert mod.bootstrap_sample(50, random.Random(5)) == mod.bootstrap_sample(50, random.Random(5)), "same seed, same sample"

    note = []
    for s in seeds((1, 2, 3)):
        Xa, ya = mod.make_friedman(s, 300)
        Xtr, ytr = Xa, ya
        Xte, yte = mod.make_friedman(100 + s, 1000)
        t_one = mod.grow(Xtr, ytr, "mse", 20, 1)
        e_tree = ref_rmse(yte, mod.predict_tree(t_one, Xte))
        bag = mod.fit_forest(Xtr, ytr, 40, None, 12, 3, "mse", s)
        rf = mod.fit_forest(Xtr, ytr, 40, 4, 12, 3, "mse", s)
        assert len(bag.trees) == 40 and len(bag.bags) == 40 and all(len(b) == 300 for b in bag.bags), "one tree and one bootstrap index list of length n per tree"
        e_bag, e_rf = ref_rmse(yte, mod.forest_predict(bag, Xte)), ref_rmse(yte, mod.forest_predict(rf, Xte))
        assert e_bag < 0.8 * e_tree and e_rf < 0.8 * e_tree, (
            f"seed {s}: averaging 40 trees should cut the error of one deep tree by at least 20%: one tree {e_tree:.2f}, bagging {e_bag:.2f}, forest {e_rf:.2f}")
        # the trees must differ, and repeated fits must agree
        assert len({structure(t) for t in rf.trees}) > 30, f"seed {s}: the trees of a forest should differ from one another"
        again = mod.fit_forest(Xtr, ytr, 40, 4, 12, 3, "mse", s)
        assert all_near(mod.forest_predict(again, Xte[:20]), mod.forest_predict(rf, Xte[:20])), f"seed {s}: the same seed must give the same forest"
        other = mod.fit_forest(Xtr, ytr, 40, 4, 12, 3, "mse", s + 77)
        assert not all_near(mod.forest_predict(other, Xte[:20]), mod.forest_predict(rf, Xte[:20]), 1e-6), "a different seed must give a different forest"
        # out-of-bag predictions never use a tree that saw the row
        oob = mod.oob_predict(rf, Xtr)
        assert len(oob) == 300, "one out-of-bag prediction per training row"
        for i in (0, 7, 100):
            votes = [mod.predict_one(t, Xtr[i]) for t, b in zip(rf.trees, rf.bags) if i not in set(b)]
            assert oob[i] is not None and near(oob[i], sum(votes) / len(votes)), (
                f"seed {s}: row {i} must be predicted by the average of exactly the {len(votes)} trees that did not draw it")
        single = mod.fit_forest(Xtr, ytr, 1, 4, 12, 3, "mse", s)
        none_rows = sum(p is None for p in mod.oob_predict(single, Xtr))
        assert abs(none_rows / 300 - 0.632) < 0.1, "with one tree, the 63% of rows it drew have no OOB prediction (None) and the rest do"
        o_rf = mod.oob_rmse(rf, Xtr, ytr)
        assert abs(o_rf - e_rf) / e_rf < 0.2, f"seed {s}: the OOB error {o_rf:.2f} should be close to the test error {e_rf:.2f} (within 20%)"
        # max_features really restricts the search: with one feature per split the root feature varies; without, it does not
        roots_all = [t["feat"] for t in bag.trees if "feat" in t]
        roots_one = [t["feat"] for t in mod.fit_forest(Xtr, ytr, 40, 1, 12, 3, "mse", s).trees if "feat" in t]
        assert len(set(roots_one)) >= 5, (f"seed {s}: with max_features=1 each tree's root should use a randomly chosen feature "
                                          f"(many different ones); roots used: {sorted(set(roots_one))}")
        assert len(set(roots_all)) <= 4, f"seed {s}: with every feature available, the roots should concentrate on the strongest few; roots used: {sorted(set(roots_all))}"
        note.append(f"seed {s}: test RMSE  one deep tree {e_tree:.2f}  bagging {e_bag:.2f}  forest (4 of 10 features) {e_rf:.2f}   OOB estimate {o_rf:.2f}   (noise floor 1.00)")
    # classification: the same forest on the churn data gives probabilities
    X, y = mod.make_churn_rules(8)
    f = mod.fit_forest(X[:1000], y[:1000], 30, 2, 12, 5, "gini", 1)
    pr = mod.forest_predict(f, X[1000:])
    acc = mod.accuracy(y[1000:], pr)
    one = mod.accuracy(y[1000:], mod.predict_tree(mod.grow(X[:1000], y[:1000], "gini", 20, 1), X[1000:]))
    assert all(0.0 <= p <= 1.0 for p in pr) and acc > one + 0.05, f"on churn, a 30-tree forest of 0/1 trees averages to probabilities and should beat one deep tree ({one:.3f}); got {acc:.3f}"
    note.append(f"churn: forest accuracy {acc:.3f} against {one:.3f} for one unlimited tree")
    return "\n".join(note)


# =============================================================================
# Milestone 4: gradient boosting for regression
# =============================================================================
def m4():
    # chapter 9's eight points, learning rate 0.5, stumps
    X1 = [[float(i)] for i in range(1, 9)]
    y1 = [1.0, 1.6, 1.3, 3.0, 3.6, 3.1, 5.4, 4.9]
    m0 = mod.fit_gbm(X1, y1, 0, 0.5, 1)
    assert near(m0.f0, 2.9875) and len(m0.trees) == 0 and all_near(mod.gbm_predict(m0, X1), [2.9875] * 8), "zero rounds is the constant mean 2.9875"
    m1_ = mod.fit_gbm(X1, y1, 1, 0.5, 1)
    p = mod.gbm_predict(m1_, X1)
    assert all_near(p, [2.14375] * 3 + [3.49375] * 5, 1e-9), (
        f"after one round: F0 + 0.5 x stump = 2.9875 + 0.5 (-1.6875) = 2.14375 on x <= 3 and 2.9875 + 0.5 (1.0125) = 3.49375 above; got {[round(v, 5) for v in p]}")
    assert near(ref_rmse(y1, [2.9875] * 8), 1.5243338709, 1e-6) and near(ref_rmse(y1, p), 1.0208567174, 1e-6)
    stg = mod.staged_rmse(mod.fit_gbm(X1, y1, 3, 0.5, 1), X1, y1)
    assert len(stg) == 3 and all_near(stg, [1.0208567174, 0.5969568006, 0.4282608893], 1e-6), (
        f"three stump rounds at lr 0.5 on chapter 9's eight points give RMSE 1.0209, 0.5970, 0.4283; got {[round(v, 4) for v in stg]}. "
        "If only the first is right, check that the running predictions F are updated by lr x tree, not the full tree")
    assert mod.best_round([3.0, 2.0, 2.5, 2.0]) == 2 and mod.best_round([1.0]) == 1, "best_round is 1-based and the first minimum wins"
    # a deep tree on the residuals interpolates in one round at lr = 1
    big = mod.fit_gbm(X1, y1, 1, 1.0, 10)
    assert ref_rmse(y1, mod.gbm_predict(big, X1)) < 1e-9, "with lr = 1 and a tree deep enough to isolate every row, one round fits the training rows exactly"

    note = []
    for s in seeds((1, 2, 3)):
        Xa, ya = mod.make_friedman(s, 500)
        Xtr, ytr, Xva, yva = Xa[:300], ya[:300], Xa[300:], ya[300:]
        Xte, yte = mod.make_friedman(100 + s, 1000)
        for lr in (0.05, 0.3, 1.0):
            m = mod.fit_gbm(Xtr, ytr, 40, lr, 3)
            tr = mod.staged_rmse(m, Xtr, ytr)
            assert len(m.trees) == 40, "fit_gbm must grow exactly n_rounds trees"
            up = next((k for k in range(1, len(tr)) if tr[k] > tr[k - 1] + 1e-9), None)
            assert up is None, (
                f"seed {s}, lr {lr}: training RMSE must never rise from one round to the next (each tree is fitted to the "
                f"residuals, and lr <= 1 takes a partial step towards them); it went from {tr[up - 1]:.3f} to {tr[up]:.3f} at round {up + 1}" if up else "")
        m = mod.fit_gbm(Xtr, ytr, 30, 0.2, 3)
        stg = mod.staged_rmse(m, Xva, yva)
        for k in (1, 7, 30):
            assert near(stg[k - 1], ref_rmse(yva, mod.gbm_predict(m, Xva, k)), 1e-9), (
                f"seed {s}: staged_rmse[{k - 1}] must equal the RMSE of gbm_predict(model, X, n_rounds={k})")
        assert all_near(mod.gbm_predict(m, Xva[:5]), mod.gbm_predict(m, Xva[:5], 30)), "n_rounds=None uses every tree"
        # the scenario: a big step overfits at once, a small one keeps improving
        big = mod.fit_gbm(Xtr, ytr, 500, 1.0, 3)
        small = mod.fit_gbm(Xtr, ytr, 500, 0.1, 3)
        cb, cs = mod.staged_rmse(big, Xva, yva), mod.staged_rmse(small, Xva, yva)
        rb, rs = mod.best_round(cb), mod.best_round(cs)
        assert rb < 25 and cb[-1] > 1.05 * cb[rb - 1], (
            f"seed {s}: with lr = 1.0 the validation error should bottom out within a few rounds ({rb}) and then climb as the model memorises noise; "
            f"best {cb[rb - 1]:.2f} at round {rb}, final {cb[-1]:.2f}")
        assert rs > 8 * rb and cs[rs - 1] < 0.85 * cb[rb - 1], (
            f"seed {s}: with lr = 0.1 the best round should come much later ({rs} vs {rb}) and give a clearly lower validation error ({cs[rs - 1]:.2f} vs {cb[rb - 1]:.2f})")
        tr_s = mod.staged_rmse(small, Xtr, ytr)
        assert tr_s[-1] < 0.5 * cs[rs - 1], f"seed {s}: training error keeps falling long after validation error stops, which is why we stop early"
        te = ref_rmse(yte, mod.gbm_predict(small, Xte, rs))
        note.append(f"seed {s}: validation RMSE  lr 1.0 best {cb[rb - 1]:.2f} at round {rb}, after 500 rounds {cb[-1]:.2f};   lr 0.1 best {cs[rs - 1]:.2f} at round {rs}   (test RMSE {te:.2f}; floor 1.00)")
    return "\n".join(note)


# =============================================================================
# Milestone 5: importances, and the three models side by side
# =============================================================================
def m5():
    X1 = [[1.0, 0.5], [2.0, 0.1], [3.0, 0.9], [4.0, 0.3]]
    y1 = [0.0, 0.0, 1.0, 1.0]
    t = mod.grow(X1, y1, "gini", 3)
    raw = mod.tree_importance_raw(t, 2)
    assert near(raw[0], 4 * 0.5, 1e-9) and raw[1] == 0.0, (
        f"a single split on feature 0 with gain 0.5 over 4 rows has raw importance n x gain = 2.0 (and 0 for feature 1); got {raw}")
    assert all_near(mod.tree_importance(t, 2), [1.0, 0.0]) and mod.normalise([0.0, 0.0]) == [0.0, 0.0] and all_near(mod.normalise([1, 3]), [0.25, 0.75])
    leaf = mod.grow(X1, [1.0, 1.0, 1.0, 1.0], "gini", 3)
    assert mod.tree_importance(leaf, 2) == [0.0, 0.0], "a tree with no splits has no importance to share (all zeros, not a division error)"
    Xs = [[float(i), 0.0, float((i * 7) % 5)] for i in range(1, 13)]
    ys = [0.0] * 6 + [1.0] * 6
    ts = mod.grow(Xs, ys, "gini", 3)
    imp = mod.tree_importance_raw(ts, 3)
    assert abs(sum(imp) - sum(nd["n"] * nd["gain"] for nd in walk(ts) if "feat" in nd)) < 1e-9, "raw importances must add up to the sum of n x gain over every split"

    note = []
    for k, s in enumerate(seeds((1, 2, 3))):
        Xa, ya = mod.make_friedman(s, 500)
        Xtr, ytr, Xva, yva = Xa[:300], ya[:300], Xa[300:], ya[300:]
        Xte, yte = mod.make_friedman(100 + s, 1000)
        tree = mod.grow(Xtr, ytr, "mse", 5, 5)
        rf = mod.fit_forest(Xtr, ytr, 60, 4, 12, 3, "mse", s)
        gb = mod.fit_gbm(Xtr, ytr, 400, 0.1, 3)
        stop = mod.best_round(mod.staged_rmse(gb, Xva, yva))
        imps = {"tree": mod.tree_importance(tree, 10), "forest": mod.forest_importance(rf, 10), "boosting": mod.gbm_importance(gb, 10)}
        for name, v in imps.items():
            assert near(sum(v), 1.0, 1e-9) and len(v) == 10, f"seed {s}: {name} importances must have 10 entries adding up to 1"
        for name in ("forest", "boosting"):
            v = imps[name]
            top = sorted(range(10), key=lambda j: -v[j])[:5]
            assert set(top) == {0, 1, 2, 3, 4}, (f"seed {s}: the five real features should hold the top five importances for the {name}; "
                                                f"got {top} from {[round(x, 3) for x in v]}")
            assert sum(v[5:]) < 0.2, f"seed {s}: the five noise features should share under 20% of the {name}'s importance; they hold {sum(v[5:]):.3f}"
        ybar = sum(ytr) / len(ytr)
        e_base = ref_rmse(yte, [ybar] * len(yte))
        e_tree = ref_rmse(yte, mod.predict_tree(tree, Xte))
        e_rf = ref_rmse(yte, mod.forest_predict(rf, Xte))
        e_gb = ref_rmse(yte, mod.gbm_predict(gb, Xte, stop))
        assert e_gb < e_rf < e_tree < e_base, (f"seed {s}: expected test RMSE ordering boosting < forest < one shallow tree < baseline; got "
                                               f"{e_gb:.2f}, {e_rf:.2f}, {e_tree:.2f}, {e_base:.2f}")
        note.append(f"seed {s}: test RMSE  mean {e_base:.2f} | one tree (depth 5) {e_tree:.2f} | forest {e_rf:.2f} | boosting, lr 0.1, stopped at round {stop} {e_gb:.2f}   (floor 1.00)")
        if k == 0:
            note.append("        importance   " + " ".join(f"x{j:<4d}" for j in range(10)))
            for name, v in imps.items():
                note.append(f"        {name:<12s} " + " ".join(f"{x:5.2f}" for x in v))
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: impurity and the best split", m1),
    (2, "Milestone 2: growing and using a tree", m2),
    (3, "Milestone 3: bagging and the random forest", m3),
    (4, "Milestone 4: gradient boosting for regression", m4),
    (5, "Milestone 5: importances, and the three models side by side", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 2 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
