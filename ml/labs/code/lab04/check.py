"""Self-check for Lab 4: The Leakage Hunt.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 1     # milestone 4, replaying ONLY the dataset of seed 1

Every dataset is synthetic and generated from a seeded random.Random, so every run gives identical
numbers and the whole check finishes in well under a minute. The oracles in this file are
deliberately independent of the functions you write: a brute-force AUC that compares every pair of
rows, spy models that record exactly which rows they were trained on, hand values from chapters 13
and 14, and properties the answer must have (no group straddles a fold, a shuffled-label score of an
honest pipeline is about 0.5, a feature known before day t cannot move when day t is changed).
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


def brute_auc(scores, y):
    """AUC by comparing every positive with every negative (ties count one half)."""
    pos = [s for s, t in zip(scores, y) if t == 1]
    neg = [s for s, t in zip(scores, y) if t == 0]
    wins = sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def snapshot(case):
    return (list(map(list, case.X)), list(case.y), list(case.groups), list(case.names), list(case.lag_days),
            list(case.series) if case.series is not None else None)


# =============================================================================
# Milestone 1: the harness's measuring tools
# =============================================================================
def m1():
    got = mod.roc_auc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1])
    assert near(got, 0.75), f"the textbook example: scores 0.1, 0.4, 0.35, 0.8 with labels 0, 0, 1, 1 has AUC 0.75 (3 of the 4 positive-negative pairs are ordered right); got {got}"
    assert near(mod.roc_auc([1, 2, 3, 4], [0, 0, 1, 1]), 1.0) and near(mod.roc_auc([1, 2, 3, 4], [1, 1, 0, 0]), 0.0), "a perfect ranking has AUC 1.0, a perfectly wrong one 0.0"
    got = mod.roc_auc([1, 1, 1, 1], [0, 1, 0, 1])
    assert near(got, 0.5), f"all scores tied: every pair counts one half, AUC 0.5; got {got}"
    got = mod.roc_auc([0.5, 0.5, 0.9], [0, 1, 1])
    assert near(got, 0.75), f"scores 0.5, 0.5, 0.9 with labels 0, 1, 1: one tied pair (0.5) and one won pair (1) give 0.75; got {got} (do ties share the average rank?)"
    try:
        mod.roc_auc([0.1, 0.2], [1, 1])
        raise AssertionError("roc_auc with only one class in y must raise ValueError")
    except ValueError:
        pass
    for seed in seeds(range(40)):
        rng = random.Random(seed)
        n = rng.randint(6, 40)
        y = [rng.randint(0, 1) for _ in range(n)]
        if 0 not in y or 1 not in y:
            y[0], y[1] = 0, 1
        s = [rng.randint(0, 6) for _ in range(n)] if seed % 2 else [rng.random() for _ in range(n)]
        assert near(mod.roc_auc(s, y), brute_auc(s, y), 1e-9), f"roc_auc disagrees with a pair-by-pair count (seed {seed}): scores {s}, labels {y}"
    # k-fold
    for n, k in [(10, 3), (103, 5), (7, 7)]:
        sp = mod.kfold_splits(n, k, 11)
        assert len(sp) == k, f"kfold_splits({n}, {k}, 11) should return {k} folds; got {len(sp)}"
        perm = list(range(n))
        random.Random(11).shuffle(perm)
        for i, (tr, va) in enumerate(sp):
            assert va == sorted(perm[i::k]), f"fold {i}: shuffle range(n) with random.Random(seed), then deal round-robin (perm[{i}::{k}]); expected {sorted(perm[i::k])[:6]}..., got {va[:6]}..."
            assert tr == [j for j in range(n) if j not in set(va)], f"fold {i}: the training rows are every row NOT in the validation fold, sorted"
        assert sorted(j for _, va in sp for j in va) == list(range(n)), "every row must be validated exactly once"
    assert [len(va) for _, va in mod.kfold_splits(10, 3, 0)] == [4, 3, 3], "10 rows in 3 folds should be 4, 3, 3"
    assert mod.kfold_splits(50, 5, 1) == mod.kfold_splits(50, 5, 1) and mod.kfold_splits(50, 5, 1) != mod.kfold_splits(50, 5, 2), "same seed same folds; another seed other folds"
    # cross_val_auc with a spy model
    rng = random.Random(5)
    X = [[rng.random(), rng.random()] for _ in range(60)]
    y = [1 if rng.random() < 0.3 + 0.4 * x[0] else 0 for x in X]
    sp = mod.kfold_splits(60, 4, 2)
    seen = []

    def spy(Xtr, ytr):
        seen.append(sorted(tuple(r) for r in Xtr))
        assert len(Xtr) == len(ytr)
        return lambda Z: [r[0] for r in Z]

    got = mod.cross_val_auc(spy, X, y, sp)
    for (tr, va), s in zip(sp, seen):
        assert s == sorted(tuple(X[i]) for i in tr), "fit must be called with the TRAINING rows of each fold, and only those"
    want = sum(brute_auc([X[i][0] for i in va], [y[i] for i in va]) for _, va in sp) / 4
    assert near(got, want, 1e-9), f"cross_val_auc should average the four fold AUCs ({want:.4f}); got {got:.4f}"
    case = mod.make_case("clean")
    honest = mod.cross_val_auc(mod.logreg_model, case.X, case.y, mod.kfold_splits(500, 5, 0))
    assert 0.66 < honest < 0.80, f"logistic regression on the clean loan data should score an AUC around 0.72; got {honest:.3f}"
    return f"AUC against a pair-by-pair count on 40 seeded lists (with ties), k-fold structure, a spy model that proves fit sees only training rows\nlogistic regression on the clean loan data: 5-fold AUC {honest:.3f}"


# =============================================================================
# Milestone 2: the column scan and the timeline audit
# =============================================================================
def m2():
    X = [[1.0, 5.0, 4.0], [2.0, 5.0, 3.0], [3.0, 5.0, 2.0], [4.0, 5.0, 1.0]]
    got = mod.column_auc_scan(X, [0, 0, 1, 1], ["up", "flat", "down"])
    assert [g[0] for g in got] == ["up", "flat", "down"], f"one entry per column, in column order, as (name, auc, distance); got {got}"
    assert near(got[0][1], 1.0) and near(got[0][2], 0.5), f"a column that ranks perfectly has AUC 1.0 and distance 0.5; got {got[0]}"
    assert near(got[1][1], 0.5) and near(got[1][2], 0.0), f"a constant column ties everywhere: AUC 0.5, distance 0; got {got[1]}"
    assert near(got[2][1], 0.0) and near(got[2][2], 0.5), f"a perfectly REVERSED column has AUC 0 and distance 0.5 (the sign does not matter for a leak); got {got[2]}"
    scan = [("a", 0.5, 0.0), ("b", 0.95, 0.45), ("c", 0.2, 0.3), ("d", 0.6, 0.1)]
    assert mod.suspects(scan) == ["b", "c"], f"suspects(flag_at=0.30) keeps columns with distance >= 0.30 (the boundary counts), in column order; got {mod.suspects(scan)}"
    assert mod.suspects(scan, flag_at=0.4) == ["b"] and mod.suspects(scan, flag_at=0.6) == [], "flag_at is a parameter"
    got = mod.audit_register(["a", "b", "c", "d"], [-3, 0, 12, 1])
    assert got == ["c", "d"], f"flag the columns written AFTER the prediction time (lag_days > 0); 0 means written at T and is not flagged. Expected ['c', 'd']; got {got}"
    hits = {}
    for kind in mod.CASES:
        c = mod.make_case(kind)
        sc = mod.column_auc_scan(c.X, c.y, c.names)
        assert len(sc) == len(c.names)
        hits[kind] = (mod.suspects(sc), mod.audit_register(c.names, c.lag_days))
    assert hits["target"][0] == ["retention_offer_sent"], f"the scan should flag exactly retention_offer_sent in the churn table (AUC about 0.96); got {hits['target'][0]}"
    assert hits["target"][1] == ["retention_offer_sent"], f"the register says retention_offer_sent is written 9 days after T; got {hits['target'][1]}"
    for kind in ("preproc", "twins", "temporal", "clean"):
        assert hits[kind] == ([], []), (f"no column of the '{kind}' case should be flagged by the scan or the register (false alarm); got {hits[kind]}. "
                                       "The clean case's best honest column has AUC 0.70, which is strong but legitimate: is flag_at still 0.30?")
    # the two detectors cover for each other
    c = mod.make_case("target")
    assert mod.suspects(mod.column_auc_scan(c.X, c.y, c.names)) == ["retention_offer_sent"], "the scan does not need the register"
    soft = [list(r) for r in c.X]
    rng = random.Random(0)
    for r, t in zip(soft, c.y):
        r[4] = 1.0 if rng.random() < (0.35 if t else 0.20) else 0.0       # still written after T, but only weakly informative
    sc = mod.column_auc_scan(soft, c.y, c.names)
    assert mod.suspects(sc) == [] and mod.audit_register(c.names, c.lag_days) == ["retention_offer_sent"], "a weak but late column slips past the scan; the register still catches it"
    return ("hand-computed scans, the 0.30 boundary, the lag rule, and all five cases: only the churn table is flagged\n"
            f"churn table: retention_offer_sent has AUC {mod.column_auc_scan(c.X, c.y, c.names)[4][1]:.3f} alone; best honest column in the clean case: "
            f"{max(mod.column_auc_scan(mod.make_case('clean').X, mod.make_case('clean').y, mod.make_case('clean').names), key=lambda s: s[2])[1]:.3f}")


# =============================================================================
# Milestone 3: preprocessing inside the fold, and the shuffled-label test
# =============================================================================
def m3():
    X = [[0, 1, 0, 7, 0], [0, 1, 1, 7, 0], [1, 0, 0, 7, 1], [1, 0, 1, 7, 2]]
    y = [0, 0, 1, 1]
    assert mod.select_top_k(X, y, 1) == [0], f"columns 0 (corr +1) and 1 (corr -1) tie on |corr|; the lower index wins; got {mod.select_top_k(X, y, 1)}"
    assert mod.select_top_k(X, y, 2) == [0, 1], f"the two perfect columns, sorted ascending; got {mod.select_top_k(X, y, 2)}"
    got = mod.select_top_k(X, y, 3)
    assert got == [0, 1, 4], f"the third best is column 4 (corr 0.90); the constant column 3 has correlation 0, not an error; got {got}"
    # spy models: which columns and rows does each fold's model see?
    case = mod.make_case("preproc")
    n = len(case.y)
    sp = mod.kfold_splits(n, 5, 0)
    log = []

    def spy(Xtr, ytr):
        log.append((len(Xtr), len(Xtr[0]), [round(v, 9) for v in Xtr[0]]))
        return lambda Z: [r[0] for r in Z]

    mod.cv_with_selection(spy, case.X, case.y, sp, 10, inside=False)
    cols_all = mod.select_top_k(case.X, case.y, 10)
    for (tr, _), (rows, width, first) in zip(sp, log):
        assert rows == len(tr) and width == 10, f"each fold should fit on its training rows and exactly 10 columns; got {rows} rows x {width} columns"
        assert first == [round(case.X[tr[0]][c], 9) for c in cols_all], "inside=False: the same 10 columns, chosen once from ALL rows, are used in every fold"
    log.clear()
    mod.cv_with_selection(spy, case.X, case.y, sp, 10, inside=True)
    for (tr, _), (rows, width, first) in zip(sp, log):
        cols = mod.select_top_k([case.X[i] for i in tr], [case.y[i] for i in tr], 10)
        assert first == [round(case.X[tr[0]][c], 9) for c in cols], ("inside=True: each fold must choose its 10 columns from that fold's TRAINING rows only "
                                                                     "(its labels, not the validation rows')")
    wrong = mod.cv_with_selection(mod.logreg_model, case.X, case.y, sp, 10, inside=False)
    right = mod.cv_with_selection(mod.logreg_model, case.X, case.y, sp, 10, inside=True)
    assert wrong > 0.75, f"picking the 10 best of 300 noise columns on all rows, then cross-validating, should look great (AUC about 0.86); got {wrong:.3f}"
    assert 0.35 < right < 0.65, f"the same pipeline with selection inside each fold is honest, about 0.5 on noise; got {right:.3f}"
    # the shuffled-label test
    y0 = [0, 1] * 20
    orig = list(y0)
    calls = []

    def probe(X, yy, s):
        calls.append(list(yy))
        return float(len(calls) - 1)

    got = mod.shuffle_test(probe, [[0]] * 40, y0, None, n_shuffles=6, seed=3)
    assert y0 == orig, "shuffle_test must not modify y; shuffle a copy"
    assert len(calls) == 6 and near(got, 2.5), f"it should call cv_fn once per shuffle and return the mean of the six results (2.5 here); got {got} after {len(calls)} calls"
    rng = random.Random(3)
    want = list(orig)
    rng.shuffle(want)
    assert calls[0] == want, "the first shuffle must be rng.shuffle(copy of y) with rng = random.Random(seed)"
    assert all(sorted(c) == sorted(orig) for c in calls) and calls[0] != calls[1], "each call gets a different permutation of the same labels"
    leaky = mod.shuffle_test(case.cv_fn, case.X, case.y, sp, 6, 0)
    honest_fn = lambda X, yy, s: mod.cv_with_selection(mod.logreg_model, X, yy, s, 10, inside=True)
    honest = mod.shuffle_test(honest_fn, case.X, case.y, sp, 6, 0)
    assert leaky > 0.70, f"the team's leaky pipeline should score well above chance on SHUFFLED labels (about 0.83); got {leaky:.3f}"
    assert 0.40 < honest < 0.60, f"the in-fold pipeline should score about 0.5 on shuffled labels; got {honest:.3f}"
    cl = mod.make_case("clean")
    sp2 = mod.kfold_splits(500, 5, 0)
    ok = mod.shuffle_test(cl.cv_fn, cl.X, cl.y, sp2, 6, 0)
    assert 0.42 < ok < 0.58, f"a clean pipeline on shuffled labels should hover near 0.5; got {ok:.3f}"
    ws = [mod.cv_with_selection(mod.logreg_model, case.X, case.y, mod.kfold_splits(n, 5, s), 10, inside=False) for s in range(5)]
    rs = [mod.cv_with_selection(mod.logreg_model, case.X, case.y, mod.kfold_splits(n, 5, s), 10, inside=True) for s in range(5)]
    return (f"column ranking by hand, spy models that show which rows and columns each fold sees, and the shuffled-label test\n"
            f"noise data (honest AUC 0.5), mean of 5 fold layouts:  selection on all rows {sum(ws) / 5:.3f},  inside the fold {sum(rs) / 5:.3f}\n"
            f"shuffled labels:  leaky pipeline {leaky:.3f},  in-fold pipeline {honest:.3f},  clean case {ok:.3f}")


# =============================================================================
# Milestone 4: twins across the wall
# =============================================================================
def m4():
    got = mod.group_kfold(["a", "a", "a", "b", "b", "c"], 2, 0)
    assert got == [([3, 4, 5], [0, 1, 2]), ([0, 1, 2], [3, 4, 5])], (f"groups a (3 rows), b (2), c (1) into 2 folds: a goes to fold 0, then b and c both go to fold 1 "
                                                                  f"(the fold with fewest rows gets the next group). Expected validation sets [0, 1, 2] and [3, 4, 5]; got {got}")
    worst = 0
    for seed in seeds((1, 2, 3)):
        rng = random.Random(seed)
        groups = []
        for g in range(120):
            groups += [f"p{g}" if g % 2 else g] * rng.randint(1, 5)
        rng.shuffle(groups)
        n = len(groups)
        sp = mod.group_kfold(groups, 5, seed)
        assert len(sp) == 5
        assert sorted(j for _, va in sp for j in va) == list(range(n)), f"every row validated exactly once (seed {seed})"
        for tr, va in sp:
            assert not ({groups[i] for i in tr} & {groups[i] for i in va}), f"a group appears in both the training and validation rows of a fold (seed {seed})"
            assert sorted(tr + va) == list(range(n)) and tr == sorted(tr) and va == sorted(va)
        sizes = [len(va) for _, va in sp]
        assert max(sizes) - min(sizes) <= 5, f"folds should be balanced to within the largest group (5 rows); sizes {sizes} (seed {seed})"
        assert sp == mod.group_kfold(groups, 5, seed), "same seed, same folds"
        worst = max(worst, max(sizes) - min(sizes))
        assert mod.twin_share(sp, groups) == 0.0
    g = ["a", "a", "b", "b"]
    assert near(mod.twin_share([([0, 2], [1, 3]), ([1, 3], [0, 2])], g), 1.0), "every validation row has its twin in training: share 1.0"
    assert near(mod.twin_share([([0, 1], [2, 3]), ([2, 3], [0, 1])], g), 0.0), "no validation row has a twin in training: share 0.0"
    assert near(mod.twin_share([([0, 2, 3], [1]), ([0, 1], [2, 3])], ["a", "a", "b", "c"]), 1 / 3), "one of the three validation rows (counted over both folds) has a twin: 1/3"
    tw = mod.make_case("twins")
    r, gr, share = mod.contamination_gap(tw)
    assert share > 0.6, f"with ordinary folds most scans of a patient should have a sibling in training (about 86%); got {share:.2f}"
    assert r > 0.85, f"1-nearest-neighbour with ordinary folds memorises the patients: AUC about 0.91; got {r:.3f}"
    assert 0.40 < gr < 0.60, f"with group folds the same model has nothing to remember: AUC about 0.5; got {gr:.3f}. Pass case.fit, and use group_kfold on case.groups"
    cl = mod.make_case("clean")
    r2, g2, s2 = mod.contamination_gap(cl)
    assert s2 == 0.0 and abs(r2 - g2) < 0.06, f"on the clean case every row is its own group: share 0 and no gap; got share {s2}, AUCs {r2:.3f} and {g2:.3f}"
    return (f"hand-worked folds, 3 seeded group layouts (fold sizes at most {worst} row apart), twin shares\n"
            f"scans of {len(set(tw.groups))} patients: ordinary folds give AUC {r:.3f} with {share:.0%} twins; group folds give {gr:.3f}")


# =============================================================================
# Milestone 5: the future inside a feature
# =============================================================================
def m5():
    assert mod.time_splits(12, 3) == [([0, 1, 2], [3, 4, 5]), (list(range(6)), [6, 7, 8]), (list(range(9)), [9, 10, 11])], \
        f"12 rows, 3 folds: b = 3, so (0..2 | 3..5), (0..5 | 6..8), (0..8 | 9..11); got {mod.time_splits(12, 3)}"
    got = mod.time_splits(14, 3)
    assert got[-1] == (list(range(9)), [9, 10, 11, 12, 13]), f"the last fold validates on everything left over (rows 9 to 13 here); got {got[-1]}"
    for tr, va in mod.time_splits(420, 5):
        assert max(tr) < min(va), "every validation row must be later than every training row"
    s = [float(v) for v in range(1, 11)]
    keep = list(s)
    ident = lambda x: list(x)
    got = mod.perturbation_test(ident, s, [3, 5])
    assert got == [3, 5], f"a feature equal to the day's own value moves when day t moves; expected [3, 5], got {got}"
    assert s == keep, "perturbation_test must not modify the series"
    assert mod.perturbation_test(mod.lag1, s, [1, 4, 7]) == [], "yesterday's value cannot move when day t and later change"
    assert mod.perturbation_test(mod.trailing_mean, s, [1, 4, 7]) == [], "a mean of days t-7..t-1 cannot move"
    assert mod.perturbation_test(mod.centred_mean, s, [1, 4, 7]) == [1, 4, 7], "a mean of days t-3..t+3 moves on every day"

    def cum_incl(x):
        out, tot = [], 0.0
        for i, v in enumerate(x):
            tot += v
            out.append(tot / (i + 1))
        return out

    def cum_excl(x):
        out, tot = [], 0.0
        for i, v in enumerate(x):
            out.append(tot / i if i else 0.0)
            tot += v
        return out

    nxt = lambda x: list(x[1:]) + [0.0]
    assert mod.perturbation_test(cum_incl, s, [2, 6]) == [2, 6], "a running mean that includes today moves"
    assert mod.perturbation_test(cum_excl, s, [2, 6]) == [], "a running mean up to yesterday does not"
    assert mod.perturbation_test(nxt, s, [2, 6]) == [2, 6], "tomorrow's value moves when day t and later change"
    assert mod.perturbation_test(ident, s, [3, 5], bump=1e-3) == [3, 5], "the bump is a parameter"
    tc = mod.make_case("temporal")
    got = mod.temporal_leaks(tc)
    assert got == ["centred7"], f"in the sales case only centred7 peeks at the future; got {got}"
    for kind in ("clean", "target", "twins", "preproc"):
        assert mod.temporal_leaks(mod.make_case(kind)) == [], f"a case without a series has no temporal leaks ({kind})"
    sp = mod.time_splits(len(tc.y), 4)
    cols_ok = [i for i, nme in enumerate(tc.names) if nme != "centred7"]
    X_ok = [[r[i] for i in cols_ok] for r in tc.X]
    leaky = mod.cross_val_auc(mod.logreg_model, tc.X, tc.y, sp)
    honest = mod.cross_val_auc(mod.logreg_model, X_ok, tc.y, sp)
    assert leaky - honest > 0.10, f"the centred mean should lift the forward-chaining AUC by more than 0.10 (got {leaky:.3f} vs {honest:.3f}); is time_splits correct?"
    return (f"hand-worked forward-chaining folds, seven feature shapes against the perturbation test (including running means and tomorrow's value)\n"
            f"sales case: forward-chaining AUC {leaky:.3f} with the centred mean, {honest:.3f} without it; only centred7 fails the test")


# =============================================================================
# Milestone 6: the whole hunt
# =============================================================================
EXPECT = {"target": {"target"}, "preproc": {"preprocessing"}, "twins": {"contamination"}, "temporal": {"temporal"}, "clean": set()}


def m6():
    lines = []
    for cs in seeds((0, 1)):
        for kind in mod.CASES:
            case = mod.make_case(kind, cs)
            before = snapshot(case)
            found = mod.hunt(case, seed=0)
            assert snapshot(case) == before, f"hunt must not modify the case ({kind}, seed {cs})"
            assert isinstance(found, dict) and all(isinstance(v, str) and v for v in found.values()), f"hunt returns {{kind: evidence string}}; got {found}"
            got = set(found)
            if got != EXPECT[kind]:
                missed, extra = EXPECT[kind] - got, got - EXPECT[kind]
                what = []
                if missed:
                    what.append(f"missed {sorted(missed)}")
                if extra:
                    what.append(f"FALSE ALARM {sorted(extra)}: {[found[k] for k in sorted(extra)]}")
                raise AssertionError(f"case '{kind}' (case seed {cs}): " + "; ".join(what))
            if cs == seeds((0, 1))[0]:
                lines.append(f"{kind:9s} -> " + (f"{sorted(found)[0]}: {found[sorted(found)[0]]}" if found else "no leak found"))
    return "every planted leak found, nothing flagged in the clean case, on 2 versions of each dataset\n" + "\n".join(lines)


check(1, "Milestone 1: AUC, k-fold splits and cross-validation", m1)
check(2, "Milestone 2: the column scan and the timeline audit", m2)
check(3, "Milestone 3: preprocessing inside the fold, and the shuffled-label test", m3)
check(4, "Milestone 4: twins across the wall (grouped folds)", m4)
check(5, "Milestone 5: the future inside a feature (perturbation test)", m5)
check(6, "Milestone 6: the whole hunt", m6)

print()
print(f"{sum(results)}/{len(results)} milestones passing  ({time.time() - START:.1f} s)")
