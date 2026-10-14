"""Self-check for Lab 1: From Brief to Evaluation Kit.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 5       # only milestone 5
    python3 check.py solution 5 17    # milestone 5, replaying ONLY the random cases of seed 17

The data are fixed files (pool.jsonl, predictions.json); the only randomness is in the
property checks, and every one is seeded and prints its seed on failure. There is no
network and no clock, and the whole check finishes in a couple of seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import itertools
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


def expect(cond, msg):
    assert cond, msg


# -----------------------------------------------------------------------------
# Independent oracles (deliberately plain, written differently from the lab)
# -----------------------------------------------------------------------------
def wilson_oracle(k, n, z=1.96):
    """Solve (p - x)^2 = z^2 x (1 - x) / n for x: the two roots are the interval."""
    p = k / n
    a = 1 + z * z / n
    b = -(2 * p + z * z / n)
    c = p * p
    disc = math.sqrt(b * b - 4 * a * c)
    return (-b - disc) / (2 * a), (-b + disc) / (2 * a)


def kappa_oracle(a, b):
    n = len(a)
    cats = sorted(set(a) | set(b))
    table = {(x, y): 0 for x in cats for y in cats}
    for x, y in zip(a, b):
        table[(x, y)] += 1
    po = sum(table[(c, c)] for c in cats) / n
    pe = sum(sum(table[(c, y)] for y in cats) * sum(table[(x, c)] for x in cats) for c in cats) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def doc(i, dtype="email", worry=False, text=None, a="covered", b="covered", adj=None):
    return {"id": i, "doc_type": dtype, "month": "2026-05", "worry": worry,
            "text": text if text is not None else f"claim number {i} about a thing that happened",
            "label_a": a, "label_b": b, "label_adj": adj}


LABELS = ["covered", "not_covered", "refer"]
POOL = None


def pool():
    global POOL
    if POOL is None:
        POOL = mod.load_pool()
    return POOL


# =============================================================================
# Milestone 1: wilson, cases_needed
# =============================================================================
def m1():
    lo, hi = mod.wilson(14, 16)
    expect(abs(lo - 0.640) < 0.002 and abs(hi - 0.965) < 0.002,
           f"wilson(14, 16) should be about (0.640, 0.965), the chapter's 'interval 64% to 97%'; got ({lo:.3f}, {hi:.3f})")
    lo, hi = mod.wilson(180, 200)
    expect(abs(lo - 0.851) < 0.002 and abs(hi - 0.934) < 0.002,
           f"wilson(180, 200) should be about (0.851, 0.934); got ({lo:.3f}, {hi:.3f})")
    lo, hi = mod.wilson(0, 10)
    expect(near(lo, 0.0, 1e-12) and abs(hi - 0.2775) < 0.001,
           f"wilson(0, 10) should start at 0 and end near 0.278 (zero errors is not zero risk); got ({lo:.4f}, {hi:.4f})")
    lo, hi = mod.wilson(10, 10)
    expect(abs(hi - 1.0) < 1e-12 and abs(lo - 0.7225) < 0.001, f"wilson(10, 10) should be about (0.722, 1.0); got ({lo:.4f}, {hi:.4f})")
    expect(tuple(mod.wilson(0, 0)) == (0.0, 1.0), "with no cases the interval is the whole range (0.0, 1.0): you know nothing")
    for s in seeds(range(1, 41)):
        rng = random.Random(s)
        n = rng.randint(1, 600)
        k = rng.randint(0, n)
        lo, hi = mod.wilson(k, n)
        olo, ohi = wilson_oracle(k, n)
        expect(abs(lo - olo) < 1e-9 and abs(hi - ohi) < 1e-9,
               f"seed {s}: wilson({k}, {n}) = ({lo:.6f}, {hi:.6f}) but an independent solve of the same quadratic gives ({olo:.6f}, {ohi:.6f}). "
               "Hint: centre = (p + z^2/2n) / (1 + z^2/n); half-width = z sqrt(p(1-p)/n + z^2/4n^2) / (1 + z^2/n)")
        expect(-1e-12 <= lo <= k / n + 1e-12 <= hi + 2e-12 and hi <= 1 + 1e-12, f"seed {s}: ({lo}, {hi}) must contain k/n = {k / n} and stay inside [0, 1]")
        lo2, hi2 = mod.wilson(k * 4, n * 4)
        expect(hi2 - lo2 < hi - lo or n * 4 > 10000, f"seed {s}: four times the cases at the same rate should narrow the interval")
        mlo, mhi = mod.wilson(n - k, n)
        expect(near(mlo, 1 - hi, 1e-9) and near(mhi, 1 - lo, 1e-9), f"seed {s}: the interval should be symmetric: wilson(n-k, n) = 1 - wilson(k, n) reversed")
    # sample size: the chapter's table (planning at p = 0.9)
    for hw, want in ((0.10, 35), (0.05, 139), (0.03, 385), (0.02, 865)):
        got = mod.cases_needed(hw)
        expect(got == want, f"cases_needed({hw}) should be {want} (z^2 p (1-p) / h^2 rounded UP at p = 0.9); got {got}")
    expect(mod.cases_needed(0.05, p=0.5) == 385, "cases_needed(0.05, p=0.5) should be 385 (the worst case, p = 0.5)")
    expect(mod.cases_needed(0.08) == 55, f"cases_needed(0.08) should be 55 (54.02 rounded UP); got {mod.cases_needed(0.08)}")
    expect(isinstance(mod.cases_needed(0.08), int), "cases_needed should return an int (use math.ceil)")
    return f"a slice of 14/16 correct: 64% to 97%; planning +/- 3%: {mod.cases_needed(0.03)} cases"


# =============================================================================
# Milestone 2: jaccard, dedupe, stratified_sample
# =============================================================================
def m2():
    expect(near(mod.jaccard({1, 2, 3}, {2, 3, 4}), 0.5), "jaccard({1,2,3}, {2,3,4}) should be 2/4 = 0.5")
    expect(mod.jaccard({1}, {2}) == 0.0, "disjoint sets have Jaccard 0.0")
    expect(mod.jaccard({1, 2}, {1, 2}) == 1.0, "equal sets have Jaccard 1.0")
    expect(mod.jaccard(set(), set()) == 1.0, "two empty sets count as identical: 1.0 (and must not divide by zero)")
    expect(mod.jaccard(set(), {1}) == 0.0, "an empty set against a non-empty one is 0.0")
    for s in seeds(range(1, 21)):
        rng = random.Random(s)
        a = {rng.randint(0, 12) for _ in range(rng.randint(0, 8))}
        b = {rng.randint(0, 12) for _ in range(rng.randint(0, 8))}
        expect(near(mod.jaccard(a, b), mod.jaccard(b, a)), f"seed {s}: jaccard must be symmetric")
    # hand-made documents: d2 is d1 plus one word (8 shared shingles of 9 -> 0.889)
    base = "the quick brown fox jumps over the lazy dog today"
    d1, d2 = doc("A1", text=base), doc("A2", text=base + " again")
    d3, d4 = doc("A3", text="a completely different note about a stolen bicycle in the hallway"), doc("A4", text=base + " twice")
    docs = [d4, d3, d2, d1]
    snapshot = [x["id"] for x in docs]
    kept = mod.dedupe(docs, 0.7)
    expect([x["id"] for x in docs] == snapshot, "dedupe must not modify (reorder) the list it is given")
    expect([x["id"] for x in kept] == ["A1", "A3"],
           f"with threshold 0.7, A2 and A4 are near-copies of A1 (each 8/9 = 0.889 similar); expected kept ids ['A1', 'A3'] (lowest id of each cluster, sorted), got {[x['id'] for x in kept]}")
    kept = mod.dedupe(docs, 8 / 9)
    expect([x["id"] for x in kept] == ["A1", "A3"], "a document AT the threshold is dropped: keep only if Jaccard < threshold (8/9 is not below 8/9)")
    kept = mod.dedupe(docs, 0.9)
    expect([x["id"] for x in kept] == ["A1", "A2", "A3", "A4"], f"with threshold 0.9 nothing is that similar (the closest pair is 0.889), so all four stay; got {[x['id'] for x in kept]}")
    # the real pool: 14 planted re-sends (ids D291..D304) must go, and nothing else
    full = pool()
    clean = mod.dedupe(full, 0.70)
    ids = [d["id"] for d in clean]
    want = [f"D{i:03d}" for i in range(1, 291)]
    extra = [i for i in ids if i not in want]
    lost = [i for i in want if i not in ids]
    expect(not extra, f"{len(extra)} near-duplicates are still in the cleaned pool (for example {extra[:3]}): compare shingle SETS, and drop when Jaccard >= threshold")
    expect(not lost, f"{len(lost)} genuinely different documents were dropped (for example {lost[:3]}): keep a document unless it is similar to one already KEPT")
    # stratified sample
    quotas = {"email/ordinary": 5, "email/worry": 3, "scanned_form/ordinary": 4, "scanned_form/worry": 99, "ghost/ordinary": 4}
    smp = mod.stratified_sample(clean, quotas, 7)
    got = {}
    for d in smp:
        got[mod.stratum_of(d)] = got.get(mod.stratum_of(d), 0) + 1
    size = {}
    for d in clean:
        size[mod.stratum_of(d)] = size.get(mod.stratum_of(d), 0) + 1
    expect(got.get("email/ordinary") == 5 and got.get("email/worry") == 3 and got.get("scanned_form/ordinary") == 4, f"each stratum should give exactly its quota; got {got}")
    expect(got.get("scanned_form/worry") == size["scanned_form/worry"], f"a quota bigger than the stratum should take the whole stratum ({size['scanned_form/worry']}); got {got.get('scanned_form/worry')}")
    expect(set(got) <= set(quotas) and "phone_note/ordinary" not in got, "documents in strata with no quota must be left out")
    expect([d["id"] for d in smp] == sorted(d["id"] for d in smp) and len({d["id"] for d in smp}) == len(smp), "the sample must be sorted by id with no repeats")
    shuffled = clean[:]
    random.Random(3).shuffle(shuffled)
    expect([d["id"] for d in mod.stratified_sample(shuffled, quotas, 7)] == [d["id"] for d in smp],
           "the sample must not depend on the order the pool arrives in: sort each stratum's members by id before drawing")
    expect([d["id"] for d in mod.stratified_sample(clean, quotas, 8)] != [d["id"] for d in smp], "a different seed should give a different sample")
    # the documented contract, exactly: sorted strata, one shared generator, sample of the id-sorted members
    rng = random.Random(7)
    want_ids = []
    for name in sorted(quotas):
        members = sorted((d for d in clean if mod.stratum_of(d) == name), key=lambda d: d["id"])
        want_ids += [d["id"] for d in rng.sample(members, min(quotas[name], len(members)))]
    expect([d["id"] for d in smp] == sorted(want_ids),
           "the sample differs from the documented draw (strata in sorted name order, ONE random.Random(seed) shared across strata, "
           "rng.sample(id-sorted members, quota)); the contract is what lets two people rebuild the same gold set")
    return f"pool of {len(full)} -> {len(clean)} after dedupe; sample of {len(smp)} from a 5/3/4/all quota"


# =============================================================================
# Milestone 3: split_dev_test, cohens_kappa, adjudicate
# =============================================================================
def m3():
    # use a plain stand-in for milestone 2 so this milestone stands on its own: the 290 originals, every other one
    gold = [d for d in pool() if int(d["id"][1:]) <= 290][::2]
    dev, test = mod.split_dev_test(gold, 0.5, 11)
    ids_d, ids_t = {d["id"] for d in dev}, {d["id"] for d in test}
    expect(not ids_d & ids_t, f"dev and test must not share a document; {len(ids_d & ids_t)} appear in both")
    expect(ids_d | ids_t == {d["id"] for d in gold} and len(dev) + len(test) == len(gold), "every document must land in exactly one half")
    by = {}
    for d in gold:
        by.setdefault(mod.stratum_of(d), []).append(d["id"])
    for name, members in by.items():
        want = min(max(int(len(members) * 0.5 + 0.5), 1), len(members) - 1) if len(members) >= 2 else 0
        have = sum(i in ids_t for i in members)
        expect(have == want, f"stratum {name} has {len(members)} documents; its test half should hold {want}, yours holds {have}")
    expect([d["id"] for d in dev] == sorted(ids_d) and [d["id"] for d in test] == sorted(ids_t), "both halves must be sorted by id")
    sh = gold[:]
    random.Random(5).shuffle(sh)
    d2, t2 = mod.split_dev_test(sh, 0.5, 11)
    expect([d["id"] for d in t2] == [d["id"] for d in test], "the split must not depend on the input order (sort each stratum by id first)")
    expect([d["id"] for d in mod.split_dev_test(gold, 0.5, 12)[1]] != [d["id"] for d in test], "a different seed should give a different split")
    tiny = [doc("T1", "email"), doc("T2", "email"), doc("T3", "scanned_form")]
    d3, t3 = mod.split_dev_test(tiny, 0.1, 1)
    expect(len(t3) == 1 and t3[0]["id"] in ("T1", "T2") and {x["id"] for x in d3} == ({"T1", "T2"} - {t3[0]["id"]}) | {"T3"},
           "a stratum of 2 must give 1 to test even at fraction 0.1, and a stratum of 1 stays in dev (so dev is never empty)")
    rng = random.Random(11)
    want_test = []
    for name in sorted(by):
        members = sorted(by[name])
        rng.shuffle(members)
        n_t = min(max(int(len(members) * 0.5 + 0.5), 1), len(members) - 1) if len(members) >= 2 else 0
        want_test += members[:n_t]
    expect(sorted(want_test) == [d["id"] for d in test], "the split differs from the documented shuffle (sorted strata, id-sorted members, ONE random.Random(seed), first n_test to test)")
    # kappa, by hand: po = 3/4, pe = .5*.25 + .5*.75 = .5, so kappa = .5
    a, b = ["x", "x", "y", "y"], ["x", "y", "y", "y"]
    expect(near(mod.cohens_kappa(a, b), 0.5), f"cohens_kappa({a}, {b}) should be (0.75 - 0.5) / (1 - 0.5) = 0.5; got {mod.cohens_kappa(a, b):.4f}")
    expect(near(mod.cohens_kappa(["a", "b", "c", "a"], ["a", "b", "c", "a"]), 1.0), "identical labels give kappa 1.0")
    expect(near(mod.cohens_kappa(["a", "a", "a"], ["a", "a", "a"]), 1.0), "both labellers always saying the same single label: pe = 1, return 1.0 (no division by zero)")
    expect(near(mod.cohens_kappa(["x", "x", "y", "y"], ["x", "y", "x", "y"]), 0.0), "agreement no better than chance gives kappa 0")
    for bad in (([], []), (["a"], ["a", "b"])):
        try:
            mod.cohens_kappa(*bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"cohens_kappa{bad} should raise ValueError")
    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        n = rng.randint(5, 80)
        a = [rng.choice(LABELS) for _ in range(n)]
        b = [x if rng.random() < 0.7 else rng.choice(LABELS) for x in a]
        k = mod.cohens_kappa(a, b)
        expect(abs(k - kappa_oracle(a, b)) < 1e-9, f"seed {s}: kappa {k:.6f} but the contingency-table oracle gives {kappa_oracle(a, b):.6f}")
        expect(near(k, mod.cohens_kappa(b, a)), f"seed {s}: kappa must be symmetric")
    # adjudication
    rows = [doc("R1", a="covered", b="covered"), doc("R2", a="covered", b="refer", adj="not_covered"),
            doc("R3", a="refer", b="refer", adj="covered"), doc("R4", a="not_covered", b="covered", adj="covered")]
    final, log = mod.adjudicate(rows)
    expect(final == {"R1": "covered", "R2": "not_covered", "R3": "refer", "R4": "covered"},
           f"agreement keeps the agreed label (even if an adjudicator label is present), a disagreement takes label_adj; got {final}")
    expect(log == [{"id": "R2", "a": "covered", "b": "refer", "final": "not_covered"}, {"id": "R4", "a": "not_covered", "b": "covered", "final": "covered"}],
           f"the log should hold one {{id, a, b, final}} per disagreement, in input order; got {log}")
    try:
        mod.adjudicate([doc("R9", a="covered", b="refer", adj=None)])
    except ValueError as e:
        expect("R9" in str(e), f"the ValueError should name the document: 'R9 needs adjudication'; got '{e}'")
    else:
        raise AssertionError("a disagreement with no adjudicator label should raise ValueError('<id> needs adjudication')")
    fin, lg = mod.adjudicate(gold)
    kappa = mod.cohens_kappa([d["label_a"] for d in gold], [d["label_b"] for d in gold])
    expect(len(fin) == len(gold) and len(lg) == sum(d["label_a"] != d["label_b"] for d in gold), "one final label per document and one log entry per disagreement")
    return f"gold set {len(gold)} -> dev {len(dev)} / test {len(test)};  kappa between the two labellers {kappa:.2f};  {len(lg)} disagreements adjudicated"


# =============================================================================
# Milestone 4: confusion, score, slice_report
# =============================================================================
CHAPTER_MATRIX = {"covered": [106, 2, 2], "not_covered": [4, 55, 1], "refer": [1, 1, 28]}   # the model's matrix from the evaluation-plans chapter


def expand(matrix):
    g, p = [], []
    for gold_label, row in matrix.items():
        for pred_label, c in zip(LABELS, row):
            g += [gold_label] * c
            p += [pred_label] * c
    return g, p


def m4():
    g = ["covered", "not_covered", "refer", "refer", "covered"]
    p = ["covered", "covered", "refer", "covered", "refer"]
    cm = mod.confusion(g, p)
    expect(set(cm) == set(LABELS) and all(set(cm[x]) == set(LABELS) for x in LABELS), "confusion must have all 3x3 cells present, even the empty ones")
    expect(cm["covered"]["covered"] == 1 and cm["covered"]["refer"] == 1 and cm["not_covered"]["covered"] == 1 and cm["refer"]["covered"] == 1 and cm["refer"]["refer"] == 1,
           f"confusion[gold][pred] counts are wrong: {cm}")
    expect(sum(sum(r.values()) for r in cm.values()) == 5 and cm["not_covered"]["not_covered"] == 0, "the cells must add up to the number of items; unseen pairs are 0")
    sc = mod.score(g, p)
    expect(sc["n"] == 5 and sc["correct"] == 2 and near(sc["accuracy"], 0.4), f"2 of 5 are right: expected accuracy 0.4; got {sc}")
    expect(sc["critical"] == 2 and near(sc["critical_rate"], 0.4),
           f"wrongly approved = gold not_covered or refer but system said covered: idx 1 and idx 3, so 2; got critical={sc['critical']}. "
           "Wrongly DENYING a covered claim is an error but not a critical one here")
    # cost: (0 + 1800 + 0 + 1800 + 40) / 5
    expect(near(sc["cost_per_case"], 728.0), f"cost_per_case should be (0 + 1800 + 0 + 1800 + 40) / 5 = 728.0 from COST[gold][pred]; got {sc['cost_per_case']}")
    # the chapter's table: accuracy 94.5%, wrongly approved 5 (2.5%), 52.10 EUR per claim
    gg, pp = expand(CHAPTER_MATRIX)
    sc = mod.score(gg, pp)
    expect(sc["n"] == 200 and sc["correct"] == 189 and near(sc["accuracy"], 0.945), f"the chapter's model matrix has 189/200 right; got {sc['correct']}/{sc['n']}")
    expect(sc["critical"] == 5 and near(sc["critical_rate"], 0.025), f"the chapter counts 5 wrongly approved (2.5%); got {sc['critical']}")
    expect(abs(sc["cost_per_case"] - 52.10) < 0.005, f"the chapter's expected cost per claim is 52.10 EUR; got {sc['cost_per_case']:.2f}")
    other = {k: {kk: 1 for kk in LABELS} for k in LABELS}
    expect(near(mod.score(["refer"], ["covered"], other)["cost_per_case"], 1.0), "score must use the `costs` argument, not always the module's COST")
    for bad in (([], []), (["covered"], [])):
        try:
            mod.score(*bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"score{bad} should raise ValueError")
    # slices
    docs = [doc(f"S{i}", "email" if i < 16 else "phone_note") for i in range(20)]
    goldm = {d["id"]: "covered" for d in docs}
    predm = {d["id"]: "covered" for d in docs}
    for i in (0, 1):                      # two email errors
        predm[f"S{i}"] = "refer"
    rep = mod.slice_report(docs, goldm, predm, "doc_type", 15)
    expect(set(rep) == {"email", "phone_note"}, f"one entry per slice value; got {sorted(rep)}")
    e = rep["email"]
    lo, hi = wilson_oracle(14, 16)
    expect(e["n"] == 16 and e["correct"] == 14 and near(e["accuracy"], 0.875), f"email: 14 of 16 right; got {e}")
    expect(abs(e["lo"] - lo) < 1e-9 and abs(e["hi"] - hi) < 1e-9, f"email interval should be the 95% Wilson interval {lo:.3f} to {hi:.3f}; got {e['lo']:.3f} to {e['hi']:.3f}")
    expect(e["reportable"] is True and rep["phone_note"]["reportable"] is False and rep["phone_note"]["n"] == 4, "reportable means n >= min_n: email (16 >= 15) yes, phone_note (4) no")
    # the real kit, with the model's predictions, against an oracle
    kit = mod.build_kit()
    P = mod.load_predictions()["model"]
    test = kit["test"]
    rep = mod.slice_report(test, kit["gold"], P, "doc_type", 15)
    lines = []
    for name in sorted(rep):
        ids = [d["id"] for d in test if d["doc_type"] == name]
        k = sum(P[i] == kit["gold"][i] for i in ids)
        lo, hi = wilson_oracle(k, len(ids))
        r = rep[name]
        expect(r["n"] == len(ids) and r["correct"] == k and abs(r["lo"] - lo) < 1e-9 and abs(r["hi"] - hi) < 1e-9,
               f"slice {name}: expected n={len(ids)}, correct={k}, interval {lo:.3f} to {hi:.3f}; got {r}")
        lines.append(f"{name:16s} n={r['n']:3d}  accuracy {r['accuracy']:5.1%}  95% interval {r['lo']:5.1%} to {r['hi']:5.1%}")
    return "model on the sealed test half, by document type:\n" + "\n".join(lines)


# =============================================================================
# Milestone 5: verdict, paired_compare, non_inferior
# =============================================================================
def pairs_from(both, a_only, b_only, neither):
    a = [True] * both + [True] * a_only + [False] * b_only + [False] * neither
    b = [True] * both + [False] * a_only + [True] * b_only + [False] * neither
    idx = list(range(len(a)))
    random.Random(99).shuffle(idx)
    return [a[i] for i in idx], [b[i] for i in idx]


def m5():
    V = mod.verdict
    expect(V(90, 100, 0.80) == "accept", f"90/100 against a bar of 80%: interval {wilson_oracle(90, 100)[0]:.3f} to {wilson_oracle(90, 100)[1]:.3f}, the low end is above 0.80, so 'accept'; got {V(90, 100, 0.80)!r}")
    expect(V(80, 100, 0.80) == "inconclusive", "80/100 against 80%: the point estimate sits ON the bar but the interval (0.71 to 0.87) straddles it, so 'inconclusive'")
    expect(V(60, 100, 0.80) == "reject", f"60/100 against 80%: even the high end (0.69) is under the bar, so 'reject'; got {V(60, 100, 0.80)!r}")
    expect(V(88, 100, 0.85) == "inconclusive", "88/100 passes a point-estimate rule of 85% but its interval starts at 0.80, so the interval rule must say 'inconclusive'")
    expect(V(1, 400, 0.06, "max") == "accept", f"1 critical error in 400 against a 6% limit: high end 1.4%, so 'accept'; got {V(1, 400, 0.06, 'max')!r}")
    expect(V(3, 100, 0.06, "max") == "inconclusive", "3 in 100 against a 6% limit: the high end (8.5%) is over the limit, so 'inconclusive' (more cases could settle it)")
    expect(V(30, 100, 0.06, "max") == "reject", "30 in 100 against 6%: even the low end (21.9%) is over the limit, so 'reject'")
    try:
        V(1, 10, 0.5, "sideways")
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown direction should raise ValueError")
    # more cases turn "inconclusive" into "accept" at the SAME observed rate
    seq = [V(round(0.9 * n), n, 0.80) for n in (20, 50, 100, 400)]
    expect(seq == ["inconclusive", "inconclusive", "accept", "accept"], f"at a constant 90% observed, n = 20, 50, 100, 400 should give inconclusive, inconclusive, accept, accept; got {seq}")
    # paired comparison: the chapter's 200 gold cases (174 both right, 15 model only, 8 process only, 3 neither)
    a, b = pairs_from(174, 15, 8, 3)
    c = mod.paired_compare(a, b)
    expect((c["n"], c["both"], c["a_only"], c["b_only"], c["neither"]) == (200, 174, 15, 8, 3), f"the four cells should be 174 / 15 / 8 / 3; got {c}")
    expect(near(c["diff"], 0.035), f"diff = (15 - 8) / 200 = 0.035; got {c['diff']}")
    expect(abs(c["lo"] - (-0.0117)) < 0.0005 and abs(c["hi"] - 0.0817) < 0.0005,
           f"paired interval: se = sqrt(23 - 49/200) / 200 = 0.0239, so -0.012 to +0.082; got {c['lo']:.4f} to {c['hi']:.4f}")
    expect(abs(c["p_sign"] - 0.210) < 0.001, f"the sign test on 15 vs 8 should give a two-sided p of about 0.210 (the chapter's value); got {c['p_sign']:.4f}")
    swapped = mod.paired_compare(b, a)
    expect(near(swapped["diff"], -c["diff"]) and near(swapped["lo"], -c["hi"]) and near(swapped["hi"], -c["lo"]) and near(swapped["p_sign"], c["p_sign"]),
           "swapping the two systems must negate the difference and its interval, and leave p unchanged")
    z = mod.paired_compare(*pairs_from(10, 0, 0, 2))
    expect(near(z["diff"], 0) and near(z["lo"], 0) and near(z["hi"], 0) and near(z["p_sign"], 1.0), "no disagreements: no difference, a zero-width interval, p = 1.0")
    w = mod.paired_compare(*pairs_from(60, 12, 0, 8))
    expect(w["p_sign"] < 0.001 and w["lo"] > 0, f"12 wins to 0 should be clearly significant; got p={w['p_sign']:.5f}, lo={w['lo']:.3f}")
    # non-inferiority
    expect(mod.non_inferior({"lo": -0.01, "hi": 0.08}, 0.03) == "accept", "interval -1% to +8% with a 3% margin: the low end is above -3%, so 'accept'")
    expect(mod.non_inferior({"lo": -0.066, "hi": 0.137}, 0.05) == "inconclusive", "interval -6.6% to +13.7% with a 5% margin straddles -5%: 'inconclusive'")
    expect(mod.non_inferior({"lo": -0.20, "hi": -0.08}, 0.05) == "reject", "interval -20% to -8% is entirely below -5%: clearly worse by more than the margin, 'reject'")
    return "chapter table: model right alone 15, process right alone 8 -> diff +3.5%, interval -1.2% to +8.2%, sign test p = 0.21 (a margin of 3% passes; 'better' is not shown)"


# =============================================================================
# Milestone 6: audit_kit, decide
# =============================================================================
def ref_gates(ids, gold, model, base, spec):
    """A plain re-derivation of the three gates, for the cross-check."""
    n = len(ids)
    ok_m = [model[i] == gold[i] for i in ids]
    ok_b = [base[i] == gold[i] for i in ids]
    k = sum(ok_m)
    crit = sum(gold[i] != "covered" and model[i] == "covered" for i in ids)
    lo, hi = wilson_oracle(k, n)
    acc = "accept" if lo >= spec["accuracy_bar"] else "reject" if hi < spec["accuracy_bar"] else "inconclusive"
    clo, chi = wilson_oracle(crit, n)
    cr = "accept" if chi <= spec["critical_limit"] else "reject" if clo > spec["critical_limit"] else "inconclusive"
    b = sum(x and not y for x, y in zip(ok_m, ok_b))
    c = sum(y and not x for x, y in zip(ok_m, ok_b))
    diff = (b - c) / n
    se = math.sqrt(b + c - (b - c) ** 2 / n) / n
    bl = "accept" if diff - 1.96 * se > -spec["margin"] else "reject" if diff + 1.96 * se < -spec["margin"] else "inconclusive"
    gates = {"accuracy": acc, "critical": cr, "baseline": bl}
    overall = "reject" if "reject" in gates.values() else "accept" if set(gates.values()) == {"accept"} else "inconclusive"
    return gates, overall


def m6():
    kit = mod.build_kit()
    spec = kit["spec"]
    expect(len(kit["test"]) > 0 and len(kit["dev"]) > 0, "build_kit gave an empty half: check milestones 2 and 3 first (python3 check.py 2, python3 check.py 3)")
    good = mod.audit_kit(kit)
    expect(good == [], f"the sound kit should have no problems; audit_kit reported {good}")

    def variant(**changes):
        k = dict(kit)
        k["spec"] = dict(spec)
        for key, v in changes.items():
            if key.startswith("spec_"):
                k["spec"][key[5:]] = v
            else:
                k[key] = v
        return k

    def drop(k, name):
        del k["spec"][name]
        return k

    twin = dict(kit["test"][0], id="X900", text=kit["test"][0]["text"] + " Sent again by post.")
    cases = [
        ("a re-sent copy of a test document sits in dev (leak)", variant(dev=kit["dev"] + [twin]), ["leak"]),
        ("a test document is also in dev (overlap; it is its own twin, so also a leak)", variant(dev=kit["dev"] + [kit["test"][0]]), ["leak", "overlap"]),
        ("kappa 0.41 between the labellers", variant(kappa=0.41), ["low_kappa"]),
        ("a plan promising +/- 2 points (needs 865 cases)", variant(spec_half_width=0.02), ["underpowered"]),
        ("a rule that accepts on the point estimate", variant(spec_rule="point"), ["point_rule"]),
        ("no baseline in the plan", drop(variant(), "baseline"), ["no_baseline"]),
        ("no critical-error limit in the plan", drop(variant(), "critical_limit"), ["no_critical"]),
    ]
    counts = {}
    for d in kit["test"]:
        counts[d[spec["slice_key"]]] = counts.get(d[spec["slice_key"]], 0) + 1
    smallest = min(counts.values())
    small = sorted(f"small_slice:{k}" for k, v in counts.items() if v < smallest + 1)
    cases.append((f"a slice floor of {smallest + 1} cases (the smallest test slice has {smallest})", variant(spec_min_slice_n=smallest + 1), small))
    cases.append(("three flaws at once", variant(kappa=0.3, spec_rule="point", dev=kit["dev"] + [twin]), ["leak", "low_kappa", "point_rule"]))
    for what, k, want in cases:
        got = mod.audit_kit(k)
        expect(got == want, f"{what}: expected {want}, got {got}")
    # decide: synthetic scenarios with known answers
    def scenario(n, wrong_idx, crit_idx, base_wrong_idx):
        ids = [f"Z{i}" for i in range(n)]
        gold = {i: "not_covered" for i in ids}
        model = dict(gold)
        for j in wrong_idx:
            model[ids[j]] = "refer"
        for j in crit_idx:
            model[ids[j]] = "covered"
        base = dict(gold)
        for j in base_wrong_idx:
            base[ids[j]] = "refer"
        return ids, gold, model, base

    spec2 = dict(spec, accuracy_bar=0.80, critical_limit=0.06, margin=0.05)
    ids, gold, model, base = scenario(400, range(0, 16), range(16, 20), range(0, 24))      # 380/400 right, 4 critical, baseline 376
    r = mod.decide(ids, gold, model, base, spec2)
    expect(r["gates"] == {"accuracy": "accept", "critical": "accept", "baseline": "accept"} and r["overall"] == "accept",
           f"380/400 right (low end 92.6% >= 80%), 4 wrongly approved (high end 2.6% <= 6%), and no worse than a baseline at 376/400: every gate should accept. Got {r['gates']} -> {r['overall']}")
    expect(r["model"]["correct"] == 380 and r["model"]["critical"] == 4 and r["baseline"]["correct"] == 376 and r["compare"]["a_only"] == 4,
           f"decide should return the score dicts and the paired comparison; got model={r['model']}, baseline={r['baseline']}")
    ids, gold, model, base = scenario(100, range(0, 40), range(0, 0), range(0, 5))        # 60/100 right
    r = mod.decide(ids, gold, model, base, spec2)
    expect(r["gates"]["accuracy"] == "reject" and r["overall"] == "reject", f"60/100 against a bar of 80% must reject, and one rejected gate rejects the whole: got {r['gates']} -> {r['overall']}")
    ids, gold, model, base = scenario(60, range(0, 3), range(3, 5), range(0, 3))          # 55/60: wide interval, 2 critical in 60
    r = mod.decide(ids, gold, model, base, spec2)
    expect(r["overall"] == "inconclusive" and "reject" not in r["gates"].values() and "inconclusive" in r["gates"].values(),
           f"a small test set with nothing clearly failing should be 'inconclusive' overall (not 'accept'); got {r['gates']} -> {r['overall']}")
    # the real thing, against an independent re-derivation
    P = mod.load_predictions()
    ids = [d["id"] for d in kit["test"]]
    notes = []
    for base_name in ("current_process", "keyword_rule"):
        r = mod.decide(ids, kit["gold"], P["model"], P[base_name], spec)
        gates, overall = ref_gates(ids, kit["gold"], P["model"], P[base_name], spec)
        expect(r["gates"] == gates and r["overall"] == overall,
               f"model vs {base_name} on the {len(ids)} sealed cases: expected gates {gates} -> {overall}; got {r['gates']} -> {r['overall']}")
        m, b, c = r["model"], r["baseline"], r["compare"]
        notes.append(f"vs {base_name}: model {m['correct']}/{m['n']} right ({m['accuracy']:.1%}), {m['critical']} wrongly approved, "
                     f"{m['cost_per_case']:.0f} EUR/case; baseline {b['accuracy']:.1%}, {b['critical']} wrongly approved, {b['cost_per_case']:.0f} EUR/case\n"
                     f"    paired gap {c['diff']:+.1%} ({c['lo']:+.1%} to {c['hi']:+.1%}), p = {c['p_sign']:.3f};  gates {r['gates']}  ->  {r['overall'].upper()}")
    return "audit: the sound kit passes and 9 planted flaw variants are caught\n  " + "\n  ".join(notes)


MILESTONES = [
    (1, "Milestone 1: how far to trust a number (Wilson interval, sample size)", m1),
    (2, "Milestone 2: clean the pool and sample by stratum", m2),
    (3, "Milestone 3: seal a test half, measure agreement, adjudicate", m3),
    (4, "Milestone 4: the metrics the customer agreed to", m4),
    (5, "Milestone 5: verdicts on intervals, paired comparison", m5),
    (6, "Milestone 6: audit the kit and decide", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
