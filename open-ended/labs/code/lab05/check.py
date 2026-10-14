"""Self-check for Lab 5: a mini Meta Agent Search with strict search / selection / test splits.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 6 3     # milestone 6, replaying ONLY the random cases of seed 3

Everything is seeded: the simulated model answers from a hash, the proposer draws from a seeded
random.Random, and there is no network and no clock, so every run gives identical numbers. The whole
check finishes in a few seconds (about three for the reference solution).
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import os
import random
import sys
import time
from collections import Counter

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


Design, Entry, Model = mod.Design, mod.Entry, mod.Model
D = lambda s, p, n, v: Design(s, p, n, v)


# =============================================================================
# Milestone 1: a design becomes an agent that can be scored
# =============================================================================
class Stub(Model):
    """A scripted model: `right(attempt)` says whether solve() is correct on that attempt, `ok(r)` what verify() says."""

    def __init__(self, right=lambda a: True, ok=lambda r: True):
        super().__init__()
        self.right, self.ok, self.log = right, ok, []

    def solve(self, kind, expr, attempt, prompt):
        self.calls += 1
        self.log.append(("solve", kind, attempt))
        truth = mod.evaluate_expr(expr)
        return truth if self.right(attempt) else truth + 1

    def verify(self, expr, value, attempt):
        self.calls += 1
        self.log.append(("verify", attempt))
        return self.ok(attempt)


def oracle_agent(design, expr, model):
    """A plain re-implementation of the agent in the docstring, for the cross-check."""
    answers = [mod.solve_once(model, design, expr, i) for i in range(design.samples)]
    counts = Counter(answers)
    top = max(counts.values())
    v = next(a for a in answers if counts[a] == top)
    for r in range(design.retries):
        if model.verify(expr, v, r):
            break
        v = mod.solve_once(model, design, expr, 100 + r)
    return v


def m1():
    # --- majority, by hand
    cases = [([3, 3, 5], 3), ([5, 3, 3, 5], 5), ([4, 7, 9], 4), ([9], 9), ([-2, 6, 6, -2, 6], 6), ([1, 2, 2, 1], 1), ([8, 8, 7, 7, 7, 8], 8)]
    for xs, want in cases:
        got = mod.majority(list(xs))
        assert got == want, (f"majority({xs}) should be {want} (the most common answer; a tie goes to the one that appears first in the list), got {got}")
    rng = random.Random(1)
    for _ in range(300):
        xs = [rng.randint(-3, 3) for _ in range(rng.choice([1, 3, 5, 7]))]
        c = Counter(xs)
        want = next(a for a in xs if c[a] == max(c.values()))
        assert mod.majority(list(xs)) == want, f"majority({xs}) should be {want}, got {mod.majority(list(xs))}"
    xs = [2, 2, 3]
    mod.majority(xs)
    assert xs == [2, 2, 3], "majority must not modify the list it is given"

    # --- the call sequence of an agent, with a scripted model
    q = "3 + 4 * 2"                                    # 14, two operations
    m = Stub()
    assert mod.build_agent(D("direct", "plain", 3, 0))(q, m) == 14
    assert m.log == [("solve", "direct", 0), ("solve", "direct", 1), ("solve", "direct", 2)], (
        f"direct, 3 samples, no retries: expected three direct calls with attempts 0, 1, 2 and nothing else, got {m.log}. "
        "Each sample needs its OWN attempt number; the same attempt gets the same reply and a vote of identical copies is worthless.")
    m = Stub(ok=lambda r: False)
    mod.build_agent(D("direct", "plain", 3, 2))(q, m)
    assert m.log == [("solve", "direct", 0), ("solve", "direct", 1), ("solve", "direct", 2),
                     ("verify", 0), ("solve", "direct", 100), ("verify", 1), ("solve", "direct", 101)], (
        f"with a verifier that always objects and 2 retries the calls should be 3 samples, then (verify 0, solve 100), (verify 1, solve 101); got {m.log}")
    m = Stub(ok=lambda r: True)
    mod.build_agent(D("direct", "plain", 3, 3))(q, m)
    assert m.calls == 4, f"when the first verification passes the loop stops: 3 samples + 1 verify = 4 calls, got {m.calls}"
    m = Stub()
    mod.build_agent(D("steps", "plain", 2, 0))(q, m)
    assert [e for e in m.log if e[0] == "solve"] == [("solve", "step", 0)] * 2 + [("solve", "step", 1)] * 2, (
        f"steps solver: one call per operation per sample (2 operations x 2 samples = 4), got {m.log}")
    # voting repairs a minority of slips; the retry loop repairs a wrong vote; a passing verifier keeps a wrong value
    m = Stub(right=lambda a: a != 0)
    assert mod.build_agent(D("direct", "plain", 3, 0))(q, m) == 14, "two right answers out of three win the vote"
    m = Stub(right=lambda a: a != 0)
    assert mod.build_agent(D("direct", "plain", 1, 0))(q, m) == 15, "one sample, attempt 0 wrong: the agent returns the wrong answer"
    m = Stub(right=lambda a: a >= 100, ok=lambda r: False)
    assert mod.build_agent(D("direct", "plain", 1, 1))(q, m) == 14, "attempt 0 is wrong, the verifier objects, attempt 100 is right: the retry's answer is returned"
    assert m.calls == 3, f"one sample + one verify + one retry solve = 3 calls, got {m.calls}"
    m = Stub(right=lambda a: a >= 100, ok=lambda r: True)
    assert mod.build_agent(D("direct", "plain", 1, 1))(q, m) == 15, "a verifier that passes the answer keeps it, even a wrong one"

    # --- evaluate against the plain re-implementation, on the real simulated model
    qs = mod.make_questions(50, 11)
    rng = random.Random(2)
    for d in rng.sample(mod.ALL_DESIGNS, 14):
        model = Model()
        ok = sum(oracle_agent(d, e, model) == a for e, a in qs)
        s = mod.evaluate(d, qs)
        assert abs(s.accuracy - ok / 50) < 1e-9, f"{d.name}: accuracy should be {ok / 50:.2f} (the plain re-implementation), got {s.accuracy:.2f}"
        assert abs(s.calls - model.calls / 50) < 1e-9, f"{d.name}: calls per question should be {model.calls / 50:.3f}, got {s.calls:.3f} (count verifications too)"
    s = mod.evaluate(D("direct", "plain", 1, 0), qs)
    assert s.calls == 1.0, f"one direct answer costs exactly one call per question, got {s.calls}"
    s = mod.evaluate(D("steps", "plain", 1, 0), mod.make_questions(50, 3))
    assert abs(s.calls - 3.0) < 1e-9, f"step-by-step costs one call per operation, and questions cycle through 1 to 5 operations: expected 3.0 per question, got {s.calls}"
    a, b = mod.evaluate(D("direct", "plain", 3, 1), qs), mod.evaluate(D("direct", "plain", 3, 1), qs)
    assert (a.accuracy, a.calls) == (b.accuracy, b.calls), "evaluate must start a fresh Model each time: the same design gave two different scores"
    shared = Model()
    mod.evaluate(D("direct", "plain", 1, 0), qs[:10], shared)
    assert shared.calls == 10, f"when a model is passed in, evaluate uses it (10 questions, 10 calls), but it recorded {shared.calls}"
    big = mod.make_questions(300, 5)
    gap = mod.evaluate(D("steps", "careful", 7, 0), big).accuracy - mod.evaluate(D("direct", "plain", 1, 0), big).accuracy
    assert gap > 0.15, f"seven careful step-by-step votes should beat one direct answer by well over 15 points on 300 questions; the gap was {gap:.2f}"
    return "the call sequence, voting and retries behave as specified; scores agree with a plain re-implementation on 14 designs"


# =============================================================================
# Milestone 2: a gate and an archive
# =============================================================================
def m2():
    good = {"solver": "steps", "prompt": "careful", "samples": 5, "retries": 2}
    d = mod.validate(dict(good))
    assert d == D("steps", "careful", 5, 2), f"validate of a good proposal should return Design('steps', 'careful', 5, 2), got {d!r}"
    bad = [
        ({**good, "solver": "step"}, "solver"), ({**good, "prompt": "carefull"}, "prompt"),
        ({**good, "samples": 4}, "samples"), ({**good, "samples": 0}, "samples"),
        ({**good, "retries": -1}, "retries"), ({**good, "retries": 4}, "retries"),
        ({**good, "samples": "3"}, "samples"), ({**good, "samples": True}, "samples"),
        ({**good, "retries": 1.0 + 1}, "retries"),
    ]
    for raw, knob in bad[:-1]:
        try:
            mod.validate(raw)
        except ValueError as e:
            assert knob in str(e), f"the message for a bad {knob} should name the knob (the meta agent reads it to repair), got: {e}"
        except Exception as e:
            raise AssertionError(f"validate({raw}) should raise ValueError, raised {type(e).__name__}: {e}")
        else:
            raise AssertionError(f"validate({raw}) should reject it ({knob} is not an allowed value)")
    # a bool is an int in Python: True == 1, and 1 is an allowed number of samples
    try:
        mod.validate({**good, "samples": True})
    except ValueError:
        pass
    else:
        raise AssertionError("samples=True must be rejected (True == 1 in Python, but a bool is not a number of samples)")
    for raw, what in [({k: v for k, v in good.items() if k != "retries"}, "a missing knob"), ({**good, "temperature": 0.7}, "an extra knob"), (None, "None"), (["steps"], "a list")]:
        try:
            mod.validate(raw)
        except ValueError:
            pass
        except Exception as e:
            raise AssertionError(f"validate({raw}) ({what}) should raise ValueError, raised {type(e).__name__}: {e}")
        else:
            raise AssertionError(f"validate must reject {what}")
    # every design in the space round-trips
    for dd in mod.ALL_DESIGNS:
        assert mod.validate(dd.as_dict()) == dd

    # --- the archive
    a = mod.Archive()
    assert len(a) == 0 and a.top(3) == []
    rows = [("direct", "plain", 1, 0, 0.50, 1.0), ("direct", "plain", 3, 0, 0.70, 3.0), ("steps", "plain", 1, 0, 0.80, 3.0),
            ("steps", "plain", 3, 0, 0.80, 9.0), ("steps", "careful", 3, 0, 0.80, 9.0), ("steps", "careful", 1, 0, 0.80, 3.0),
            ("direct", "terse", 1, 0, 0.30, 1.0)]
    for i, (s, p, n, v, sc, c) in enumerate(rows):
        a.add(Entry(D(s, p, n, v), sc, c, None, i))
    assert len(a) == 7, f"len(archive) should be 7 after seven adds, got {len(a)}"
    names = [e.design.name for e in a.top(4)]
    want = ["steps-careful-x1-v0", "steps-plain-x1-v0", "steps-careful-x3-v0", "steps-plain-x3-v0"]
    assert names == want, (f"top(4) sorts by score (highest first), then by fewer calls, then by name. Expected {want}, got {names}. "
                           "A tie on score and calls goes to the alphabetically earlier name; sort with a key tuple (-score, calls, name).")
    assert len(a.top(50)) == 7, "top(k) with k larger than the archive returns every entry"
    assert [e.design.name for e in a.entries][:2] == ["direct-plain-x1-v0", "direct-plain-x3-v0"], "top() must not reorder or modify self.entries (use sorted(), not .sort())"
    assert D("steps", "plain", 3, 0) in a and D("steps", "plain", 5, 3) not in a, "`design in archive` should be true exactly for stored designs"
    try:
        a.add(Entry(D("direct", "plain", 1, 0), 0.9, 1.0, None, 9))
    except ValueError:
        pass
    else:
        raise AssertionError("adding a design that is already stored must raise ValueError")
    assert len(a) == 7, "a rejected add must leave the archive unchanged"
    # the archive keeps the worse child
    child = Entry(D("direct", "plain", 5, 0), 0.10, 5.0, "direct-plain-x3-v0", 8)
    a.add(child)
    assert child in a.entries and len(a) == 8, "worse designs are stored too: the archive is a memory, not a leaderboard"
    return "validation rejects every bad proposal with a message naming the knob; the archive orders by score, calls, name and refuses duplicates"


# =============================================================================
# Milestone 3: the stand-in meta agent
# =============================================================================
class FakeArchive:
    """Just enough of an archive for propose(): entries, top(k) and `design in archive`. (Your Archive is not needed here.)"""

    def __init__(self):
        self.entries, self.names = [], set()

    def add(self, e):
        self.entries.append(e)
        self.names.add(e.design.name)

    def __contains__(self, d):
        return d.name in self.names

    def __len__(self):
        return len(self.entries)

    def top(self, k):
        return sorted(self.entries, key=lambda e: (-e.score, e.calls, e.design.name))[:k]


def seeded_archive():
    a = FakeArchive()
    for i, d in enumerate(mod.SEEDS):
        a.add(Entry(d, 0.5 + 0.1 * i, 1.0 + 2 * i, None, 0))
    return a


def m3():
    a = seeded_archive()
    a.add(Entry(D("steps", "plain", 1, 0), 0.80, 3.0, "direct-plain-x1-v0", 1))
    top3 = {e.design.name for e in a.top(3)}
    assert len(top3) == 3
    for s in seeds(range(1, 4)):
        rng = random.Random(s)
        diffs, parents, kids = Counter(), Counter(), set()
        for _ in range(400):
            raw, parent = mod.propose(a, rng)
            assert isinstance(raw, dict) and set(raw) == set(mod.KNOBS), f"the first result of propose must be a dict with exactly the knobs {mod.KNOBS}, got {raw!r}"
            child = mod.validate(raw)
            assert child not in a, f"propose returned {child.name}, which is already in the archive; keep drawing until the child is new"
            assert parent in top3, f"seed {s}: the parent {parent!r} is not among the top 3 {sorted(top3)}; draw parents from archive.top(3) while that works"
            pd = next(e.design for e in a.entries if e.design.name == parent)
            changed = [k for k in mod.KNOBS if getattr(child, k) != getattr(pd, k)]
            assert len(changed) == 1, f"seed {s}: a child must differ from its parent in exactly one knob; {child.name} vs {pd.name} differ in {changed}"
            diffs[changed[0]] += 1
            parents[parent] += 1
            kids.add(child)
        assert all(diffs[k] > 15 for k in mod.KNOBS), f"seed {s}: every knob should be changed regularly; got {dict(diffs)}. Choose the knob with rng.choice(KNOBS)."
        assert all(parents[p] > 60 for p in top3), f"seed {s}: all three top entries should be parents regularly; got {dict(parents)}. Choose the parent uniformly from the top 3."
        assert len(kids) > 6, "proposals should vary"
    r1 = [mod.propose(a, random.Random(5)) for _ in range(3)]
    r2 = [mod.propose(a, random.Random(5)) for _ in range(3)]
    assert r1 == r2, "the same rng seed must give the same proposal (use only the rng you are given)"
    snapshot = [(e.design.name, e.score) for e in a.entries]
    mod.propose(a, random.Random(0))
    assert snapshot == [(e.design.name, e.score) for e in a.entries], "propose must not change the archive"

    # the neighbourhood of the best designs can be used up: then look further afield
    far = D("steps", "terse", 7, 3)
    full = FakeArchive()
    for i, d in enumerate(mod.ALL_DESIGNS):
        if d != far:
            diff = sum(getattr(d, k) != getattr(far, k) for k in mod.KNOBS)
            full.add(Entry(d, 0.5 + 0.01 * diff, 1.0, None, 0))   # the best entries differ from `far` in all 4 knobs
    assert not any(sum(getattr(e.design, k) != getattr(far, k) for k in mod.KNOBS) <= 1 for e in full.top(3))
    raw, parent = mod.propose(full, random.Random(0))
    assert mod.validate(raw) == far, (f"every design except {far.name} is archived, but the top 3 are all far from it; after the neighbourhood of the top 3 "
                                      f"is exhausted (100 draws) propose must draw parents from the whole archive. Got {raw}")
    full.add(Entry(far, 0.5, 1.0, None, 0))
    try:
        mod.propose(full, random.Random(0))
    except RuntimeError:
        pass
    else:
        raise AssertionError("with all 96 designs archived there is nothing new to propose: raise RuntimeError")
    return "children differ from a top-3 parent in one knob, are never already archived, and the search can move further afield when the neighbourhood is used up"


# =============================================================================
# Milestone 4: the search loop
# =============================================================================
def scripted(items):
    """A proposer that ignores the archive and replays a list of (raw, parent)."""
    calls = []
    it = iter(items)

    def proposer(archive, rng):
        calls.append(len(archive))
        return next(it)
    proposer.calls = calls
    return proposer


def m4():
    qs = mod.make_questions(40, 21)
    seed_names = [d.name for d in mod.SEEDS]
    g1 = D("steps", "plain", 1, 0).as_dict()
    g2 = D("steps", "plain", 3, 1).as_dict()
    g3 = D("direct", "careful", 5, 0).as_dict()
    typo = {**g1, "solver": "step"}
    dup = mod.SEEDS[1].as_dict()
    prop = scripted([(typo, "p"), (dup, "q"), (g1, "direct-plain-x1-v0"), (g2, "steps-plain-x1-v0"), (typo, "p"), (typo, "p"), (g3, "direct-plain-x3-v0")])
    res = mod.meta_search(prop, qs, 3, seed=1)
    arch = res.archive
    assert [e.design.name for e in arch.entries][:2] == seed_names and all(e.iteration == 0 and e.parent is None for e in arch.entries[:2]), (
        "the archive must start with the seed designs, scored, with iteration 0 and parent None")
    for e in arch.entries[:2]:
        assert abs(e.score - mod.evaluate(e.design, qs).accuracy) < 1e-9 and abs(e.calls - mod.evaluate(e.design, qs).calls) < 1e-9, f"seed {e.design.name} must be scored on the search questions"
    got = [(e.design.name, e.parent, e.iteration) for e in arch.entries[2:]]
    want = [("steps-plain-x1-v0", "direct-plain-x1-v0", 1), ("steps-plain-x3-v1", "steps-plain-x1-v0", 2), ("direct-careful-x5-v0", "direct-plain-x3-v0", 3)]
    assert got == want, f"with a proposer that says typo, duplicate, good | good | typo, typo, good the archive should gain {want}; got {got}"
    assert (res.repairs, res.duplicates, res.skipped) == (3, 1, 0), f"expected 3 repairs (the typos), 1 duplicate and 0 skipped iterations, got {(res.repairs, res.duplicates, res.skipped)}"
    for e in arch.entries[2:]:
        assert abs(e.score - mod.evaluate(e.design, qs).accuracy) < 1e-9, f"{e.design.name} must be scored on the search questions"

    # a proposer that never produces a valid design: every iteration is skipped, after MAX_REPAIRS + 1 asks
    asks = scripted([(typo, "p")] * (4 * (mod.MAX_REPAIRS + 1)))
    res = mod.meta_search(asks, qs, 4, seed=1)
    assert len(res.archive) == 2 and res.skipped == 4, f"4 iterations with nothing valid: the archive stays at its 2 seeds and skipped is 4; got {len(res.archive)} entries, skipped {res.skipped}"
    assert len(asks.calls) == 4 * (mod.MAX_REPAIRS + 1), (f"the loop should ask {mod.MAX_REPAIRS + 1} times per failed iteration ({4 * (mod.MAX_REPAIRS + 1)} in all), asked {len(asks.calls)}")
    assert res.repairs == 4 * (mod.MAX_REPAIRS + 1), f"repairs should count every rejected invalid proposal ({4 * (mod.MAX_REPAIRS + 1)}), got {res.repairs}"

    # the real thing: stand-in meta agent with typos
    for s in seeds(range(1, 4)):
        res = mod.meta_search(mod.with_typos(mod.propose, 0.25), qs, 25, s)
        arch = res.archive
        assert len(arch) == 2 + 25 - res.skipped, f"seed {s}: archive size should be seeds + iterations - skipped = {2 + 25 - res.skipped}, got {len(arch)}"
        assert res.repairs > 0, f"seed {s}: with 25% typos some proposals must have been rejected"
        best = arch.top(1)[0]
        assert best.score >= max(e.score for e in arch.entries[:2]) + 0.15, (
            f"seed {s}: after 25 iterations the best design ({best.design.name}, {best.score:.2f}) should beat the best seed by at least 0.15")
        by_name = {e.design.name: e for e in arch.entries}
        worse = [e for e in arch.entries if e.parent and e.score < by_name[e.parent].score]
        assert worse, f"seed {s}: some children must score worse than their parents, and they must still be in the archive"
        again = mod.meta_search(mod.with_typos(mod.propose, 0.25), qs, 25, s)
        assert [e.design.name for e in again.archive.entries] == [e.design.name for e in arch.entries], f"seed {s}: the same seed must give the same archive"
    return f"typos are repaired, duplicates refused, failed iterations skipped; 25 iterations take the best score from {max(e.score for e in arch.entries[:2]):.2f} to {arch.top(1)[0].score:.2f} on the search questions (seed {s})"


# =============================================================================
# Milestone 5: three sets, used for three jobs
# =============================================================================
def m5():
    pool = mod.make_questions(300, 9)
    before = list(pool)
    for s in seeds(range(1, 4)):
        se, sel, test = mod.three_way_split(pool, (50, 80, 120), s)
        assert (len(se), len(sel)) == (50, 80) and len(test) == 120, f"sizes should be 50, 80 and 120, got {len(se)}, {len(sel)}, {len(test)}"
        assert isinstance(test, mod.SealedSet), "the test set must come back wrapped in a SealedSet"
        tq = test.open()
        sets = [set(se), set(sel), set(tq)]
        assert len(sets[0] | sets[1] | sets[2]) == 250, f"seed {s}: the three sets must share no question (their union has {len(sets[0] | sets[1] | sets[2])} of 250)"
        assert (sets[0] | sets[1] | sets[2]) <= set(pool), "every question must come from the pool"
        se2, sel2, test2 = mod.three_way_split(pool, (50, 80, 120), s)
        assert se2 == se and sel2 == sel and test2.open() == tq, "the same seed must give the same split"
    se3, _, _ = mod.three_way_split(pool, (50, 80, 120), 99)
    assert se3 != se, "a different seed should shuffle differently"
    assert pool == before, "three_way_split must not modify the pool (shuffle a copy)"
    se, sel, test = mod.three_way_split(pool, (50, 80, 120), 4)
    assert se != pool[:50], "the pool must be shuffled before it is cut: the first 50 questions are the easiest-to-hardest cycle, not a random sample"
    try:
        mod.three_way_split(pool[:100], (50, 80, 120), 1)
    except ValueError:
        pass
    else:
        raise AssertionError("asking for more questions than the pool holds should raise ValueError")

    # --- choose_winner: only the shortlist is re-scored, and the selection set decides
    sel_qs = mod.make_questions(100, 31)
    ds = [D("steps", "careful", 7, 0), D("steps", "plain", 5, 2), D("steps", "plain", 3, 0), D("direct", "plain", 3, 1),
          D("direct", "plain", 1, 0), D("steps", "terse", 1, 0), D("direct", "terse", 1, 0), D("direct", "careful", 1, 0)]
    fake = [0.60, 0.90, 0.88, 0.86, 0.84, 0.82, 0.30, 0.20]       # search scores: the best true design is deliberately NOT first
    arch = mod.Archive()
    for d, sc in zip(ds, fake):
        arch.add(Entry(d, sc, mod.evaluate(d, sel_qs).calls, None, 0))
    sel_scores = {d.name: mod.evaluate(d, sel_qs).accuracy for d in ds}
    short = sorted(arch.entries, key=lambda e: (-e.score, e.calls, e.design.name))[:5]
    want = min(short, key=lambda e: (-sel_scores[e.design.name], e.calls, e.design.name))
    w, ws = mod.choose_winner(arch, sel_qs, 5)
    assert w.design == want.design, (f"the winner should be the shortlist member with the best SELECTION score ({want.design.name}, {sel_scores[want.design.name]:.2f}); "
                                     f"got {w.design.name}. The shortlist is the top 5 by SEARCH score.")
    assert abs(ws - sel_scores[w.design.name]) < 1e-9, f"the returned selection score should be {sel_scores[w.design.name]:.2f}, got {ws:.2f}"
    outside = max(ds, key=lambda d: sel_scores[d.name])
    assert w.design != outside or outside in [e.design for e in short], "a design outside the shortlist must not win"
    w1, _ = mod.choose_winner(arch, sel_qs, 1)
    assert w1.design == ds[1], f"with a shortlist of 1 the winner is simply the best search score ({ds[1].name}), got {w1.design.name}"
    tie = mod.Archive()
    tie.add(Entry(D("steps", "plain", 3, 0), 0.9, 9.0, None, 0))
    tie.add(Entry(D("steps", "plain", 3, 0).__class__("steps", "plain", 1, 0), 0.9, 3.0, None, 0))
    sa = mod.evaluate(D("steps", "plain", 3, 0), sel_qs).accuracy
    sb = mod.evaluate(D("steps", "plain", 1, 0), sel_qs).accuracy
    if sa == sb:
        assert mod.choose_winner(tie, sel_qs, 2)[0].design.samples == 1, "on a tie of selection scores the cheaper design (fewer calls) wins"

    # --- final_report: the test set is opened once
    test_qs = mod.make_questions(120, 41)
    sealed = mod.SealedSet(test_qs)
    rep = mod.final_report(w, ws, sealed)
    for k in ("design", "search", "selection", "test", "calls", "inflation"):
        assert k in rep, f"final_report must return the key {k!r}"
    exp = mod.evaluate(w.design, test_qs)
    assert abs(rep["test"] - exp.accuracy) < 1e-9 and abs(rep["calls"] - exp.calls) < 1e-9, f"'test' should be the winner's accuracy on the sealed questions ({exp.accuracy:.3f}), got {rep['test']:.3f}"
    assert rep["design"] == w.design.name and rep["search"] == w.score and rep["selection"] == ws
    assert abs(rep["inflation"] - (w.score - exp.accuracy)) < 1e-12, "inflation is the search score minus the test score"
    try:
        mod.final_report(w, ws, sealed)
    except RuntimeError:
        pass
    else:
        raise AssertionError("a second report on the same sealed set must fail: open() may be called only once, so final_report must call it exactly once and never leave a second look possible")
    return "disjoint, reproducible splits; the winner is chosen on the selection set among the search shortlist; the test set is opened once"


# =============================================================================
# Milestone 6: how much does the best of many overstate itself?
# =============================================================================
def m6():
    r = mod.inflation(5, 40, 30, 1)
    assert set(r) >= {"looks", "is", "inflation", "best_available"}, f"inflation must return a dict with keys looks, is, inflation, best_available; got {sorted(r)}"
    assert abs(r["inflation"] - (r["looks"] - r["is"])) < 1e-12 and r["best_available"] >= r["is"] - 1e-12
    assert mod.inflation(5, 40, 30, 1) == r, "same seed, same answer"
    TR = 120
    table = {}
    for s in seeds([1]):
        for n in (1, 5, 20, 60):
            table[(n, 40)] = mod.inflation(n, 40, TR, s)
        table[(60, 400)] = mod.inflation(60, 400, 40, s)
        one = table[(1, 40)]
        assert abs(one["inflation"]) < 0.025, (f"a single design has nothing to select from, so its search score should be unbiased: inflation {one['inflation']:+.3f} "
                                               "over 120 trials should be within 0.025 of zero. Draw FRESH questions in every trial and look the true accuracy up for the design you picked.")
        infl = [table[(n, 40)]["inflation"] for n in (1, 5, 20, 60)]
        assert infl[1] > infl[0] + 0.012 and infl[2] > infl[1] and infl[3] > 0.035, (
            f"on 40 questions the more designs you pick the best of, the more the winner overstates itself: expected inflation to grow past 0.035 by 60 designs, got {[round(x, 3) for x in infl]}")
        assert table[(60, 400)]["inflation"] < table[(60, 40)]["inflation"] / 2, (
            f"ten times more search questions should cut the overstatement by more than half: 40 questions {table[(60, 40)]['inflation']:+.3f}, 400 questions {table[(60, 400)]['inflation']:+.3f}")
        assert table[(60, 40)]["looks"] > table[(60, 40)]["best_available"], "the winner's search score should exceed even the best true accuracy that was on offer: that is the bias"

    # the whole protocol, 30 times: search on a small set, choose on the selection set, report on the sealed test set
    pool = mod.make_questions(1000, 2026)
    rows = []
    for sd in seeds(range(30)):
        se, sel, test = mod.three_way_split(pool, (40, 100, 400), sd)
        res = mod.meta_search(mod.with_typos(mod.propose, 0.25), se, 40, sd)
        w, ws = mod.choose_winner(res.archive, sel)
        rep = mod.final_report(w, ws, test)
        rep["truth"] = mod.true_accuracy(w.design)
        rows.append(rep)
    mean = lambda k: sum(x[k] for x in rows) / len(rows)
    search, selection, test_, truth, calls = mean("search"), mean("selection"), mean("test"), mean("truth"), mean("calls")
    if ONLY_SEED is None:
        assert search - test_ > 0.012, f"averaged over 30 runs the winner's SEARCH score should exceed its TEST score by more than 0.012; the gap was {search - test_:+.3f}"
        assert selection - test_ < search - test_, f"the selection score is biased too, but less than the search score: search {search - test_:+.3f}, selection {selection - test_:+.3f}"
        assert abs(test_ - truth) < 0.012, f"the sealed test score should be an unbiased estimate of the winner's true accuracy: test {test_:.3f}, truth {truth:.3f}"
        assert sum(x["inflation"] > 0 for x in rows) >= 20, "in most runs the search score should overstate the test score"
    note = ["best of N designs on a search set (120 trials per row, 40 for the 400-question row; 'looks' = the winner's search score, 'is' = its accuracy on 600 held-out questions):",
            f"  {'designs':>8s} {'questions':>10s} | {'looks':>6s} {'is':>6s} {'inflation':>9s} {'best on offer':>14s}"]
    for (n, q), v in sorted(table.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        note.append(f"  {n:8d} {q:10d} | {v['looks']:6.3f} {v['is']:6.3f} {v['inflation']:+9.3f} {v['best_available']:14.3f}")
    note.append(f"the full protocol, 30 searches (40 search questions, 40 iterations, 100 selection, 400 test), means:")
    note.append(f"  search {search:.3f}   selection {selection:.3f}   test {test_:.3f}   winner's true accuracy {truth:.3f}   calls/question {calls:.1f}")
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: a design becomes an agent", m1),
    (2, "Milestone 2: a gate and an archive", m2),
    (3, "Milestone 3: the stand-in meta agent", m3),
    (4, "Milestone 4: the search loop", m4),
    (5, "Milestone 5: three sets, three jobs", m5),
    (6, "Milestone 6: the best of many overstates itself", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 5 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
