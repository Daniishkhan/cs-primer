"""Self-check for Lab 2: A Retrieval Evaluation Harness.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 5       # only milestone 5
    python3 check.py solution 5 3     # milestone 5, replaying ONLY the random scenario of seed 3

Everything is deterministic: the judgements and runs are files in this folder (qrels.txt,
run_*.txt, made by make_data.py), and every random scenario comes from a seeded
random.Random. No network, no clock. The whole check finishes in a few seconds.
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


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


SYSTEMS = ["bm25", "bm25-tuned", "hybrid"]

# Chapter 4's running example: grades at ranks 1..10, and two judged documents never retrieved.
RANKED = [3, 0, 2, 0, 0, 1, 0, 2, 0, 0]
MISSED = [2, 1]
EVERYTHING = RANKED + MISSED


# -----------------------------------------------------------------------------
# An independent oracle, written differently on purpose (plain loops, own parser)
# -----------------------------------------------------------------------------
def o_qrels(text):
    out = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        q, _, d, g = line.split()
        out.setdefault(q, {})[d] = int(g)
    return out


def o_run(text):
    tmp = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        q, _, d, _, s, _ = line.split()
        tmp.setdefault(q, []).append((-float(s), d))
    return {q: [d for _, d in sorted(v)] for q, v in tmp.items()}


def o_metrics(ranking, qrel, k=10):
    g = [qrel.get(d, 0) for d in ranking]
    R = sum(1 for v in qrel.values() if v >= 1)
    top = g[:k]
    p = sum(1 for v in top if v >= 1) / k
    r = sum(1 for v in top if v >= 1) / R
    rr = 0.0
    for i, v in enumerate(top, 1):
        if v >= 1:
            rr = 1 / i
            break
    precs = [sum(1 for u in g[:i] if u >= 1) / i for i in range(1, len(g) + 1) if g[i - 1] >= 1]
    ap = sum(precs) / R
    dcg = sum(v / math.log2(i + 1) for i, v in enumerate(top, 1))
    ideal = sorted(qrel.values(), reverse=True)[:k]
    idcg = sum(v / math.log2(i + 1) for i, v in enumerate(ideal, 1))
    return {"P@10": p, "R@10": r, "MRR@10": rr, "MAP": ap, "nDCG@10": dcg / idcg}


def o_scores(system, metric):
    qrels, run = o_qrels(read("qrels.txt")), o_run(read(f"run_{system}.txt"))
    return {q: o_metrics(run.get(q, []), qrel)[metric] for q, qrel in qrels.items() if any(v >= 1 for v in qrel.values())}


def o_boot(values, seed=99, n=4000):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n) - 1]


# =============================================================================
# Milestone 1: files to data structures
# =============================================================================
def m1():
    qrels = mod.parse_qrels("# header comment\nq1 0 dA 2\nq1 0 dB 0\n\nq2 0 dC 1\n   \nq1 0 dD 3\n")
    assert qrels == {"q1": {"dA": 2, "dB": 0, "dD": 3}, "q2": {"dC": 1}}, f"parse_qrels: skip blank and # lines, int grades; got {qrels}"
    assert mod.parse_qrels("") == {}, "empty text, no queries"
    for bad in ["q1 0 dA", "q1 0 dA 2 extra", "q1 dA 2"]:
        try:
            mod.parse_qrels("q0 0 d0 1\n" + bad)
        except ValueError as e:
            assert "2" in str(e), f"the error for a malformed qrels line should name the line number (here 2); got {e}"
        else:
            raise AssertionError(f"parse_qrels should raise ValueError for {bad!r}")

    text = ("# a comment\n"
            "q1 Q0 dX 9 3.0 sys\n"
            "q1 Q0 dB 1 2.5 sys\n"
            "q1 Q0 dA 2 2.5 sys\n"
            "q1 Q0 dX 3 0.5 sys\n"          # dX again, lower score: the 3.0 line stands
            "q2 Q0 dZ 1 -1.0 sys\n"
            "q2 Q0 dY 2 -3.0 sys\n"
            "q1 Q0 dC 4 2.0 sys\n")
    run = mod.parse_run(text)
    assert run == {"q1": ["dX", "dA", "dB", "dC"], "q2": ["dZ", "dY"]}, (
        "parse_run: order by score descending (the rank column is ignored), ties by docid ascending, "
        f"a repeated document counts once at its best score.\n      expected {{'q1': ['dX', 'dA', 'dB', 'dC'], 'q2': ['dZ', 'dY']}}\n      got      {run}")
    try:
        mod.parse_run("q1 Q0 dA 1 0.5")
    except ValueError:
        pass
    else:
        raise AssertionError("parse_run should raise ValueError for a line with 5 fields")

    assert mod.grades_for(["a", "b", "c", "d"], {"a": 2, "c": 0, "z": 3}) == [2, 0, 0, 0], \
        "grades_for: grade per ranked document, unjudged documents count as 0"
    assert mod.grades_for([], {"a": 1}) == [], "empty ranking, empty grades"

    q, r = mod.parse_qrels(read("qrels.txt")), mod.parse_run(read("run_hybrid.txt"))
    assert len(q) == 60 and len(r) == 60, f"qrels.txt and run_hybrid.txt each cover 60 queries; got {len(q)} and {len(r)}"
    assert all(len(v) == 20 for v in r.values()), "every query in the run has 20 distinct documents"
    assert q == o_qrels(read("qrels.txt")) and r == o_run(read("run_hybrid.txt")), "the parsed files differ from the oracle's parse"
    return f"qrels: {sum(len(v) for v in q.values())} judgements over {len(q)} queries; hybrid run: {sum(len(v) for v in r.values())} lines"


# =============================================================================
# Milestone 2: binary metrics
# =============================================================================
def m2():
    for k, p, r in [(1, 1.0, 1 / 6), (3, 2 / 3, 2 / 6), (5, 0.4, 2 / 6), (10, 0.4, 4 / 6)]:
        gp, gr = mod.precision_at_k(RANKED, k), mod.recall_at_k(RANKED, k, 6)
        assert near(gp, p), f"chapter 4's list: P@{k} should be {p:.4f}, got {gp}"
        assert near(gr, r), f"chapter 4's list: R@{k} should be {r:.4f}, got {gr}"
    assert near(mod.precision_at_k([1, 0, 1], 10), 0.2), "a list shorter than k still divides by k: P@10 of [1,0,1] is 0.2"
    assert near(mod.precision_at_k([3, 2, 1, 0], 4, thr=2), 0.5), "thr = 2 counts only grades 2 and 3"
    assert mod.recall_at_k([1, 1], 5, 0) == 0.0, "no relevant documents: return 0.0, do not divide by zero"
    try:
        mod.precision_at_k([1], 0)
    except ValueError:
        pass
    else:
        raise AssertionError("precision_at_k with k = 0 should raise ValueError")
    assert mod.hit_rate_at_k(RANKED, 1) == 1.0 and mod.hit_rate_at_k([0, 0, 1], 2) == 0.0 and mod.hit_rate_at_k([0, 0, 1], 3) == 1.0, \
        "hit_rate_at_k is 1.0 if any of the first k is relevant"
    assert near(mod.reciprocal_rank([0, 0, 2, 1]), 1 / 3), "reciprocal_rank: first relevant at rank 3 gives 1/3"
    assert mod.reciprocal_rank([0, 0, 0]) == 0.0 and mod.reciprocal_rank([]) == 0.0, "nothing relevant: 0.0"
    assert near(mod.reciprocal_rank([1, 3], thr=3), 0.5), "thr = 3: the first grade-3 result is at rank 2"
    ap = mod.average_precision(RANKED, 6)
    assert near(ap, (1 + 2 / 3 + 3 / 6 + 4 / 8) / 6), f"chapter 4's AP is 0.444 ((1 + 2/3 + 3/6 + 4/8) / 6); got {ap}"
    assert near(mod.average_precision([1, 0, 1], 4), (1 + 2 / 3) / 4), \
        "AP divides by ALL relevant documents (4 here), so the two never retrieved count as zeros"
    assert near(mod.average_precision([1, 1, 1], 3), 1.0) and mod.average_precision([0, 0], 3) == 0.0 and mod.average_precision([], 0) == 0.0, \
        "AP: a perfect list is 1.0, nothing relevant is 0.0"

    for s in seeds(range(1, 9)):
        rng = random.Random(s)
        for _ in range(30):
            g = [rng.choice([0, 0, 0, 1, 2, 3]) for _ in range(rng.randint(0, 25))]
            n_rel = sum(1 for v in g if v >= 1) + rng.randint(0, 4)
            k = rng.randint(1, 30)
            if n_rel == 0:
                continue
            hits = sum(1 for v in g[:k] if v >= 1)
            assert near(mod.precision_at_k(g, k), hits / k), f"seed {s}: P@{k} of {g}"
            assert near(mod.recall_at_k(g, k, n_rel), hits / n_rel), f"seed {s}: R@{k} of {g} with {n_rel} relevant"
            precs = [sum(1 for u in g[:i] if u >= 1) / i for i in range(1, len(g) + 1) if g[i - 1] >= 1]
            assert near(mod.average_precision(g, n_rel), sum(precs) / n_rel), f"seed {s}: AP of {g} with {n_rel} relevant"
            first = next((i for i, v in enumerate(g, 1) if v >= 1), None)
            assert near(mod.reciprocal_rank(g), 1 / first if first else 0.0), f"seed {s}: RR of {g}"
            assert 0 <= mod.average_precision(g, n_rel) <= 1 + 1e-12, f"seed {s}: AP must lie in [0, 1]"
            rs = [mod.recall_at_k(g, j, n_rel) for j in range(1, 30)]
            assert all(x <= y + 1e-12 for x, y in zip(rs, rs[1:])), f"seed {s}: recall can only rise as k grows"
    return ""


# =============================================================================
# Milestone 3: graded metrics
# =============================================================================
def m3():
    assert near(mod.dcg(RANKED, 10), 3 + 2 / 2 + 1 / math.log2(7) + 2 / math.log2(9)), \
        f"chapter 4: DCG@10 of the running example is 4.987; got {mod.dcg(RANKED, 10)}"
    assert near(mod.dcg(sorted(EVERYTHING, reverse=True), 10), 6.866, 5e-4), "the ideal order has DCG@10 = 6.866"
    assert near(mod.dcg(RANKED, 3), 3 + 0 + 2 / 2), "DCG@3: only the first three ranks count"
    assert near(mod.dcg([2], 5), 2.0) and mod.dcg([], 5) == 0.0, "short or empty lists are fine"
    assert near(mod.dcg([3, 1], 2, exp_gain=True), 7 + 1 / math.log2(3)), "exp_gain uses 2**g - 1: [3, 1] gives 7 + 1/log2(3)"
    got = mod.ndcg_at_k(RANKED, 10, EVERYTHING)
    assert abs(got - 0.726) < 5e-4, f"chapter 4: nDCG@10 of the running example is 0.726; got {got:.4f}"
    got = mod.ndcg_at_k(RANKED, 3, EVERYTHING)
    assert abs(got - 0.760) < 5e-4, f"chapter 4: nDCG@3 is 0.760; got {got:.4f}"
    better = [3, 2, 0, 0, 0, 1, 0, 2, 0, 0]
    assert abs(mod.ndcg_at_k(better, 10, EVERYTHING) - 0.764) < 5e-4, "swap the grade-2 result up to rank 2: nDCG@10 becomes 0.764"
    x, y, pool = [3] + [0] * 9, [2, 2, 2] + [0] * 7, [3, 2, 2, 2]
    lin = (mod.ndcg_at_k(x, 10, pool), mod.ndcg_at_k(y, 10, pool))
    exp = (mod.ndcg_at_k(x, 10, pool, True), mod.ndcg_at_k(y, 10, pool, True))
    assert abs(lin[0] - 0.490) < 5e-4 and abs(lin[1] - 0.696) < 5e-4, f"linear gain: X 0.490, Y 0.696 (chapter 4); got {lin}"
    assert abs(exp[0] - 0.599) < 5e-4 and abs(exp[1] - 0.547) < 5e-4, f"exponential gain: X 0.599, Y 0.547 (chapter 4); got {exp}"
    assert mod.ndcg_at_k([0, 0], 5, [0, 0, 0]) == 0.0, "no relevant documents: nDCG is 0.0, not a ZeroDivisionError"
    assert near(mod.ndcg_at_k([2, 1], 5, [2, 1]), 1.0), "the ideal order scores exactly 1"
    assert mod.ndcg_at_k([1], 3, [1, 1, 1]) < mod.ndcg_at_k([1], 3, [1]), "ideal comes from ALL judged documents, not only the retrieved ones"

    for s in seeds(range(1, 9)):
        rng = random.Random(s)
        for _ in range(30):
            judged = [rng.choice([0, 0, 1, 2, 3]) for _ in range(rng.randint(1, 20))]
            order = judged[:]
            rng.shuffle(order)
            k = rng.randint(1, 15)
            n = mod.ndcg_at_k(order, k, judged)
            assert -1e-12 <= n <= 1 + 1e-12, f"seed {s}: nDCG must lie in [0, 1]; got {n} for {order} (all grades {judged})"
            ideal = sorted(judged, reverse=True)
            assert near(mod.ndcg_at_k(ideal, k, judged), 1.0 if any(judged) else 0.0), f"seed {s}: the ideal order must score 1 (or 0 if nothing is relevant)"
            if any(judged) and len(order) > 1:
                i = rng.randrange(len(order) - 1)
                if order[i] < order[i + 1]:
                    swapped = order[:]
                    swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
                    assert mod.dcg(swapped, k) >= mod.dcg(order, k) - 1e-12, f"seed {s}: moving a better document up cannot lower DCG"
    return ""


# =============================================================================
# Milestone 4: scoring whole runs
# =============================================================================
def m4():
    qrels = {"q1": {"a": 2, "b": 0, "c": 1}, "q2": {"x": 0, "y": 0}, "q3": {"m": 3}}
    run = {"q1": ["c", "z", "a"], "q9": ["a"]}
    seen = {}

    def spy(grades, all_grades):
        seen[len(seen)] = (list(grades), sorted(all_grades))
        return float(sum(grades))

    out = mod.evaluate_run(run, qrels, spy)
    assert out == {"q1": 3.0, "q3": 0.0}, (f"evaluate_run: q2 has no relevant document (leave it out), q3 is missing from the run "
                                          f"(score it on an empty ranking), q9 is not in qrels (ignore it); got {out}")
    assert seen[0] == ([1, 0, 2], [0, 1, 2]), f"for q1 the metric gets grades [1, 0, 2] (z is unjudged) and all judged grades [0, 1, 2]; got {seen[0]}"
    assert seen[1] == ([], [3]), f"q3 is scored on an empty ranking: grades [] and all_grades [3]; got {seen[1]}"
    assert mod.evaluate_run({}, {}, spy) == {}, "no queries, no scores"

    assert near(mod.mean([1, 2, 6]), 3.0) and near(mod.mean({"a": 1.0, "b": 2.0}), 1.5) and mod.mean([]) == 0.0 and mod.mean({}) == 0.0, \
        "mean works on a list or on a dict's values, and returns 0.0 when empty"

    q = mod.parse_qrels(read("qrels.txt"))
    metrics = mod.make_metrics(10)
    note = []
    for system in SYSTEMS:
        run = mod.parse_run(read(f"run_{system}.txt"))
        row = {}
        for name, fn in metrics.items():
            scores = mod.evaluate_run(run, q, fn)
            assert len(scores) == 58, f"{system} {name}: 60 queries, 2 without a relevant document, so 58 scores; got {len(scores)}"
            want = o_scores(system, name)
            for qid in want:
                assert near(scores[qid], want[qid]), f"{system} {name} on {qid}: oracle says {want[qid]:.6f}, you got {scores[qid]:.6f}"
            row[name] = mod.mean(scores)
        note.append(f"{system:<11}" + "  ".join(f"{k} {v:.3f}" for k, v in row.items()))
    return "\n".join(note)


# =============================================================================
# Milestone 5: a bootstrap confidence interval
# =============================================================================
def m5():
    lo, hi = mod.bootstrap_ci([0.5] * 12)
    assert near(lo, 0.5) and near(hi, 0.5), f"identical values have a zero-width interval; got ({lo}, {hi})"
    lo, hi = mod.bootstrap_ci([0.3])
    assert near(lo, 0.3) and near(hi, 0.3), "one value: the interval collapses to it"
    try:
        mod.bootstrap_ci([])
    except ValueError:
        pass
    else:
        raise AssertionError("bootstrap_ci([]) should raise ValueError")
    vals = [0, 0, 0, 1, 1, 1, 1, 0, 1, 1]
    lo, hi = mod.bootstrap_ci(vals, n_boot=4000, seed=5)
    assert 0.2 <= lo <= 0.6 <= hi <= 0.95 and lo < hi, f"ten 0/1 outcomes with mean 0.6: expected an interval around 0.6, about (0.3, 0.9); got ({lo:.3f}, {hi:.3f})"
    spread = [0.13 * i % 1.0 for i in range(1, 41)]
    assert mod.bootstrap_ci(spread, 500, 0.05, 11) == mod.bootstrap_ci(spread, 500, 0.05, 11), "same seed, same interval"
    assert mod.bootstrap_ci(spread, 500, 0.05, 11) != mod.bootstrap_ci(spread, 500, 0.05, 12), "a different seed should resample differently"

    note = ""
    for s in seeds(range(1, 4)):
        rng = random.Random(s)
        xs = [rng.gauss(0.5, 0.25) for _ in range(120)]
        m = sum(xs) / len(xs)
        sd = math.sqrt(sum((v - m) ** 2 for v in xs) / (len(xs) - 1))
        half = 1.96 * sd / math.sqrt(len(xs))
        lo, hi = mod.bootstrap_ci(xs, n_boot=2000, seed=s)
        assert lo < m < hi, f"seed {s}: the interval ({lo:.4f}, {hi:.4f}) must contain the sample mean {m:.4f}"
        assert 0.9 * half <= m - lo <= 1.1 * half and 0.9 * half <= hi - m <= 1.1 * half, (
            f"seed {s}: for 120 values each side of the interval should be about 1.96 x sd / sqrt(n) = {half:.4f} from the mean {m:.4f}; "
            f"got {m - lo:.4f} below and {hi - m:.4f} above. Check that each resample has n values and that you take the 2.5% and 97.5% quantiles of the MEANS")
        lo90, hi90 = mod.bootstrap_ci(xs, n_boot=2000, alpha=0.10, seed=s)
        assert (hi90 - lo90) < (hi - lo), f"seed {s}: a 90% interval (alpha 0.10) must be narrower than a 95% one"
        lo4, hi4 = mod.bootstrap_ci(xs[:30], n_boot=2000, seed=s)
        assert (hi4 - lo4) > 1.5 * (hi - lo), f"seed {s}: 30 values must give a clearly wider interval than 120"
        note = f"n=120, sd={sd:.3f}: bootstrap half-width {(hi - lo) / 2:.4f} against the normal approximation {half:.4f}"

    # Coverage: how often does the interval contain the true mean (0.0) of fresh samples?
    for s in seeds([7]):
        rng = random.Random(s)
        trials, covered = 200, 0
        for t in range(trials):
            xs = [rng.gauss(0.0, 1.0) for _ in range(30)]
            lo, hi = mod.bootstrap_ci(xs, n_boot=400, seed=t)
            covered += lo <= 0.0 <= hi
        assert 0.88 <= covered / trials <= 0.99, (f"seed {s}: a 95% interval should contain the true mean about 95% of the time; "
                                                  f"yours did in {covered} of {trials} fresh samples ({covered / trials:.0%})")
        note += f"\ncoverage of the true mean over {trials} fresh samples of 30: {covered / trials:.1%}"
    return note


# =============================================================================
# Milestone 6: a paired comparison
# =============================================================================
def exact_sign_flip(diffs):
    n = len(diffs)
    obs = abs(sum(diffs)) - 1e-12
    hits = 0
    for mask in range(2 ** n):
        tot = sum(d if (mask >> i) & 1 else -d for i, d in enumerate(diffs))
        hits += abs(tot) >= obs
    return hits / 2 ** n


def m6():
    qids, diffs = mod.paired_diffs({"q1": 0.5, "q2": 0.2, "q4": 0.9}, {"q2": 0.6, "q1": 0.4, "q3": 0.1})
    assert qids == ["q1", "q2"] and len(diffs) == 2 and near(diffs[0], -0.1) and near(diffs[1], 0.4), \
        f"paired_diffs: common queries only, sorted, difference is b - a; got {qids}, {diffs}"

    cases = [([1, 1, 1], 0.25), ([1, -1], 1.0), ([2, 1, 1, 1], 0.125), ([0.0, 0.0], 1.0), ([3, 1, 1, -1], 0.5)]
    for d, want in cases:
        got = mod.sign_flip_p(d)
        assert near(got, want), f"sign_flip_p({d}) should be {want} (exact enumeration of {2 ** len(d)} sign patterns); got {got}"
    assert mod.sign_flip_p([]) == 1.0, "no differences: p = 1.0"
    rng = random.Random(3)
    d12 = [rng.gauss(0.3, 0.5) for _ in range(12)]
    assert near(mod.sign_flip_p(d12), exact_sign_flip(d12)), "twelve differences or fewer must be enumerated exactly"

    for s in seeds([1, 2, 3]):
        rng = random.Random(s)
        d14 = [rng.gauss(0.25, 0.6) for _ in range(14)]
        want = exact_sign_flip(d14)
        got = mod.sign_flip_p(d14, n_perm=20000, seed=s)
        assert abs(got - want) < 0.025, f"seed {s}: with 14 differences the Monte Carlo p ({got:.4f}) should be near the exact {want:.4f}"
        assert mod.sign_flip_p(d14, 3000, s) == mod.sign_flip_p(d14, 3000, s), f"seed {s}: same seed, same p"
        sym = [v for x in d14[:7] for v in (x, -x)]
        assert mod.sign_flip_p(sym, 2000, s) > 0.99, f"seed {s}: differences that sum to exactly 0 cannot be unusual: p must be 1"

    a = {f"q{i}": 0.5 for i in range(20)}
    b = {q: v + 0.1 for q, v in a.items()}
    r = mod.paired_compare(a, b)
    assert r["n"] == 20 and near(r["mean_a"], 0.5) and near(r["mean_b"], 0.6) and near(r["diff"], 0.1), f"paired_compare summary numbers: got {r}"
    assert near(r["ci"][0], 0.1) and near(r["ci"][1], 0.1) and r["verdict"] == "B better" and 0 < r["p"] < 0.001, f"a constant +0.1 on every query: B better, p tiny but never exactly 0 (Monte Carlo: (count + 1) / (n_perm + 1)); got {r}"
    assert mod.paired_compare(b, a)["verdict"] == "A better", "swap the systems: A better"
    same = mod.paired_compare(a, dict(a))
    assert same["verdict"] == "no clear difference" and near(same["p"], 1.0), f"identical systems: no clear difference, p = 1; got {same}"
    part = mod.paired_compare({"q1": 0.1, "q2": 0.2, "q3": 0.3}, {"q2": 0.4, "q3": 0.5, "q4": 0.9})
    assert part["n"] == 2 and near(part["diff"], 0.2), f"only queries scored for both systems are compared; got n={part['n']}"
    try:
        mod.paired_compare({"q1": 1.0}, {"q2": 1.0})
    except ValueError:
        pass
    else:
        raise AssertionError("no shared queries should raise ValueError")

    q = mod.parse_qrels(read("qrels.txt"))
    ndcg = mod.make_metrics(10)["nDCG@10"]
    sc = {s: mod.evaluate_run(mod.parse_run(read(f"run_{s}.txt")), q, ndcg) for s in SYSTEMS}
    full = mod.paired_compare(sc["bm25"], sc["hybrid"])
    ref = {s: o_scores(s, "nDCG@10") for s in SYSTEMS}
    want_diff = sum(ref["hybrid"][k] - ref["bm25"][k] for k in ref["bm25"]) / 58
    want_lo, want_hi = o_boot([ref["hybrid"][k] - ref["bm25"][k] for k in sorted(ref["bm25"])])
    assert near(full["diff"], want_diff), f"bm25 vs hybrid: mean difference should be {want_diff:.4f}; got {full['diff']:.4f}"
    assert abs(full["ci"][0] - want_lo) < 0.015 and abs(full["ci"][1] - want_hi) < 0.015, \
        f"bm25 vs hybrid: the 95% interval should be about ({want_lo:.3f}, {want_hi:.3f}); got ({full['ci'][0]:.3f}, {full['ci'][1]:.3f})"
    assert full["verdict"] == "B better" and full["p"] < 0.01, f"hybrid beats bm25 on nDCG@10 across 58 queries; got {full['verdict']} with p = {full['p']}"
    tuned = mod.paired_compare(sc["bm25"], sc["bm25-tuned"])
    assert tuned["verdict"] == "no clear difference" and tuned["ci"][0] < 0 < tuned["ci"][1], \
        f"bm25-tuned is almost the same system: expect no clear difference; got {tuned['verdict']}, CI {tuned['ci']}"
    first = sorted(sc["bm25"])[:15]
    small = mod.paired_compare({k: sc["bm25"][k] for k in first}, {k: sc["hybrid"][k] for k in first})
    assert small["verdict"] == "no clear difference", f"on only the first 15 queries the same gain is not yet distinguishable from noise; got {small['verdict']}, CI {small['ci']}"
    assert (small["ci"][1] - small["ci"][0]) > 1.5 * (full["ci"][1] - full["ci"][0]), "15 queries must give a much wider interval than 58"
    f = lambda r: f"diff {r['diff']:+.3f}  95% CI ({r['ci'][0]:+.3f}, {r['ci'][1]:+.3f})  p {r['p']:.4f}  -> {r['verdict']}"
    return (f"nDCG@10 bm25 -> hybrid, 58 queries: {f(full)}\n"
            f"nDCG@10 bm25 -> bm25-tuned, 58 queries: {f(tuned)}\n"
            f"nDCG@10 bm25 -> hybrid, first 15 queries: {f(small)}")


MILESTONES = [
    (1, "Milestone 1: judgements and runs from files", m1),
    (2, "Milestone 2: precision, recall, reciprocal rank, average precision", m2),
    (3, "Milestone 3: DCG and nDCG", m3),
    (4, "Milestone 4: scoring a whole run, macro means", m4),
    (5, "Milestone 5: a bootstrap confidence interval", m5),
    (6, "Milestone 6: a paired comparison of two systems", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 2 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
