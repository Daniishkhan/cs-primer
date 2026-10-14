"""Self-check for Lab 5: Thresholds & Calibration.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 2     # milestone 4, replaying ONLY seed 2

Every dataset is synthetic and drawn from a seeded random.Random, so every run gives identical numbers and
the whole check finishes in a few seconds. The oracles in this file are deliberately independent of the
functions you write: a threshold-by-threshold recount of precision and recall, a brute-force search over every
candidate threshold, the min-max formula for isotonic regression, the two score equations that define a
logistic fit, and (for the decision scenarios) the expected cost computed against the TRUE probabilities that
the generator knows and your code never sees. Prints a tick, a cross, or "not implemented yet" for each
milestone.
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
INF = float("inf")


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


def true_cost(flags, p_true, c_fp, c_fn):
    """Expected cost per case of a set of flags, computed against the TRUE probabilities (the generator's
    secret): a flagged case costs (1 - p) * c_fp in expectation, an unflagged one p * c_fn."""
    return sum((1 - p) * c_fp if f else p * c_fn for f, p in zip(flags, p_true)) / len(p_true)


def bayes_flags(p_true, c_fp, c_fn):
    t = c_fp / (c_fp + c_fn)
    return [1 if p >= t else 0 for p in p_true]


# =============================================================================
# Milestone 1: the precision-recall curve
# =============================================================================
def m1():
    pts = mod.precision_recall_points([0.9, 0.8, 0.7, 0.6], [1, 0, 1, 0])
    want = [(0.9, 1.0, 0.5), (0.8, 0.5, 0.5), (0.7, 2 / 3, 1.0), (0.6, 0.5, 1.0)]
    assert len(pts) == 4 and all(near(a, c) and near(b, d) and near(e, f) for (a, b, e), (c, d, f) in zip(pts, want)), \
        f"scores 0.9 0.8 0.7 0.6 with labels 1 0 1 0 give points (threshold, precision, recall) {want}; got {pts}"
    got = mod.precision_recall_points([0.5, 0.5, 0.5, 0.9], [1, 0, 0, 1])
    assert len(got) == 2 and near(got[0][1], 1.0) and near(got[0][2], 0.5) and near(got[1][1], 0.5) and near(got[1][2], 1.0), \
        f"three cases tied at 0.5 (one positive) enter TOGETHER: expected [(0.9, 1.0, 0.5), (0.5, 0.5, 1.0)], got {got}"
    got = mod.average_precision([0.9, 0.8, 0.7, 0.6], [1, 0, 1, 0])
    assert near(got, 0.5 * 1.0 + 0.5 * (2 / 3)), f"AP of the first example = 0.5 x 1.0 + 0.5 x 0.667 = 0.8333; got {got}"
    got = mod.average_precision([0.5, 0.5, 0.5, 0.9], [1, 0, 0, 1])
    assert near(got, 0.75), f"AP of the tie example = 0.5 x 1.0 + 0.5 x 0.5 = 0.75; got {got} (recall steps times precision AT each point)"
    assert near(mod.average_precision([4, 3, 2, 1], [1, 1, 0, 0]), 1.0), "a perfect ranking has AP 1.0"
    got = mod.average_precision([0.3] * 8, [1, 0, 0, 0, 1, 0, 0, 0])
    assert near(got, 0.25), f"all scores tied: one point with precision = base rate 0.25 and recall 1, so AP = 0.25; got {got}"
    try:
        mod.precision_recall_points([0.1, 0.2, 0.3], [0, 0, 0])
        raise AssertionError("no positives in y must raise ValueError")
    except ValueError:
        pass
    for seed in seeds(range(40)):
        rng = random.Random(seed)
        n = rng.randint(5, 40)
        y = [rng.randint(0, 1) for _ in range(n)]
        y[0], y[1] = 1, 0
        s = [rng.randint(0, 7) for _ in range(n)] if seed % 2 else [round(rng.random(), 3) for _ in range(n)]
        pts = mod.precision_recall_points(s, y)
        distinct = sorted(set(s), reverse=True)
        assert [p[0] for p in pts] == distinct, f"one point per distinct score, highest first (seed {seed}): expected thresholds {distinct}, got {[p[0] for p in pts]}"
        for t, prec, rec in pts:
            flagged = [i for i in range(n) if s[i] >= t]
            tp = sum(y[i] for i in flagged)
            assert near(prec, tp / len(flagged)) and near(rec, tp / sum(y)), \
                f"seed {seed}, threshold {t}: recount gives precision {tp}/{len(flagged)} and recall {tp}/{sum(y)}; got precision {prec}, recall {rec}"
        ap = sum((r - r0) * p for (_, p, r), (_, _, r0) in zip(pts, [(0, 0, 0)] + pts[:-1]))
        assert near(mod.average_precision(s, y), ap), f"average_precision disagrees with the recount (seed {seed})"
    scores, y, p = mod.make_cases(20000, 7, stretch=2.0, shift=0.5)
    _, _, p0 = mod.make_cases(20000, 7)
    base = sum(y) / len(y)
    ap_s, ap_p = mod.average_precision(scores, y), mod.average_precision(p, y)
    assert near(ap_s, ap_p, 1e-9), f"AP depends only on the ranking, and a stretch of the log-odds keeps it: got {ap_s:.6f} and {ap_p:.6f}"
    assert ap_p > 4 * base, f"a model with AUC 0.85 should have AP several times the base rate {base:.3f}; got {ap_p:.3f}"
    rnd = random.Random(1)
    ap_rand = mod.average_precision([rnd.random() for _ in y], y)
    assert abs(ap_rand - base) < 0.02, f"random scores should have AP near the base rate {base:.3f}; got {ap_rand:.3f}"
    return (f"hand curves with ties, a point-by-point recount on 40 seeded lists, AP invariance under a monotone change\n"
            f"20,000 cases at base rate {base:.3f}: AP {ap_p:.3f} for the model ({ap_p / base:.1f}x the base rate), {ap_rand:.3f} for random scores")


# =============================================================================
# Milestone 2: thresholds from costs, recall promises and capacity
# =============================================================================
def m2():
    assert near(mod.cost_threshold(5, 100), 5 / 105) and near(mod.cost_threshold(1, 1), 0.5) and near(mod.cost_threshold(10, 1), 10 / 11), \
        "cost_threshold(c_fp, c_fn) = c_fp / (c_fp + c_fn): 5 and 100 give 0.0476, equal costs 0.5"
    s, y = [0.9, 0.2, 0.6, 0.1], [1, 0, 0, 1]
    got = mod.expected_cost(s, y, 0.5, 5, 100)
    assert near(got, 26.25), f"threshold 0.5: 0.9 is a hit, 0.6 a false alarm (5), 0.1 a miss (100); (5 + 100) / 4 = 26.25; got {got}"
    got = mod.expected_cost(s, y, 0.6, 5, 100)
    assert near(got, 26.25), f"a case whose score EQUALS the threshold is flagged (score >= threshold); expected 26.25, got {got}"
    assert near(mod.expected_cost(s, y, INF, 5, 100), 50.0), "flag nothing: two misses cost 200 over 4 cases = 50"
    got = mod.best_threshold(s, y, 5, 10)
    assert got[0] == 0.9 and near(got[1], 2.5), f"costs 5 and 10: thresholds 0.9 and 0.1 both cost 2.5; ties go to the HIGHER threshold, so (0.9, 2.5); got {got}"
    got = mod.best_threshold([0.1, 0.2], [0, 0], 5, 100)
    assert got[0] == INF and near(got[1], 0.0), f"with no positives the best rule flags nothing: (inf, 0.0); got {got}"
    for seed in seeds(range(40)):
        rng = random.Random(seed)
        n = rng.randint(4, 30)
        y = [1 if rng.random() < 0.35 else 0 for _ in range(n)]
        s = [rng.randint(0, 9) / 10 for _ in range(n)]
        c_fp, c_fn = rng.choice([1, 2, 5, 10]), rng.choice([1, 5, 20, 100])
        cands = sorted(set(s), reverse=True) + [INF]
        costs = [(mod.expected_cost(s, y, t, c_fp, c_fn), t) for t in cands]
        low = min(c for c, _ in costs)
        want_t = max(t for c, t in costs if near(c, low))
        t, c = mod.best_threshold(s, y, c_fp, c_fn)
        assert t == want_t and near(c, low), \
            f"seed {seed}: brute force over every candidate threshold finds cost {low:.4f} at {want_t} (ties: the highest); got ({t}, {c:.4f}). Scores {s}, labels {y}, c_fp {c_fp}, c_fn {c_fn}"
    scores, y, p = mod.make_cases(40000, 3)
    t0 = time.time()
    mod.best_threshold(scores, y, 5, 100)
    took = time.time() - t0
    assert took < 3.0, f"best_threshold took {took:.1f} s on 40,000 cases: sort once and sweep with running counts instead of recomputing the cost for every candidate"
    pr = [0.9, 0.8, 0.7, 0.6], [1, 0, 1, 0]
    assert mod.threshold_for_recall(*pr, 0.5) == 0.9 and mod.threshold_for_recall(*pr, 0.51) == 0.7 and mod.threshold_for_recall(*pr, 1.0) == 0.7, \
        "recall 0.5 needs only the top case (0.9); anything above 0.5, up to 1.0, needs the second positive (0.7)"
    for bad in (0.0, 1.2):
        try:
            mod.threshold_for_recall(*pr, bad)
            raise AssertionError(f"target recall {bad} is outside (0, 1] and must raise ValueError")
        except ValueError:
            pass
    assert mod.threshold_for_capacity([0.2, 0.9, 0.5, 0.7], 2) == 0.7 and mod.threshold_for_capacity([0.2, 0.9, 0.5, 0.7], 4) == 0.2, \
        "capacity k flags the k highest scores: the threshold is the k-th largest score"
    flagged = sum(1 for v in [0.5, 0.5, 0.9, 0.1] if v >= mod.threshold_for_capacity([0.5, 0.5, 0.9, 0.1], 2))
    assert flagged == 3, "two cases tie at the k-th score, and a capacity cannot split a tie: 3 are flagged, not 2"
    for k in (0, 5):
        try:
            mod.threshold_for_capacity([0.2, 0.9, 0.5, 0.7], k)
            raise AssertionError(f"k = {k} is out of range and must raise ValueError")
        except ValueError:
            pass
    for seed in seeds(range(3)):
        scores, y, p = mod.make_cases(30000, 50 + seed)
        for target in (0.5, 0.8, 0.95):
            t = mod.threshold_for_recall(scores, y, target)
            flagged = [i for i in range(len(y)) if scores[i] >= t]
            rec = sum(y[i] for i in flagged) / sum(y)
            higher = [v for v in set(scores) if v > t]
            t_up = min(higher) if higher else INF
            rec_above = sum(y[i] for i in range(len(y)) if scores[i] >= t_up) / sum(y)
            assert rec >= target - 1e-12 and rec_above < target, \
                f"seed {seed}, target {target}: the returned threshold must reach the target (recall {rec:.4f}) and the next distinct score up must not (recall {rec_above:.4f})"
    # the cost rule against the empirical optimum
    rows = []
    for seed in seeds(range(3)):
        honest, y, p = mod.make_cases(40000, 60 + seed)
        over, _, _ = mod.make_cases(40000, 60 + seed, stretch=2.0, shift=0.5)
        ft = mod.cost_threshold(5, 100)
        t_h, c_h = mod.best_threshold(honest, y, 5, 100)
        f_h = mod.expected_cost(honest, y, ft, 5, 100)
        t_o, c_o = mod.best_threshold(over, y, 5, 100)
        f_o = mod.expected_cost(over, y, ft, 5, 100)
        assert f_h <= c_h * 1.03, f"seed {seed}: on HONEST probabilities the formula threshold {ft:.4f} should cost within 3% of the best threshold's cost {c_h:.3f}; it cost {f_h:.3f}"
        assert abs(t_h - ft) < 0.02, f"seed {seed}: the empirical best threshold {t_h:.4f} on honest probabilities should land near the formula's {ft:.4f}"
        assert f_o > c_o * 1.10, f"seed {seed}: on STRETCHED scores (log-odds doubled and shifted) the formula threshold should cost over 10% more than the best ({c_o:.3f}); it cost {f_o:.3f}. Is the cost computed per case?"
        rows.append((f_h, c_h, t_h, f_o, c_o, t_o))
    r = rows[0]
    cap = mod.threshold_for_capacity(mod.make_cases(40000, 60)[0], 2000)
    return (f"hand costs, a brute-force search over every candidate on 40 seeded lists with ties, recall and capacity thresholds, ties\n"
            f"40,000 cases, cost 5 and 100 (seed {ONLY_SEED if ONLY_SEED is not None else 0}): honest scores, formula threshold 0.0476 costs {r[0]:.3f}, best in hindsight {r[1]:.3f} at {r[2]:.4f}\n"
            f"same ranking, stretched scores: formula threshold costs {r[3]:.3f}, best in hindsight {r[4]:.3f} at {r[5]:.4f}")


# =============================================================================
# Milestone 3: proper scores and the reliability diagram
# =============================================================================
def m3():
    got = mod.brier_score([0.9, 0.2], [1, 0])
    assert near(got, 0.025), f"Brier: ((0.9 - 1)^2 + (0.2 - 0)^2) / 2 = 0.025; got {got}"
    b = 0.2
    y = [1] * 20 + [0] * 80
    got = mod.brier_score([b] * 100, y)
    assert near(got, b * (1 - b)), f"always predicting the base rate b scores b(1 - b) = 0.16; got {got}"
    got = mod.log_loss([0.8, 0.1], [1, 0])
    assert near(got, -(math.log(0.8) + math.log(0.9)) / 2), f"log loss: -(ln 0.8 + ln 0.9) / 2 = 0.16425; got {got}"
    got = mod.log_loss([0.0, 1.0], [1, 0])
    assert math.isfinite(got) and got > 20, f"a certain-and-wrong forecast must be clipped, not infinite: expected a large finite number (about 27.6); got {got}"
    p = [0.0625, 0.15625, 0.125, 0.9375, 1.0, 0.5]
    y = [0, 0, 1, 1, 1, 0]
    got = mod.reliability_table(p, y, 10)
    want = [(0, 1, 0.0625, 0.0), (1, 2, 0.140625, 0.5), (5, 1, 0.5, 0.0), (9, 2, 0.96875, 1.0)]
    assert len(got) == 4 and all(a[0] == b[0] and a[1] == b[1] and near(a[2], b[2]) and near(a[3], b[3]) for a, b in zip(got, want)), \
        f"10 bins: expected only the non-empty ones {want} (bin, count, mean predicted, observed rate); got {got}. Does p = 1.0 land in the LAST bin?"
    got = mod.ece(p, y, 10)
    want_ece = (0.0625 + 2 * abs(0.140625 - 0.5) + 0.5 + 2 * abs(0.96875 - 1.0)) / 6
    assert near(got, want_ece), f"ECE = sum over bins of (count / n) x |mean predicted - observed|. The hand table has counts 1, 2, 1, 2 out of 6 cases, so ECE = {want_ece:.6f}; got {got}. Is each bin weighted by its share of the cases?"
    got5 = mod.reliability_table(p, y, 5)
    assert [r[0] for r in got5] == [0, 2, 4] and [r[1] for r in got5] == [3, 1, 2], f"5 bins of width 0.2: counts 3, 1, 2 in bins 0, 2, 4; got {got5}"
    for seed in seeds(range(3)):
        scores, yy, pt = mod.make_cases(20000, 80 + seed, stretch=1.7, shift=-0.3)
        tab = mod.reliability_table(scores, yy, 10)
        assert sum(r[1] for r in tab) == 20000, "bin counts must add up to the number of cases"
        assert near(sum(r[1] * r[2] for r in tab), sum(scores), 1e-9) and near(sum(r[1] * r[3] for r in tab), sum(yy), 1e-9), \
            "bin counts times means must add back to the total predicted and the total positives"
    scores_o, y, p_true = mod.make_cases(40000, 5, stretch=2.0)
    honest = p_true
    assert mod.ece(honest, y, 10) < 0.01, f"honest probabilities should have ECE under 0.01 on 40,000 cases; got {mod.ece(honest, y, 10):.4f}"
    e_o = mod.ece(scores_o, y, 10)
    assert e_o > 2 * mod.ece(honest, y, 10), f"a model that doubles the log-odds should have a clearly larger ECE; got {e_o:.4f}"
    ll_h, ll_o = mod.log_loss(honest, y), mod.log_loss(scores_o, y)
    br_h, br_o = mod.brier_score(honest, y), mod.brier_score(scores_o, y)
    assert ll_h < ll_o and br_h < br_o, "same ranking, so the honest numbers must win on both proper scores"
    assert near(mod.roc_auc(honest, y), mod.roc_auc(scores_o, y), 1e-12), "(given) AUC does not see the difference"
    base = sum(y) / len(y)
    const = [base] * len(y)
    assert mod.ece(const, y, 10) < 1e-9 and near(mod.brier_score(const, y), base * (1 - base)), "a constant forecast at the base rate has zero ECE"
    return (f"hand scores, a hand reliability table with p = 1.0 in the last bin, ECE by hand, conservation checks on 3 seeds\n"
            f"same ranking (AUC {mod.roc_auc(honest, y):.3f}): honest ECE {mod.ece(honest, y, 10):.4f} Brier {br_h:.4f} log loss {ll_h:.4f}; stretched x2 ECE {e_o:.4f} Brier {br_o:.4f} log loss {ll_o:.4f}\n"
            f"a constant forecast of the base rate: ECE {mod.ece(const, y, 10):.4f}, Brier {mod.brier_score(const, y):.4f} (so never quote ECE alone)")


# =============================================================================
# Milestone 4: Platt scaling
# =============================================================================
def m4():
    s = [0.2] * 4 + [0.8] * 4
    y = [1, 0, 0, 0, 1, 1, 1, 0]
    a, b = mod.fit_platt(s, y)
    assert near(a, math.log(3) / math.log(4), 1e-6) and abs(b) < 1e-6, \
        f"two score values with observed rates 0.25 and 0.75: the logistic fit reproduces both exactly, so a = ln 3 / ln 4 = 0.7925 and b = 0; got a = {a:.6f}, b = {b:.6f}"
    out = mod.apply_platt((a, b), [0.2, 0.8])
    assert near(out[0], 0.25, 1e-6) and near(out[1], 0.75, 1e-6), f"apply_platt should map 0.2 to 0.25 and 0.8 to 0.75; got {out}"
    out = mod.apply_platt((1.0, 0.0), [0.0, 0.3, 1.0])
    assert all(0.0 <= v <= 1.0 and math.isfinite(v) for v in out) and near(out[1], 0.3, 1e-6), f"(1, 0) leaves a score alone, and 0 or 1 must not blow up; got {out}"
    notes = []
    for seed in seeds(range(3)):
        scores, y, _ = mod.make_cases(40000, 100 + seed, stretch=2.0, shift=0.5)
        a, b = mod.fit_platt(scores, y)
        z = [mod.logit(v) for v in scores]
        p = [mod.sigmoid(a * zi + b) for zi in z]
        n = len(y)
        g0 = sum(pi - t for pi, t in zip(p, y)) / n
        g1 = sum((pi - t) * zi for pi, t, zi in zip(p, y, z)) / n
        assert abs(g0) < 1e-6 and abs(g1) < 1e-6, \
            f"seed {seed}: at the maximum-likelihood fit the average residual (p - y) and the average residual x logit must both be 0; got {g0:.2e} and {g1:.2e}. Did Newton's method converge? (50+ iterations, start from a = 0, b = logit(base rate))"
        assert abs(a - 0.5) < 0.08 and abs(b - (-0.25)) < 0.35, \
            f"seed {seed}: the model reports sigmoid(2 z + 0.5), so the honest map is logit/2 - 0.25: expected a near 0.5 and b near -0.25; got a = {a:.3f}, b = {b:.3f}"
        notes.append((a, b))
    scores, y, _ = mod.make_cases(40000, 110, stretch=2.0, shift=0.5)
    test, yt, _ = mod.make_cases(40000, 111, stretch=2.0, shift=0.5)
    params = mod.fit_platt(scores, y)
    after = mod.apply_platt(params, test)
    e0, e1 = mod.ece(test, yt), mod.ece(after, yt)
    l0, l1 = mod.log_loss(test, yt), mod.log_loss(after, yt)
    b0, b1 = mod.brier_score(test, yt), mod.brier_score(after, yt)
    assert e1 < e0 / 3 and e1 < 0.01, f"on a fresh test set Platt scaling should cut ECE at least threefold (to under 0.01): {e0:.4f} -> {e1:.4f}"
    assert l1 < l0 and b1 < b0, f"log loss and Brier must both improve: log loss {l0:.4f} -> {l1:.4f}, Brier {b0:.4f} -> {b1:.4f}"
    assert near(mod.roc_auc(test, yt), mod.roc_auc(after, yt), 1e-12), "a Platt map with a > 0 is strictly increasing, so the AUC cannot change"
    under, yu, _ = mod.make_cases(40000, 112, stretch=0.6)
    au, bu = mod.fit_platt(under, yu)
    assert au > 1.2, f"an underconfident model (log-odds shrunk to 0.6x) needs a stretch a above 1 (about 1.67); got a = {au:.3f}"
    return (f"two-point hand fit (a = ln 3 / ln 4), score equations satisfied to 1e-6 on 3 seeds, recovery of the planted map\n"
            f"planted stretch 2, shift 0.5 (honest map a = 0.5, b = -0.25): fitted a = {notes[0][0]:.3f}, b = {notes[0][1]:.3f}\n"
            f"fresh test set: ECE {e0:.4f} -> {e1:.4f}, log loss {l0:.4f} -> {l1:.4f}, Brier {b0:.4f} -> {b1:.4f}, AUC unchanged at {mod.roc_auc(after, yt):.4f}")


# =============================================================================
# Milestone 5: isotonic regression
# =============================================================================
def minmax_isotonic(y):
    """Independent oracle: the isotonic fit at position i is max over j <= i of min over k >= i of mean(y[j..k])."""
    n = len(y)
    out = []
    for i in range(n):
        best = -INF
        for j in range(i + 1):
            low = INF
            for k in range(i, n):
                low = min(low, sum(y[j:k + 1]) / (k - j + 1))
            best = max(best, low)
        out.append(best)
    return out


def m5():
    xs, vals = mod.fit_isotonic([1, 2, 3, 4, 5, 6], [0, 1, 0, 1, 1, 0])
    assert list(xs) == [1, 3, 6] and all(near(a, b) for a, b in zip(vals, [0.0, 0.5, 2 / 3])), \
        f"labels 0 1 0 1 1 0 at scores 1..6: pooling gives blocks ending at 1, 3, 6 with values 0, 0.5, 0.667; got {list(xs)}, {list(vals)}"
    xs, vals = mod.fit_isotonic([1, 1, 2, 2], [1, 0, 0, 1])
    assert list(xs) == [2] and all(near(a, b) for a, b in zip(vals, [0.5])), \
        f"equal scores cannot be separated: the groups at 1 and 2 both have mean 0.5, and equal means are pooled into ONE block ending at 2; got {list(xs)}, {list(vals)}"
    xs, vals = mod.fit_isotonic([1, 2, 3, 4], [0, 0, 1, 1])
    assert list(xs) == [2, 4] and list(vals) == [0.0, 1.0], f"already monotone labels: blocks ending at 2 and 4 with values 0 and 1; got {list(xs)}, {list(vals)}"
    got = mod.apply_isotonic(([1, 3, 6], [0.0, 0.5, 2 / 3]), [0.5, 1, 1.5, 3, 3.5, 6, 100])
    want = [0.0, 0.0, 0.5, 0.5, 2 / 3, 2 / 3, 2 / 3]
    assert all(near(a, b) for a, b in zip(got, want)), f"a score belongs to the first block whose upper edge is >= it; expected {[round(v, 3) for v in want]}, got {[round(v, 3) for v in got]}"
    for seed in seeds(range(40)):
        rng = random.Random(seed)
        n = rng.randint(3, 14)
        y = [1 if rng.random() < 0.2 + 0.6 * i / n else 0 for i in range(n)]
        s = rng.sample(range(100), n)
        order = sorted(range(n), key=lambda i: s[i])
        sorted_s, sorted_y = [s[i] for i in order], [y[i] for i in order]
        model = mod.fit_isotonic(s, y)
        fitted = mod.apply_isotonic(model, sorted_s)
        want = minmax_isotonic(sorted_y)
        assert all(near(a, b, 1e-9) for a, b in zip(fitted, want)), \
            f"seed {seed}: the min-max formula gives {[round(v, 3) for v in want]} for labels {sorted_y} sorted by score; your fit applied back gives {[round(v, 3) for v in fitted]}"
    info = []
    for seed in seeds(range(3)):
        scores, y, _ = mod.make_cases(3000, 200 + seed, stretch=1.5)
        xs, vals = mod.fit_isotonic(scores, y)
        assert all(a < b for a, b in zip(xs, xs[1:])) and all(a < b for a, b in zip(vals, vals[1:])), \
            f"seed {seed}: block edges and values must both be strictly increasing"
        assert all(0.0 <= v <= 1.0 for v in vals), "values are mean labels, so they lie in [0, 1]"
        fitted = mod.apply_isotonic((xs, vals), scores)
        assert near(sum(fitted), sum(y), 1e-9), f"seed {seed}: pooling preserves the total: the fitted values must add to the number of positives ({sum(y)}); got {sum(fitted):.4f}"
        sse = sum((f - t) ** 2 for f, t in zip(fitted, y))
        platt = mod.apply_platt(mod.fit_platt(scores, y), scores)
        sse_platt = sum((f - t) ** 2 for f, t in zip(platt, y))
        base = sum(y) / len(y)
        sse_const = sum((base - t) ** 2 for t in y)
        assert sse <= sse_platt + 1e-9 and sse < sse_const, \
            f"seed {seed}: isotonic regression minimises squared error over ALL non-decreasing functions, so it must do at least as well as Platt's ({sse_platt:.3f}) and the constant ({sse_const:.3f}); got {sse:.3f}"
        info.append((len(set(scores)), len(xs)))
    # small versus large calibration sets
    rows = []
    test, yt, pt = mod.make_cases(30000, 301, stretch=1.5)
    for n_cal in (400, 1500, 20000):
        cal, yc, _ = mod.make_cases(n_cal, 300 + n_cal % 7, stretch=1.5)
        pl = mod.apply_platt(mod.fit_platt(cal, yc), test)
        iso = mod.apply_isotonic(mod.fit_isotonic(cal, yc), test)
        rows.append((n_cal, len(mod.fit_isotonic(cal, yc)[0]), mod.log_loss(pl, yt), mod.log_loss(iso, yt), mod.ece(pl, yt), mod.ece(iso, yt)))
    assert rows[0][3] > rows[0][2], f"with only 400 calibration cases the step function should overfit: log loss isotonic {rows[0][3]:.4f} should exceed Platt {rows[0][2]:.4f}"
    assert rows[2][3] < rows[0][3] and rows[2][5] < rows[0][5], "20,000 calibration cases should serve isotonic regression better than 400 (log loss and ECE)"
    assert rows[2][3] < rows[2][2] + 0.006, f"with 20,000 calibration cases isotonic regression should be close to Platt (within 0.006 log loss); got {rows[2][3]:.4f} against {rows[2][2]:.4f}"
    out = [f"hand blocks (0 .5 .667), ties pooled, and the min-max formula on 40 seeded lists; {info[0][0]} distinct scores became {info[0][1]} blocks (3,000 cases)",
           "test log loss by calibration-set size (stretch 1.5):",
           "   cases   blocks   Platt    isotonic    ECE Platt   ECE isotonic"]
    for n_cal, nb, lp, li, ep, ei in rows:
        out.append(f"  {n_cal:>6}  {nb:>6}  {lp:.4f}   {li:.4f}      {ep:.4f}      {ei:.4f}")
    return "\n".join(out)


# =============================================================================
# Milestone 6: undersampling, prior shift and the whole decision
# =============================================================================
def m6():
    got = mod.correct_undersampling(0.5, 0.1)
    assert near(got, 0.05 / 0.55), f"ps = 0.5 after keeping 10% of the negatives: p = 0.1 x 0.5 / (0.1 x 0.5 - 0.5 + 1) = 0.0909; got {got}"
    assert near(mod.correct_undersampling(0.3, 1.0), 0.3), "beta = 1 means nothing was dropped: no correction"
    rng = random.Random(1)
    for _ in range(50):
        p, beta = rng.uniform(0.001, 0.999), rng.choice([0.5, 0.1, 0.02])
        assert near(mod.correct_undersampling(mod.inflate(p, beta), beta), p, 1e-9), "correct_undersampling must be the inverse of the given inflate"
    got = mod.shift_prior(0.5, 0.01, 0.03)
    odds = (0.03 / 0.97) / (0.01 / 0.99)
    assert near(got, odds / (1 + odds)), f"p = 0.5 is odds 1; the odds ratio of the new to the old prior is (0.03/0.97)/(0.01/0.99) = 3.062, so p = 0.754; got {got}"
    assert near(mod.shift_prior(0.2, 0.05, 0.05), 0.2), "no change in the rate, no change in p"
    for beta in (0.1, 0.02):
        r_true = 0.03
        r_sample = (r_true / (1 - r_true) / beta) / (1 + r_true / (1 - r_true) / beta)
        ps = 0.4
        assert near(mod.shift_prior(ps, r_sample, r_true), mod.correct_undersampling(ps, beta), 1e-9), \
            "undersampling is a prior shift: moving from the sampled rate to the true rate must equal correct_undersampling"
    try:
        mod.calibrated_flags([0.1, 0.2], [0, 1], [0.1], 5, 100, "magic")
        raise AssertionError("an unknown method must raise ValueError")
    except ValueError:
        pass
    flags = mod.calibrated_flags([0.1, 0.2], [0, 1], [0.04, 0.0476, 0.05], 5, 100, "none")
    assert flags == [0, 0, 1], f"'none' flags a score at or above 5/105 = 0.047619: expected [0, 0, 1] (0.0476 is just below), got {flags}"
    table = []
    ok = None
    for seed in seeds(range(3)):
        beta = 0.02
        cal, yc, _ = mod.make_cases(6000, 400 + seed, stretch=1.5)
        test, yt, pt = mod.make_cases(30000, 500 + seed, stretch=1.5)
        raw_c = [mod.inflate(v, beta) for v in cal]
        raw_t = [mod.inflate(v, beta) for v in test]
        bayes = true_cost(bayes_flags(pt, 5, 100), pt, 5, 100)
        costs = {"none": true_cost(mod.calibrated_flags(raw_c, yc, raw_t, 5, 100, "none"), pt, 5, 100)}
        fix = [mod.correct_undersampling(v, beta) for v in raw_t]
        costs["undersampling corrected only"] = true_cost([1 if v >= 5 / 105 else 0 for v in fix], pt, 5, 100)
        for method in ("platt", "isotonic"):
            fl = mod.calibrated_flags(raw_c, yc, raw_t, 5, 100, method)
            assert len(fl) == len(raw_t) and set(fl) <= {0, 1}, "calibrated_flags returns one 0 or 1 per test case"
            order = sorted(range(len(raw_t)), key=lambda i: raw_t[i])
            assert all(fl[order[i]] <= fl[order[i + 1]] for i in range(len(order) - 1)), f"{method}: a higher score must never be flagged less often than a lower one"
            costs[method] = true_cost(fl, pt, 5, 100)
        assert costs["none"] > 1.3 * bayes, f"seed {seed}: scores inflated by undersampling and stretched should cost over 1.3x the best possible {bayes:.3f} if used as they are; got {costs['none']:.3f}"
        assert costs["platt"] < 1.03 * bayes, f"seed {seed}: Platt scaling on 6,000 held-out cases should reach within 3% of the best possible cost {bayes:.3f}; got {costs['platt']:.3f}"
        assert costs["isotonic"] < 1.06 * bayes, f"seed {seed}: isotonic regression on 6,000 held-out cases should reach within 6% of the best possible cost {bayes:.3f}; got {costs['isotonic']:.3f}"
        assert costs["undersampling corrected only"] < costs["none"] and costs["undersampling corrected only"] > costs["platt"], \
            f"seed {seed}: undoing the undersampling helps but leaves the overconfidence, so it must land between 'none' and Platt: {costs}"
        if ok is None:
            ok = (bayes, costs, sum(yc))
    bayes, costs, n_pos = ok
    lines = [f"hand corrections, undersampling = a prior shift, monotone flags, and a scenario on 3 seeds (6,000 calibration cases, {n_pos} positives; 30,000 test cases)",
             f"expected cost per case against the true probabilities (cost 5 and 100); best possible {bayes:.3f}:"]
    for name in ("none", "undersampling corrected only", "platt", "isotonic"):
        lines.append(f"  {name:<30}{costs[name]:.3f}   ({costs[name] / bayes:.2f}x the best)")
    return "\n".join(lines)


check(1, "Milestone 1: the precision-recall curve and average precision", m1)
check(2, "Milestone 2: thresholds from costs, recall and capacity", m2)
check(3, "Milestone 3: Brier, log loss, reliability tables and ECE", m3)
check(4, "Milestone 4: Platt scaling", m4)
check(5, "Milestone 5: isotonic regression", m5)
check(6, "Milestone 6: undersampling, prior shift and the whole decision", m6)

print()
print(f"{sum(results)}/{len(results)} milestones passing  ({time.time() - START:.1f} s)")
