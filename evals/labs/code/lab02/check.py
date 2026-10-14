"""Self-check for Lab 2: Calibrate an LLM Judge.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 5       # only milestone 5
    python3 check.py solution 2 7     # milestone 2, replaying ONLY the random trials of seed 7

Everything is synthetic and seeded: the 200 labelled answers, the 1,500 production answers, the stand-in
judge, the bootstrap resamples. There is no network and no real model, so every run gives identical
numbers. The whole check finishes in a few seconds. Prints a tick, a cross, or "not implemented yet"
for each milestone.
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
import judge as J  # noqa: E402

results = []
# The true pass rate of the 1,500 production answers, known only because the fixture was generated.
PRODUCTION_TRUTH = 0.588


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


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception:
        return False
    return False


P, F = "PASS", "FAIL"
LAB = mod.load_labelled()
PROD = mod.load_production()
HUMAN = [it["human"] for it in LAB]


def oracle_verdicts(items):
    return [J.judge_single(it["question"], it["answer"]) for it in items]


# =============================================================================
# Milestone 1: confusion matrix, TPR, TNR, kappa
# =============================================================================
def m1():
    cm = mod.confusion([P, P, F, F, P, F], [P, F, P, F, P, F])
    assert dict(cm) == {"tp": 2, "fn": 1, "fp": 1, "tn": 2}, f"expected tp=2 fn=1 fp=1 tn=2 (human is the reference, PASS is positive); got {cm}"
    for label, h, j in [("different lengths", [P, F], [P]), ("a bad label", [P, "OK"], [P, F]), ("a bad judge label", [P, F], [P, "pass"])]:
        assert raises(ValueError, mod.confusion, h, j), f"confusion must raise ValueError for {label}"

    book = {"tp": 104, "fn": 4, "fp": 30, "tn": 62}          # chapter 3's worked example
    r = mod.rates(book)
    assert near(r["accuracy"], 166 / 200) and near(r["tpr"], 104 / 108) and near(r["tnr"], 62 / 92), \
        f"chapter 3's judge: accuracy 0.83, TPR 104/108 = 0.963, TNR 62/92 = 0.674; got {r}"
    r0 = mod.rates({"tp": 0, "fn": 0, "fp": 5, "tn": 5})
    assert r0["tpr"] is None and near(r0["tnr"], 0.5), "a rate with no items in its class is None (not a ZeroDivisionError, not 0.0)"
    assert near(mod.cohen_kappa(book), 0.6505, 5e-4), \
        (f"kappa for chapter 3's judge: po = 0.83, pe = 0.54 x 0.67 + 0.46 x 0.33 = 0.5136, kappa = 0.6505; "
         f"got {mod.cohen_kappa(book):.4f}")
    lazy = {"tp": 90, "fn": 0, "fp": 10, "tn": 0}            # says PASS to everything on a 90% PASS task
    assert near(mod.rates(lazy)["accuracy"], 0.9) and mod.rates(lazy)["tnr"] == 0.0, "a judge that always passes: accuracy 0.9, TNR 0.0"
    assert near(mod.cohen_kappa(lazy), 0.0, 1e-12), "...and kappa 0.0: agreement no better than chance (accuracy alone would have called it 90%)"
    assert near(mod.cohen_kappa({"tp": 0, "fn": 50, "fp": 50, "tn": 0}), -1.0), "total disagreement: kappa -1"
    assert near(mod.cohen_kappa({"tp": 10, "fn": 0, "fp": 0, "tn": 10}), 1.0), "perfect agreement: kappa 1"
    assert mod.cohen_kappa({"tp": 10, "fn": 0, "fp": 0, "tn": 0}) == 1.0, "everyone says PASS, no variation: pe = 1, return 1.0 when po = 1"

    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        n = rng.randint(30, 120)
        h = [rng.choice([P, F]) for _ in range(n)]
        j = [x if rng.random() < 0.8 else (F if x == P else P) for x in h]
        cm = mod.confusion(h, j)
        assert sum(cm.values()) == n, f"seed {s}: the four cells must add up to {n}; got {sum(cm.values())}"
        assert cm["tp"] + cm["fn"] == h.count(P) and cm["tp"] + cm["fp"] == j.count(P), f"seed {s}: row and column totals are wrong"
        k = mod.cohen_kappa(cm)
        sw = mod.cohen_kappa({"tp": cm["tp"], "fn": cm["fp"], "fp": cm["fn"], "tn": cm["tn"]})
        assert near(k, sw, 1e-12), f"seed {s}: kappa is symmetric in the two raters (swapping fn and fp must not change it)"
        assert -1 <= k <= 1

    # the real stand-in judge on the 200 labelled answers, against an independent count
    verdicts = oracle_verdicts(LAB)
    want = {"tp": 0, "fn": 0, "fp": 0, "tn": 0}
    for h, v in zip(HUMAN, verdicts):
        want[("t" if h == v else "f") + ("p" if v == P else "n")] += 1
    cm = mod.confusion(HUMAN, verdicts)
    assert dict(cm) == want, f"on the 200 labelled answers expected {want}; got {dict(cm)}"
    r = mod.rates(cm)
    return (f"the stand-in judge on {len(LAB)} labelled answers: tp={cm['tp']} fn={cm['fn']} fp={cm['fp']} tn={cm['tn']}\n"
            f"  accuracy {r['accuracy']:.1%}   TPR {r['tpr']:.1%}   TNR {r['tnr']:.1%}   kappa {mod.cohen_kappa(cm):.2f}")


# =============================================================================
# Milestone 2: honest evaluation
# =============================================================================
def m2():
    items = [{"id": f"i{k}", "human": P if k < 12 else F} for k in range(20)]
    keep = [dict(x) for x in items]
    dev, test = mod.split_items(items)
    assert items == keep, "split_items must not modify its input"
    assert len(dev) == 10 and len(test) == 10, f"dev_frac 0.5 of 20 items: 10 and 10; got {len(dev)} and {len(test)}"
    assert not {x["id"] for x in dev} & {x["id"] for x in test}, "an item must not be in both dev and test"
    assert {x["id"] for x in dev} | {x["id"] for x in test} == {x["id"] for x in items}, "every item lands in dev or test"
    assert sum(x["human"] == P for x in dev) == 6 and sum(x["human"] == F for x in dev) == 4, \
        "stratified: 12 PASS and 8 FAIL split in half gives 6 PASS + 4 FAIL in dev"
    for part in (dev, test):
        ids = [int(x["id"][1:]) for x in part]
        assert ids == sorted(ids), "each part keeps the original order of the items"
    assert mod.split_items(items, seed=0) == (dev, test), "same seed, same split"
    assert mod.split_items(items, seed=1) != (dev, test), "a different seed gives a different split"
    d2, t2 = mod.split_items(items, dev_frac=0.25)
    assert (len(d2), sum(x["human"] == P for x in d2)) == (5, 3), f"dev_frac 0.25: round(0.25 x 12) = 3 PASS and round(0.25 x 8) = 2 FAIL in dev; got {len(d2)} items"
    dev, test = mod.split_items(LAB)
    assert len(dev) == 100 and len(test) == 100
    assert abs(sum(x["human"] == P for x in dev) - sum(x["human"] == P for x in test)) <= 1, "stratified halves have the same PASS count to within one"

    perfect = mod.bootstrap_rate_cis([P] * 20 + [F] * 20, [P] * 20 + [F] * 20)
    assert perfect["tpr"] == (1.0, 1.0) and perfect["tnr"] == (1.0, 1.0), "a judge that is always right has a degenerate interval"
    h = [P] * 100 + [F] * 100
    j = [P] * 75 + [F] * 25 + [F] * 60 + [P] * 40
    ci = mod.bootstrap_rate_cis(h, j, B=2000, seed=5)
    assert ci == mod.bootstrap_rate_cis(h, j, B=2000, seed=5), "same seed, same intervals"
    for name, p in (("tpr", 0.75), ("tnr", 0.60)):
        lo, hi = ci[name]
        assert lo < p < hi, f"{name}: the interval ({lo:.3f}, {hi:.3f}) should contain the observed rate {p}"
        want = 2 * 1.96 * math.sqrt(p * (1 - p) / 100)
        assert 0.75 < (hi - lo) / want < 1.25, f"{name}: width should be near 2 x 1.96 x sqrt(p(1-p)/100) = {want:.3f}; got {hi - lo:.3f}"
    small = mod.bootstrap_rate_cis([P] * 10 + [F] * 190, [P] * 8 + [F] * 2 + [F] * 150 + [P] * 40, B=1500, seed=2)
    w = small["tpr"][1] - small["tpr"][0]
    assert 0.35 < w < 0.65, (f"only 10 items are human-PASS, so the TPR interval is wide (about 0.5); got width {w:.2f}. "
                              "Resample the human-PASS items for TPR and the human-FAIL items for TNR, separately")

    th = [x["human"] for x in test]
    tj = oracle_verdicts(test)
    cm = mod.confusion(th, tj)
    r = mod.rates(cm)
    cis = mod.bootstrap_rate_cis(th, tj, B=1000, seed=0)
    for name in ("tpr", "tnr"):
        assert cis[name][0] <= r[name] <= cis[name][1], f"{name} {r[name]:.3f} should lie inside its interval {cis[name]}"
    wt, wn = cis["tpr"][1] - cis["tpr"][0], cis["tnr"][1] - cis["tnr"][0]
    assert wn > wt, f"TNR is estimated from fewer, harder items and a lower rate: its interval should be wider than TPR's ({wn:.3f} vs {wt:.3f})"
    return (f"held-out test half ({len(test)} items): TPR {r['tpr']:.1%} (95% CI {cis['tpr'][0]:.1%} to {cis['tpr'][1]:.1%}), "
            f"TNR {r['tnr']:.1%} ({cis['tnr'][0]:.1%} to {cis['tnr'][1]:.1%}), kappa {mod.cohen_kappa(cm):.2f}")


# =============================================================================
# Milestone 3: position bias and the swap test
# =============================================================================
def m3():
    pairs = [(f"q{i}", f"good{i}", f"bad{i}") for i in range(4)]
    calls = []

    def scripted(q, first, second):
        calls.append((q, first, second))
        if q == "q0":
            return "A" if first.startswith("good") else "B"          # always right
        if q == "q1":
            return "A"                                                # always the first slot
        if q == "q2":
            return "B"                                                # always the second slot
        return "A" if first.startswith("bad") else "B"                # always wrong

    r = mod.swap_test(pairs, scripted)
    assert len(calls) == 8 and len(set(calls)) == 8, f"each of the 4 pairs is judged twice, in both orders: 8 distinct calls expected; got {len(calls)}"
    assert ("q0", "good0", "bad0") in calls and ("q0", "bad0", "good0") in calls, "one call with the good answer first, one with the bad answer first"
    want = {"first_slot_rate": 0.5, "good_first": 0.5, "good_second": 0.5, "strict_win": 0.25, "strict_loss": 0.25,
            "consistent": 0.5, "swap_score": 0.5}
    for k, v in want.items():
        assert near(r[k], v), f"scripted judge, key {k!r}: expected {v}, got {r.get(k)}  (full result {r})"

    r = mod.swap_test(pairs, lambda q, a, b: "A")
    assert near(r["first_slot_rate"], 1.0) and near(r["good_first"], 1.0) and near(r["good_second"], 0.0) and near(r["consistent"], 0.0) \
        and near(r["swap_score"], 0.5), (f"a judge that always says 'A' ignores the content: first_slot_rate 1, good_first 1, good_second 0, "
                                         f"consistent 0, swap_score 0.5; got {r}")
    r = mod.swap_test(pairs, lambda q, a, b: "A" if a.startswith("good") else "B")
    assert near(r["strict_win"], 1.0) and near(r["swap_score"], 1.0) and near(r["first_slot_rate"], 0.5), "a perfect judge wins every pair in both orders"

    real_pairs = mod.make_pairs(LAB)
    assert len(real_pairs) == 69, f"make_pairs (given) should find 69 pairs with one human-PASS and one human-FAIL answer; got {len(real_pairs)}"
    r = mod.swap_test(real_pairs)
    a_picks = good_first = good_second = 0
    for q, g, b in real_pairs:
        v1, v2 = J.judge_pair(q, g, b), J.judge_pair(q, b, g)
        a_picks += (v1 == "A") + (v2 == "A")
        good_first += v1 == "A"
        good_second += v2 == "B"
    n = len(real_pairs)
    assert near(r["first_slot_rate"], a_picks / (2 * n)) and near(r["good_first"], good_first / n) and near(r["good_second"], good_second / n), \
        "on the real judge your numbers differ from an independent count of the same 2 x 69 judgments"
    assert r["first_slot_rate"] > 0.54, "the stand-in judge has a position bias: it should pick slot A clearly more often than half the time"
    assert r["good_first"] - r["good_second"] > 0.10, "the good answer wins more often when shown first: that gap is the position bias"
    assert 0.5 <= r["swap_score"] <= 1.0 and r["strict_win"] + r["strict_loss"] + (1 - r["consistent"]) > 0.99
    return (f"{n} pairs, each judged in both orders: slot A chosen {r['first_slot_rate']:.1%} of the time\n"
            f"  good answer wins {r['good_first']:.1%} when shown first, {r['good_second']:.1%} when shown second\n"
            f"  same verdict in both orders {r['consistent']:.1%} (win {r['strict_win']:.1%}, loss {r['strict_loss']:.1%}); swap score {r['swap_score']:.1%}")


# =============================================================================
# Milestone 4: length bias and the padding probe
# =============================================================================
def m4():
    pad = mod.pad_answer
    sentence = mod.PAD_SENTENCE
    assert pad("Hello there.", 0) == "Hello there." and pad("Hello there.", -5) == "Hello there.", "extra_words <= 0 leaves the answer alone"
    assert pad("Hello there.", 6) == "Hello there. " + sentence, f"6 extra words is exactly one filler sentence after a single space; got {pad('Hello there.', 6)!r}"
    assert pad("Hello there.", 7) == "Hello there. " + sentence + " " + sentence, "7 extra words needs two sentences (round up)"
    long = pad("x", 80)
    assert len(long.split()) == 1 + 14 * 6 and long.startswith("x "), f"80 extra words rounds up to 14 sentences = 84 words; got {len(long.split()) - 1}"

    items = [{"question": "q", "answer": "a b c"}, {"question": "q", "answer": "d e"}, {"question": "q", "answer": " ".join(["w"] * 25)}]

    def length_judge(q, a):
        return P if len(a.split()) >= 20 else F

    r = mod.padding_probe(items, length_judge, extra_words=30)
    assert (r["n_fail"], r["n_pass"]) == (2, 1), f"before padding the judge fails 2 short answers and passes 1; got n_fail={r['n_fail']} n_pass={r['n_pass']}"
    assert near(r["fail_to_pass"], 1.0) and near(r["pass_to_fail"], 0.0), "a judge that counts words: padding turns every FAIL into a PASS and no PASS into a FAIL"
    r = mod.padding_probe(items, length_judge, extra_words=12)
    assert near(r["fail_to_pass"], 0.0), "12 extra words is two filler sentences, so the short answers reach only 15 and 14 words: still below the judge's 20"
    r2 = mod.padding_probe(items, lambda q, a: F if sentence in a else P, extra_words=10)
    assert near(r2["pass_to_fail"], 1.0) and r2["fail_to_pass"] is None, "a judge that punishes padding: every PASS flips to FAIL; no item was failed before, so fail_to_pass is None"
    r3 = mod.padding_probe(items[:1], lambda q, a: F, extra_words=10)
    assert r3["pass_to_fail"] is None and r3["n_pass"] == 0, "no passes before padding: pass_to_fail is None"

    # the real judge, against an independent implementation of the probe
    prev = -1.0
    out = {}
    for extra in (20, 40, 80):
        got = mod.padding_probe(LAB, extra_words=extra)
        nf = f2p = npass = p2f = 0
        reps = -(-extra // 6)
        for it in LAB:
            before = J.judge_single(it["question"], it["answer"])
            after = J.judge_single(it["question"], it["answer"] + (" " + sentence) * reps)
            if before == F:
                nf += 1
                f2p += after == P
            else:
                npass += 1
                p2f += after == F
        assert got["n_fail"] == nf and got["n_pass"] == npass, f"extra={extra}: before padding expected {nf} fails and {npass} passes; got {got['n_fail']} and {got['n_pass']}"
        assert near(got["fail_to_pass"], f2p / nf) and near(got["pass_to_fail"], p2f / npass), f"extra={extra}: flip rates differ from the independent count"
        assert got["fail_to_pass"] >= prev, "more padding must not flip fewer answers"
        prev = got["fail_to_pass"]
        out[extra] = got
    assert out[40]["fail_to_pass"] > 0.3 and out[80]["fail_to_pass"] > 0.6 and out[80]["pass_to_fail"] < 0.05, \
        "the stand-in judge likes length: 80 words of fluff should flip a majority of its FAILs to PASS and almost no PASS to FAIL"
    prod = mod.padding_probe(PROD[:300], extra_words=40)
    assert prod["fail_to_pass"] > 0.3, "the probe needs no human labels: it works on unlabelled production answers too"
    return ("padding with fluff that carries no information, on the 200 labelled answers:\n"
            + "\n".join(f"  +{e} words: {o['fail_to_pass']:.1%} of the judge's {o['n_fail']} FAILs become PASS; {o['pass_to_fail']:.1%} of its PASSes become FAIL"
                        for e, o in out.items())
            + f"\n  (+40 words on 300 unlabelled production answers: {prod['fail_to_pass']:.1%} of FAILs flip)")


# =============================================================================
# Milestone 5: correct the estimate
# =============================================================================
def m5():
    rg = mod.rogan_gladen
    assert near(rg(0.70, 0.96, 0.67), 0.5873, 1e-3), \
        f"chapter 3: observed 0.70, TPR 0.96, TNR 0.67 -> (0.70 + 0.67 - 1) / 0.63 = 0.587; got {rg(0.70, 0.96, 0.67):.4f}"
    assert near(rg(0.7025, 0.95, 0.60), 0.55, 1e-9), "chapter 3's check: 0.55 x 0.95 + 0.45 x 0.40 = 0.7025 observed, so the truth was 0.55"
    assert rg(0.2, 0.9, 0.8) == 0.0, "(0.2 + 0.8 - 1) / 0.7 = 0"
    assert rg(0.1, 0.9, 0.8) == 0.0, "a negative estimate (-0.14) is clipped to 0.0"
    assert rg(0.95, 0.9, 0.8) == 1.0, "an estimate above 1 (1.07) is clipped to 1.0"
    assert near(rg(0.42, 1.0, 1.0), 0.42), "a perfect judge needs no correction"
    for tpr, tnr in [(0.6, 0.4), (0.5, 0.5), (0.3, 0.6)]:
        assert raises(ValueError, rg, 0.5, tpr, tnr), f"TPR + TNR - 1 <= 0 (here {tpr + tnr - 1:+.1f}): no discriminating power, raise ValueError"

    h = [P] * 10 + [F] * 10
    j = [P] * 9 + [F] + [F] * 7 + [P] * 3
    prod = [P] * 60 + [F] * 40
    c = mod.correct_pass_rate(h, j, prod)
    assert near(c["observed"], 0.6) and near(c["tpr"], 0.9) and near(c["tnr"], 0.7) and near(c["corrected"], 0.5), \
        f"toy calibration: TPR 0.9, TNR 0.7, observed 0.6 -> corrected (0.6 + 0.7 - 1) / 0.6 = 0.5; got {c}"

    perfect = mod.corrected_ci(h, h, prod, B=1500, seed=3)
    want = 2 * 1.96 * math.sqrt(0.6 * 0.4 / 100)
    assert 0.75 < (perfect[1] - perfect[0]) / want < 1.25, ("a perfect judge adds no calibration uncertainty: the interval is just the sampling "
                                                              f"interval of the production rate (about {want:.3f} wide); got {perfect[1] - perfect[0]:.3f}")
    tiny = mod.corrected_ci([P, F, F], [P, F, F], [P, P, F, F], B=300, seed=1)
    assert len(tiny) == 2 and tiny[0] <= tiny[1], "resamples that contain no human-PASS item must be skipped, not crash"

    hv = oracle_verdicts(LAB)
    pv = oracle_verdicts(PROD)
    c = mod.correct_pass_rate(HUMAN, hv, pv)
    obs = sum(v == P for v in pv) / len(pv)
    assert near(c["observed"], obs), f"observed is the share of production answers the judge passes: {obs:.4f}; got {c['observed']:.4f}"
    err_raw, err_cor = abs(obs - PRODUCTION_TRUTH), abs(c["corrected"] - PRODUCTION_TRUTH)
    assert err_cor < err_raw / 2, (f"the corrected estimate {c['corrected']:.3f} should be much closer to the true pass rate {PRODUCTION_TRUTH} "
                                   f"than the judge's raw {obs:.3f}")
    lo, hi = mod.corrected_ci(HUMAN, hv, pv, B=2000, seed=0)
    assert (lo, hi) == mod.corrected_ci(HUMAN, hv, pv, B=2000, seed=0), "same seed, same interval"
    assert lo < c["corrected"] < hi, f"the interval ({lo:.3f}, {hi:.3f}) should contain the point estimate {c['corrected']:.3f}"
    assert lo < PRODUCTION_TRUTH < hi, f"the interval ({lo:.3f}, {hi:.3f}) should contain the true pass rate {PRODUCTION_TRUTH}"
    naive = 2 * 1.96 * math.sqrt(obs * (1 - obs) / len(pv))
    assert 1.3 * naive < hi - lo < 0.2, (f"the weak judge magnifies the noise by 1 / (TPR + TNR - 1) and the TPR/TNR estimates add their own: "
                                         f"expected a width between {1.3 * naive:.3f} and 0.20; got {hi - lo:.3f}. "
                                         "Resample BOTH the calibration pairs and the production verdicts")
    return (f"judge says {obs:.1%} of 1,500 production answers pass; TPR {c['tpr']:.1%}, TNR {c['tnr']:.1%}\n"
            f"  corrected estimate {c['corrected']:.1%} (95% CI {lo:.1%} to {hi:.1%}); the planted truth is {PRODUCTION_TRUTH:.1%}\n"
            f"  the raw judge was {100 * (obs - PRODUCTION_TRUTH):+.1f} points off, the corrected estimate {100 * (c['corrected'] - PRODUCTION_TRUTH):+.1f}")


MILESTONES = [
    (1, "Milestone 1: confusion matrix, TPR, TNR and kappa", m1),
    (2, "Milestone 2: an honest split and error bars on the rates", m2),
    (3, "Milestone 3: position bias and the swap test", m3),
    (4, "Milestone 4: length bias and the padding probe", m4),
    (5, "Milestone 5: correct the pass rate, with an interval", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 2 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
