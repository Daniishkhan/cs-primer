"""Self-check for Lab 1: An Eval Harness with Error Bars.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 7     # milestone 3, replaying ONLY the random trials of seed 7

Everything is synthetic and seeded: the cases, the stand-in assistant, the bootstrap resamples. There
is no network and no real model, so every run gives identical numbers. The whole check finishes in
a few seconds. Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import json
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
from assistant import make_assistant  # noqa: E402

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


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception:
        return False
    return False


CASES_TEXT = open(os.path.join(HERE, "cases.jsonl"), encoding="utf-8").read()
REPLIES = json.load(open(os.path.join(HERE, "replies.json"), encoding="utf-8"))


def load_real():
    return mod.load_cases(CASES_TEXT)


def oracle_scores(version, cases, k):
    """Independent per-case scores: a reply is a pass iff it is the stand-in's 'good' reply."""
    system = make_assistant(version)
    scores, errors = [], 0
    for c in cases:
        ok = 0
        for s in range(k):
            try:
                ok += system(c["input"], s) == REPLIES[c["id"]]["good"]
            except TimeoutError:
                errors += 1
        scores.append(ok / k)
    return scores, errors


# =============================================================================
# Milestone 1: cases as data, assertions
# =============================================================================
def m1():
    text = ('{"id": "a", "input": "hi", "checks": [{"type": "contains", "value": "x"}]}\n'
            "\n"
            '{"id": "b", "input": "yo", "group": "g1", "tags": ["t"], "checks": [{"type": "max_words", "value": 3}]}\n')
    cs = mod.load_cases(text)
    assert [c["id"] for c in cs] == ["a", "b"], f"blank lines must be skipped and order kept; got {[c.get('id') for c in cs]}"
    assert cs[0]["group"] == "a" and cs[0]["tags"] == [], "a case without group/tags gets group = its id and tags = []"
    assert cs[1]["group"] == "g1" and cs[1]["tags"] == ["t"], "given group and tags are kept"
    good = '{"id": "a", "input": "hi", "checks": [{"type": "contains", "value": "x"}]}'
    for label, bad in [("duplicate id", good + "\n" + good), ("invalid JSON", good + "\n{not json"),
                       ("missing input", '{"id": "z", "checks": [{"type": "contains", "value": "x"}]}'),
                       ("missing id", '{"input": "q", "checks": [{"type": "contains", "value": "x"}]}'),
                       ("empty checks", '{"id": "z", "input": "q", "checks": []}'),
                       ("missing checks", '{"id": "z", "input": "q"}'),
                       ("a JSON list instead of an object", '[1, 2]')]:
        assert raises(ValueError, mod.load_cases, bad), f"load_cases must raise ValueError for {label}"
    real = load_real()
    assert len(real) == 160 and len({c["id"] for c in real}) == 160, f"cases.jsonl has 160 cases; got {len(real)}"
    assert len({c["group"] for c in real}) == 40, "40 groups of 4 paraphrases"

    rc = mod.run_check
    table = [
        ({"type": "contains", "value": "30 days"}, "Within 30 days.", True),
        ({"type": "contains", "value": "30 days"}, "Within 60 days.", False),
        ({"type": "not_contains", "value": "60 days"}, "Within 30 days.", True),
        ({"type": "not_contains", "value": "60 days"}, "Sure, 60 days!", False),
        ({"type": "not_regex", "pattern": r"(?i)\bI have cancel"}, "i have cancelled it", False),
        ({"type": "not_regex", "pattern": r"(?i)\bI have cancel"}, "Cancellation needs your order number", True),
        ({"type": "json_keys", "keys": ["order", "status"]}, '{"order": 1, "status": "ok", "x": 2}', True),
        ({"type": "json_keys", "keys": ["order", "status"]}, '{"order": 1}', False),
        ({"type": "json_keys", "keys": ["order", "status"]}, "Order 1 has shipped.", False),
        ({"type": "json_keys", "keys": ["order"]}, "[1, 2, 3]", False),
        ({"type": "number_close", "expected": 1204.5, "rel_tol": 0.005}, "The total is $1,204.50", True),
        ({"type": "number_close", "expected": 1204.5, "rel_tol": 0.005}, "So 1204.5 dollars.", True),
        ({"type": "number_close", "expected": 1204.5, "rel_tol": 0.005}, "The total is $1,240.50", False),
        ({"type": "number_close", "expected": 1204.5, "rel_tol": 0.005}, "I could not find the total.", False),
        ({"type": "number_close", "expected": 1204.5, "rel_tol": 0.005}, "Item 3 costs 1204.50 but the total is 12.0", False),
        ({"type": "number_close", "expected": 100, "rel_tol": 0.01}, "about 101", True),
        ({"type": "number_close", "expected": 100, "rel_tol": 0.01}, "about 101.5", False),
        ({"type": "max_words", "value": 3}, "one two three", True),
        ({"type": "max_words", "value": 3}, "one two three four", False),
    ]
    for chk, out, want in table:
        got = rc(out, chk)
        assert isinstance(got, tuple) and len(got) == 2, f"run_check must return (ok, reason); got {got!r}"
        assert bool(got[0]) is want, f"run_check({out!r}, {chk}) should be {'ok' if want else 'a failure'}, got ok={got[0]}"
        if not want:
            assert got[1], f"a failing check must give a reason (so a failing case can be debugged); got {got[1]!r} for {chk['type']}"
    assert raises(ValueError, rc, "x", {"type": "contians", "value": "x"}), \
        "an unknown check type must raise ValueError: a typo in a case file must not pass silently"

    assert mod.grade("Within 30 days.", [{"type": "contains", "value": "30 days"},
                                         {"type": "not_contains", "value": "60 days"}]) == []
    why = mod.grade("Sure! 60 days.", [{"type": "contains", "value": "30 days"}, {"type": "not_contains", "value": "60 days"}])
    assert len(why) == 2, f"grade returns one reason per failed check (2 here); got {why!r}"

    # scenario: every case's checks must pass its good reply and fail its bad reply
    for c in real:
        g = mod.grade(REPLIES[c["id"]]["good"], c["checks"])
        b = mod.grade(REPLIES[c["id"]]["bad"], c["checks"])
        assert g == [], f"case {c['id']}: the good reply {REPLIES[c['id']]['good']!r} should pass every check; failed with {g}"
        assert b != [], f"case {c['id']}: the bad reply {REPLIES[c['id']]['bad']!r} should fail at least one check, but passed"
    return "all 160 cases: the known-good reply passes every check and the known-bad reply fails at least one"


# =============================================================================
# Milestone 2: runner and summary
# =============================================================================
def m2():
    cs = [{"id": "c1", "group": "g", "tags": ["x", "y"], "input": "p1", "checks": [{"type": "contains", "value": "ok"}]},
          {"id": "c2", "group": "g", "tags": ["x"], "input": "p2", "checks": [{"type": "contains", "value": "ok"}]},
          {"id": "c3", "group": "h", "tags": [], "input": "p3", "checks": [{"type": "contains", "value": "ok"}]}]
    calls = []

    def system(prompt, sample):
        calls.append((prompt, sample))
        if prompt == "p2" and sample == 1:
            raise TimeoutError("boom")
        if prompt == "p3" and sample == 0:
            raise KeyError("x")
        return "ok" if (prompt == "p1" or sample == 2) else "nope"

    res = mod.run_suite(system, cs, k=3)
    assert [r.id for r in res] == ["c1", "c2", "c3"], "one Result per case, in case order"
    assert calls.count(("p1", 0)) == 1 and len(calls) == 9, f"expected 3 cases x 3 attempts = 9 calls, got {len(calls)}"
    assert sorted({s for _, s in calls}) == [0, 1, 2], "the attempt index passed to the system runs 0..k-1"
    want = {"c1": ["pass", "pass", "pass"], "c2": ["fail", "error", "pass"], "c3": ["error", "fail", "pass"]}
    for r in res:
        assert list(r.outcomes) == want[r.id], f"{r.id}: expected outcomes {want[r.id]}, got {list(r.outcomes)} (an exception is an 'error', a failed check a 'fail')"
    assert res[0].group == "g" and list(res[0].tags) == ["x", "y"], "Result carries the case's group and tags"
    assert len(res[1].reasons) == 3 and res[1].reasons[0] and res[1].reasons[1] == [] and res[1].reasons[2] == [], \
        "reasons has one entry per attempt: the failed-check reasons for a fail, [] for a pass or an error"
    assert near(res[1].score, 1 / 3), "a case with outcomes fail, error, pass scores 1/3: an error is NOT a pass but stays in the denominator"

    s = mod.summarise(res)
    assert s["n"] == 3 and s["attempts"] == 9 and s["errors"] == 2, f"n/attempts/errors should be 3/9/2; got {s['n']}/{s['attempts']}/{s['errors']}"
    assert near(s["score"], (1 + 1 / 3 + 1 / 3) / 3), f"overall score is the mean of per-case scores (5/9); got {s['score']}"
    assert set(s["by_tag"]) == {"x", "y"}, f"by_tag has one entry per tag that occurs; got {sorted(s['by_tag'])}"
    assert s["by_tag"]["x"]["n"] == 2 and near(s["by_tag"]["x"]["score"], (1 + 1 / 3) / 2), f"tag x covers c1 and c2: {s['by_tag']['x']}"
    assert s["by_tag"]["y"]["n"] == 1 and near(s["by_tag"]["y"]["score"], 1.0)
    assert mod.run_suite(lambda p, k: "ok", cs, k=1)[0].outcomes == ["pass"], "k defaults to 1"

    real = load_real()
    note = []
    for v in (1, 2, 3):
        res = mod.run_suite(make_assistant(v), real, k=3)
        s = mod.summarise(res)
        want_scores, want_err = oracle_scores(v, real, 3)
        got = [r.score for r in res]
        bad = [(r.id, g, w) for r, g, w in zip(res, got, want_scores) if not near(g, w)]
        assert not bad, f"assistant v{v}: case scores differ from the independent oracle, e.g. {bad[:2]} (id, yours, expected)"
        assert s["errors"] == want_err and s["n"] == 160 and s["attempts"] == 480, \
            f"assistant v{v}: expected 160 cases, 480 attempts, {want_err} errors; got {s['n']}, {s['attempts']}, {s['errors']}"
        assert near(s["score"], sum(want_scores) / 160)
        assert set(s["by_tag"]) == {"refund", "status", "billing", "cancel", "privacy", "critical"}
        note.append(f"v{v}: score {s['score']:.1%} over {s['n']} cases x 3 attempts, {s['errors']} timeouts counted as errors, "
                    f"weakest tag {min(s['by_tag'], key=lambda t: s['by_tag'][t]['score'])}")
    return "\n".join(note)


# =============================================================================
# Milestone 3: error bars
# =============================================================================
def m3():
    m, se = mod.mean_se([1, 2, 3, 4])
    assert near(m, 2.5) and near(se, math.sqrt((5 / 3) / 4)), f"mean_se([1,2,3,4]) = (2.5, 0.6455); got ({m}, {se})"
    assert mod.mean_se([5.0])[1] == 0.0, "one value has no spread: standard error 0.0"
    for k, n, lo, hi in [(20, 20, 0.8389, 1.0), (3, 50, 0.0206, 0.1622), (45, 50, 0.7864, 0.9565), (0, 10, 0.0, 0.2775)]:
        a, b = mod.wilson(k, n)
        assert near(a, lo, 5e-4) and near(b, hi, 5e-4), f"wilson({k}, {n}) should be ({lo}, {hi}); got ({a:.4f}, {b:.4f})"
    assert mod.wilson(7, 10)[0] < 0.7 < mod.wilson(7, 10)[1], "the Wilson interval contains the observed rate"

    se = mod.clustered_se([1, 1, 0, 0], ["a", "a", "b", "b"])
    assert near(se, 0.38188, 1e-4), (f"two clusters of two, identical within a cluster: SE^2 = 0.0833 (naive) + 1/16 (cross terms) = 0.1458, "
                                      f"so 0.3819; got {se:.4f}")
    xs = [random.Random(4).random() for _ in range(30)]
    assert near(mod.clustered_se(xs, list(range(30))), mod.mean_se(xs)[1], 1e-12), \
        "when every item is its own cluster there are no cross terms: clustered SE = naive SE"
    rng = random.Random(9)
    cl = [rng.random() < 0.5 for _ in range(60)]
    scores = [1.0 if c else 0.0 for c in cl for _ in range(5)]
    gr = [i for i in range(60) for _ in range(5)]
    ratio = mod.clustered_se(scores, gr) / mod.mean_se(scores)[1]
    assert 2.0 < ratio < 2.4, (f"60 clusters of 5 identical answers are worth about 60 independent ones: the clustered SE should be about "
                               f"sqrt(5) = 2.2 times the naive one; got {ratio:.2f}")

    # bootstrap
    assert mod.bootstrap_ci([1.0] * 50) == (1.0, 1.0), "all values equal: the interval collapses to that value"
    xs = [1 if random.Random(i).random() < 0.7 else 0 for i in range(300)]
    lo, hi = mod.bootstrap_ci(xs, B=2000, seed=3)
    mean = sum(xs) / 300
    assert lo < mean < hi, f"the interval ({lo:.3f}, {hi:.3f}) should contain the observed mean {mean:.3f}"
    assert mod.bootstrap_ci(xs, B=2000, seed=3) == (lo, hi), "same seed, same interval: use random.Random(seed)"
    se = mod.mean_se(xs)[1]
    assert 0.85 < (hi - lo) / (2 * 1.96 * se) < 1.15, \
        f"for a plain mean the bootstrap width should be close to 2 x 1.96 x SE = {2 * 1.96 * se:.3f}; got {hi - lo:.3f}"
    w80 = mod.bootstrap_ci(xs, alpha=0.2, B=2000, seed=3)
    assert w80[1] - w80[0] < hi - lo and (w80[0] > lo or w80[1] < hi), "alpha=0.2 gives a narrower (80%) interval than alpha=0.05"
    keep = list(xs)
    mod.bootstrap_ci(xs, ["g"] * 300, B=10)
    assert xs == keep, "bootstrap_ci must not modify its input"
    # whole groups, not single items: one lone 0 in group x, nine 1s in group y -> pooled means can only be 0, 0.9 or 1
    lo2, hi2 = mod.bootstrap_ci([0.0] + [1.0] * 9, ["x"] + ["y"] * 9, B=2000, seed=1)
    assert lo2 in (0.0, 0.9, 1.0) and hi2 in (0.0, 0.9, 1.0), (
        f"resampling whole groups of sizes 1 and 9 can only produce means 0, 0.9 or 1.0; your interval ({lo2:.3f}, {hi2:.3f}) "
        "means you resampled single items, or averaged group means instead of pooling the values")
    assert (lo2, hi2) == (0.0, 1.0), f"with these groups the 95% interval is (0.0, 1.0); got ({lo2}, {hi2})"
    # coverage: a 95% interval should cover the truth about 95% of the time
    cov, trials = 0, 0
    for s in seeds(range(120)):
        r = random.Random(s)
        data = [1 if r.random() < 0.7 else 0 for _ in range(100)]
        a, b = mod.bootstrap_ci(data, B=300, seed=s)
        cov += a <= 0.7 <= b
        trials += 1
    if ONLY_SEED is None:
        assert 0.88 <= cov / trials <= 0.995, f"a 95% interval covered the true rate in {cov}/{trials} simulated evals; expected about 95%"

    # the clustered fixture: the honest interval is much wider than the naive one
    real = load_real()
    res = mod.run_suite(make_assistant(2), real, k=3)
    sc = [r.score for r in res]
    gr = [r.group for r in res]
    naive = mod.bootstrap_ci(sc, B=2000, seed=0)
    grouped = mod.bootstrap_ci(sc, gr, B=2000, seed=0)
    se_n, se_c = mod.mean_se(sc)[1], mod.clustered_se(sc, gr)
    wn, wg = naive[1] - naive[0], grouped[1] - grouped[0]
    assert wg > 1.5 * wn, (f"scores of paraphrases move together, so resampling whole groups must give a much wider interval than "
                           f"resampling cases: grouped {wg:.3f} vs per-case {wn:.3f}")
    assert 0.8 < wg / (2 * 1.96 * se_c) < 1.2, f"the group bootstrap ({wg:.3f}) should agree with 2 x 1.96 x clustered SE ({2 * 1.96 * se_c:.3f})"
    return (f"assistant v2, {len(sc)} cases in {len(set(gr))} groups: score {sum(sc) / len(sc):.1%}\n"
            f"  per-case bootstrap  {naive[0]:.1%} to {naive[1]:.1%}  (width {wn:.1%}, SE {se_n:.1%})\n"
            f"  per-group bootstrap {grouped[0]:.1%} to {grouped[1]:.1%}  (width {wg:.1%}, clustered SE {se_c:.1%})")


# =============================================================================
# Milestone 4: paired comparison and the diff
# =============================================================================
def m4():
    a = [1, 1, 0, 0, 1, 0]
    b = [1, 1, 1, 0, 1, 1]
    p = mod.paired_stats(a, b)
    d = [y - x for x, y in zip(a, b)]
    assert near(p["diff"], 1 / 3), f"diff is the mean of b - a = 1/3; got {p['diff']}"
    assert near(p["se_paired"], math.sqrt((12 / 45) / 6)), f"se_paired = sd(b - a) / sqrt(n) = 0.2108; got {p['se_paired']:.4f}"
    se_a = math.sqrt(0.3 / 6)
    se_b = math.sqrt((5 / 6 * 1 / 6 * 6 / 5) / 6)
    assert near(p["se_unpaired"], math.sqrt(se_a ** 2 + se_b ** 2), 1e-9), \
        f"se_unpaired = sqrt(se_a^2 + se_b^2) = {math.sqrt(se_a ** 2 + se_b ** 2):.4f}; got {p['se_unpaired']:.4f}"
    assert near(p["z_paired"], p["diff"] / p["se_paired"]) and near(p["z_unpaired"], p["diff"] / p["se_unpaired"])
    assert p["a_only"] == 0 and p["b_only"] == 2, f"b beats a on 2 cases and a never beats b; got a_only={p['a_only']}, b_only={p['b_only']}"
    assert near(p["corr"], 0.5 / math.sqrt(1.25), 1e-9), f"Pearson correlation of these a and b is 0.4472; got {p['corr']}"
    same = mod.paired_stats([1, 0, 1, 1], [1, 0, 1, 1])
    assert same["diff"] == 0 and same["z_paired"] == 0.0 and same["z_unpaired"] == 0.0, "identical scores: diff 0 and z 0.0 (no division by zero)"
    flat = mod.paired_stats([1, 1, 1], [1, 1, 1])
    assert flat["corr"] == 0.0 and flat["se_paired"] == 0.0, "no spread: correlation 0.0 and SE 0.0, not a ZeroDivisionError"

    ratios = []
    for s in seeds((1, 2, 3, 4, 5)):
        r = random.Random(s)
        hard = [r.gauss(0, 1) for _ in range(300)]
        sa = [1 if 0.0 + r.gauss(0, 0.35) > h else 0 for h in hard]
        sb = [1 if 0.15 + r.gauss(0, 0.35) > h else 0 for h in hard]
        q = mod.paired_stats(sa, sb)
        assert q["corr"] > 0.4, f"seed {s}: systems that face the same questions should have correlated scores; got {q['corr']:.2f}"
        assert q["se_paired"] < 0.85 * q["se_unpaired"], f"seed {s}: pairing should shrink the standard error (paired {q['se_paired']:.4f}, unpaired {q['se_unpaired']:.4f})"
        ratios.append(q["se_unpaired"] / q["se_paired"])
        ind = mod.paired_stats(sa, [1 if r.random() < 0.6 else 0 for _ in range(300)])
        assert abs(ind["se_paired"] / ind["se_unpaired"] - 1) < 0.1, f"seed {s}: independent scores should give about equal SEs"

    R = mod.Result
    ra = [R("c", "g1", ["t1"], ["fail"]), R("a", "g1", ["t1", "t2"], ["pass"]), R("b", "g2", ["t2"], ["pass", "fail"]),
          R("d", "g2", [], ["fail", "fail"])]
    rb = [R("a", "g1", ["t1", "t2"], ["fail"]), R("b", "g2", ["t2"], ["pass", "pass"]), R("c", "g1", ["t1"], ["pass"]),
          R("d", "g2", [], ["pass", "fail"])]
    dr = mod.diff_runs(ra, rb)
    assert dr["fixed"] == ["b", "c", "d"] and dr["regressed"] == ["a"], (
        "runs are matched by id, not position; a case is fixed when its score rises by at least min_change (default 0.5): "
        f"expected fixed ['b', 'c', 'd'] and regressed ['a']; got fixed {dr['fixed']}, regressed {dr['regressed']}")
    strict = mod.diff_runs(ra, rb, min_change=1.0)
    assert strict["fixed"] == ["c"] and strict["regressed"] == ["a"], \
        f"min_change=1.0 keeps only the full fail -> pass and pass -> fail flips; got fixed {strict['fixed']}, regressed {strict['regressed']}"
    bt = dr["by_tag"]
    assert near(bt["t1"], 0.0) and near(bt["t2"], (-1 + 0.5) / 2), f"by_tag: mean change in score per tag; t1 = (c +1, a -1)/2 = 0, t2 = (a -1, b +0.5)/2 = -0.25; got {bt}"
    assert raises(ValueError, mod.diff_runs, ra, rb[:3]), "runs over different ids cannot be compared: raise ValueError"

    real = load_real()
    r1 = mod.run_suite(make_assistant(1), real, k=3)
    r2 = mod.run_suite(make_assistant(2), real, k=3)
    p = mod.paired_stats([r.score for r in r1], [r.score for r in r2])
    assert p["z_paired"] > 2.5 and p["z_unpaired"] < 1.5, (f"v1 -> v2 is a real 5-point gain that the pairing can see and the unpaired SE hides; "
                                                           f"expected z_paired > 2.5 and z_unpaired < 1.5, got {p['z_paired']:.2f} and {p['z_unpaired']:.2f}")
    d12 = mod.diff_runs(r1, r2)
    assert len(d12["fixed"]) >= 5 * max(1, len(d12["regressed"])), f"expected many more fixes than regressions; got {len(d12['fixed'])} vs {len(d12['regressed'])}"
    return (f"v1 -> v2 on {len(real)} cases x 3 attempts: difference {p['diff']:+.1%}, correlation {p['corr']:.2f}\n"
            f"  unpaired SE {p['se_unpaired']:.2%} (z = {p['z_unpaired']:.2f})    paired SE {p['se_paired']:.2%} (z = {p['z_paired']:.2f})\n"
            f"  {len(d12['fixed'])} cases fixed, {len(d12['regressed'])} regressed")


# =============================================================================
# Milestone 5: power, verdict, the whole comparison
# =============================================================================
def m5():
    for delta, k, want in [(0.10, 1, 349), (0.05, 1, 1395), (0.03, 1, 3876), (0.02, 1, 8721), (0.05, 5, 558)]:
        got = mod.n_required(delta, 1 / 9, 1 / 6, 1 / 6, k, k)
        assert abs(got - want) < 1, f"n_required({delta}, 1/9, 1/6, 1/6, ka={k}, kb={k}) should be about {want} (chapter 4's table); got {got:.0f}"
    assert abs(mod.n_required(0.05, 1 / 9) - 349) < 1, "with no answer noise, 5 points needs 349 questions"
    assert abs(mod.n_required(0.05, 1 / 9, 1 / 6, 1 / 6, alpha=0.01) - 1395) > 100, "alpha is a parameter: a stricter alpha needs more questions"
    assert near(mod.mde(198, 1 / 9, 1 / 6, 1 / 6), 0.133, 5e-4), f"198 questions, K=1: minimum detectable effect 13.3 points; got {mod.mde(198, 1 / 9, 1 / 6, 1 / 6):.4f}"
    assert near(mod.mde(198, 1 / 9, 1 / 6, 1 / 6, 10, 10), 0.076, 5e-4), "198 questions, K=10: 7.6 points"
    for n in (100, 777, 5000):
        d = mod.mde(n, 0.1, 0.2, 0.15, 2, 3)
        assert near(mod.n_required(d, 0.1, 0.2, 0.15, 2, 3), n, 1e-6), f"mde and n_required must be inverses (n={n})"

    assert mod.verdict(0.01, 0.09) == "B better" and mod.verdict(-0.09, -0.01) == "A better"
    assert mod.verdict(-0.02, 0.08) == "cannot tell" and mod.verdict(0.0, 0.05) == "cannot tell" and mod.verdict(-0.05, 0.0) == "cannot tell", \
        "an interval that touches 0 is 'cannot tell'; a positive difference whose interval includes 0 is not evidence that B is better"

    cases = load_real()
    note = []
    a1, a2, a3 = make_assistant(1), make_assistant(2), make_assistant(3)

    r = mod.compare(a1, a2, cases, k=3)
    s1, e1 = oracle_scores(1, cases, 3)
    s2, e2 = oracle_scores(2, cases, 3)
    assert near(r["score_a"], sum(s1) / 160) and near(r["score_b"], sum(s2) / 160), "score_a and score_b are the mean per-case scores"
    want = sum(y - x for x, y in zip(s1, s2)) / 160
    assert near(r["diff"], want), f"diff should be {want:+.4f}; got {r['diff']:+.4f}"
    assert (r["errors_a"], r["errors_b"]) == (e1, e2), f"errors_a/errors_b count timeouts in each run: expected {(e1, e2)}, got {(r['errors_a'], r['errors_b'])}"
    lo, hi = r["diff_ci"]
    assert lo < r["diff"] < hi and r["ci_a"][0] < r["score_a"] < r["ci_a"][1] and r["ci_b"][0] < r["score_b"] < r["ci_b"][1], "every interval contains its point estimate"
    assert r["verdict"] == "B better" and lo > 0, f"v2 is truly better than v1 and 160 paired cases can show it; got verdict {r['verdict']!r}, interval ({lo:+.3f}, {hi:+.3f})"
    assert r["z_paired"] > 2.5 and r["z_unpaired"] < 1.5
    assert len(r["fixed"]) > 5 * max(1, len(r["regressed"]))
    assert r == mod.compare(a1, a2, cases, k=3), "compare must be deterministic: same inputs, same output"
    note.append(f"v1 -> v2: {r['score_a']:.1%} -> {r['score_b']:.1%}, difference {r['diff']:+.1%} (95% CI {lo:+.1%} to {hi:+.1%}): {r['verdict']}; "
                f"{len(r['fixed'])} fixed, {len(r['regressed'])} regressed")

    r = mod.compare(a2, a3, cases, k=3)
    lo, hi = r["diff_ci"]
    assert abs(r["diff"]) < 0.03 and r["verdict"] == "cannot tell", \
        f"v3 trades one skill for another: the overall change is tiny and the interval spans 0; got diff {r['diff']:+.3f}, verdict {r['verdict']!r}"
    assert r["by_tag"]["status"] < -0.25, f"v3 broke order-status JSON: the per-tag change for 'status' should be below -0.25; got {r['by_tag']['status']:+.2f}"
    assert r["by_tag"]["billing"] > 0.25, f"v3 is better at billing: expected a per-tag gain above +0.25; got {r['by_tag']['billing']:+.2f}"
    bad = [i for i in r["regressed"] if i.startswith("status-")]
    assert len(bad) >= 8, f"the regressed list should name the status cases that broke; found only {len(bad)} of them in {r['regressed']}"
    note.append(f"v2 -> v3: {r['score_a']:.1%} -> {r['score_b']:.1%}, difference {r['diff']:+.1%} (95% CI {lo:+.1%} to {hi:+.1%}): {r['verdict']}; "
                f"yet status {r['by_tag']['status']:+.0%}, billing {r['by_tag']['billing']:+.0%}, {len(bad)} status cases regressed")

    r = mod.compare(a2, a2, cases, k=3)
    assert r["diff"] == 0 and r["fixed"] == [] and r["regressed"] == [] and r["verdict"] == "cannot tell" and r["diff_ci"] == (0.0, 0.0), \
        "comparing a system with itself must give a zero difference, an empty diff and 'cannot tell'"
    note.append("v2 -> v2: difference +0.0%, no case changes, cannot tell (as it must)")
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: cases as data and assertions", m1),
    (2, "Milestone 2: the runner, errors and the summary", m2),
    (3, "Milestone 3: error bars, Wilson and the cluster bootstrap", m3),
    (4, "Milestone 4: paired comparison and the diff", m4),
    (5, "Milestone 5: power, a verdict and the whole comparison", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
