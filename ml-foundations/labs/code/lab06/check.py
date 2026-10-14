"""Self-check for Lab 6: A Tiny Evolution Engine.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 12    # milestone 3, replaying ONLY seed 12

Everything is deterministic: hand-worked packings first, then seeded
property checks (every mutant must be valid, the same seed must give the
same run), then a short evolution run scored on instances the search
never saw. The whole check finishes in a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import ast
import importlib
import json
import math
import os
import random
import sys
import tempfile
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

FF = "def priority(item, rem):\n    return 0\n"
BF = "def priority(item, rem):\n    return -(rem - item)\n"
SEED = mod.SEED_SRC


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
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb)
                      if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def raises(exc, fn, *a, **k):
    """True if fn raises exc. NotImplementedError passes straight up."""
    try:
        fn(*a, **k)
    except exc:
        return True
    except NotImplementedError:
        raise
    except Exception as e:
        raise AssertionError(
            f"expected {exc.__name__} but got {type(e).__name__}: {e}")
    return False


def nodes(tree):
    return len(list(ast.walk(tree)))


def wrap(body):
    return f"def priority(item, rem):\n    {body}\n"


# ── Milestone 1 ─────────────────────────────────────────────────────────
GOOD = [
    (BF, (30, 50), -20),
    (FF, (30, 50), 0),
    (wrap("return max(rem - item, 3) * 2"), (30, 50), 40),
    (wrap("gap = rem - item\n    return abs(gap - 25)"), (30, 50), 5),
]
BAD = [
    ("import os\ndef priority(item, rem):\n    return 0\n", "an import"),
    ("def priority(item, rem):\n    return 0\n"
     "def helper(x):\n    return x\n", "two functions"),
    ("def prio(item, rem):\n    return 0\n", "the wrong name"),
    ("def priority(item):\n    return 0\n", "the wrong arguments"),
    ("def priority(item, rem=3):\n    return 0\n", "a default argument"),
    ("def priority(item, rem):\n    return open('x')\n", "a call to open"),
    ("def priority(item, rem):\n    return eval('1')\n", "a call to eval"),
    ("def priority(item, rem):\n    return __import__('os')\n",
     "an underscore name"),
    ("def priority(item, rem):\n    return item.real\n", "an attribute"),
    ("def priority(item, rem):\n    return [item]\n", "a list"),
    ("def priority(item, rem):\n    for i in item:\n        pass\n",
     "a for loop"),
    ("def priority(item, rem):\n    return lambda: 1\n", "a lambda"),
    ("def priority(item, rem):\n    return (\n", "a syntax error"),
    ("def priority(item, rem):\n    return 0\n" + "#" * 2000, "long source"),
]


def milestone1():
    for src, args, want in GOOD:
        fn = mod.make_heuristic(src, mod.Fuel(1000))
        assert callable(fn), "make_heuristic must return a function"
        got = fn(*args)
        assert got == want, (
            f"{src!r} at {args}: expected {want}, got {got!r}")
    for src, why in BAD:
        assert raises(mod.Rejected, mod.make_heuristic, src,
                      mod.Fuel(1000)), (
            f"{why} must raise Rejected, but make_heuristic accepted it."
            "\n      Hint: check the node types against ALLOWED_NODES.")
    tree = mod.validate(BF)
    assert isinstance(tree, ast.Module), "validate returns the ast.Module"
    # restricted builtins: a name that is not abs, min or max is unknown
    fn = mod.make_heuristic(wrap("return len"), mod.Fuel(1000))
    assert raises(NameError, fn, 1, 2), (
        "only abs, min and max may exist in the namespace.\n"
        "      Hint: pass {'__builtins__': {...}} to exec, with just those.")
    # fuel: a loop that never ends must run the fuel out
    loop = wrap("while rem > 0:\n        pass\n    return 0")
    fn = mod.make_heuristic(loop, mod.Fuel(500))
    assert raises(mod.OutOfFuel, fn, 1, 2), (
        "an endless loop must raise OutOfFuel.\n"
        "      Hint: compile the instrument(tree) result and pass "
        "fuel.tick as _tick.")
    return f"{len(GOOD)} programs run, {len(BAD)} bad sources rejected"


# ── Milestone 2 ─────────────────────────────────────────────────────────
def first_fit(item, rem):
    return 0


def best_fit(item, rem):
    return -(rem - item)


def milestone2():
    cases = [
        ([60, 60, 40, 40], 2, 2),
        ([20, 30, 60, 20, 50], 3, 2),
        ([50, 60, 20, 30, 30], 2, 3),
        ([], 0, 0),
        ([60, 60, 60], 3, 3),
    ]
    for items, ff, bf in cases:
        got = mod.pack(first_fit, items)
        assert got == ff, (f"first fit on {items}: expected {ff} bins, "
                           f"got {got}")
        got = mod.pack(best_fit, items)
        assert got == bf, (f"best fit on {items}: expected {bf} bins, "
                           f"got {got}")
    # the 30 fits in both open bins (each has 40 left): one call per bin
    picks = []

    def spy(item, rem):
        picks.append((item, rem))
        return 0

    mod.pack(spy, [60, 60, 30])
    assert picks == [(30, 40), (30, 40)], (
        f"priority must be called once per feasible bin, in bin order: "
        f"expected [(30, 40), (30, 40)], got {picks}")
    for bad in (float("nan"), float("inf"), "x", None, True):
        assert raises(ValueError, mod.pack, lambda i, r: bad, [30, 30]), (
            f"a priority that returns {bad!r} must raise ValueError")
    # score: totals
    inst = mod.make_instances(range(3))
    want = sum(mod.pack(best_fit, i) for i in inst) / 3
    got = mod.score(BF, inst)
    assert abs(got - want) < 1e-9, f"score(best fit): expected {want}, " \
        f"got {got}"
    assert mod.score(FF, inst) > got, "first fit should use more bins here"
    # score never raises
    hostile = {
        "rejected": "import os",
        "a crash": wrap("return 1 / 0"),
        "an unknown name": wrap("return len"),
        "a bad value": wrap("return item > rem"),
        "a value that is not finite": wrap("return 1e308 * 1e308"),
        "an endless loop": wrap("while 1 > 0:\n        pass\n    return 0"),
    }
    for why, src in hostile.items():
        try:
            got = mod.score(src, inst)
        except NotImplementedError:
            raise
        except Exception as e:
            raise AssertionError(
                f"score raised {type(e).__name__} for {why}; it must "
                "return a penalty instead.\n      Hint: one try/except "
                "around the compile AND the packing.")
        assert got == mod.PENALTY, (
            f"{why}: expected the penalty {mod.PENALTY}, got {got!r}")
    assert math.isfinite(mod.PENALTY)
    # a small fuel budget turns a good program into a penalty
    assert mod.score(BF, inst, fuel_budget=50) == mod.PENALTY, (
        "with fuel_budget=50, scoring must run out of fuel.")
    assert mod.score(BF, inst, fuel_budget=10 ** 6) == want
    return "first fit and best fit packings match; bad programs score " \
        f"{mod.PENALTY:g}"


# ── Milestone 3 ─────────────────────────────────────────────────────────
def milestone3():
    NUDGES = set(mod.NUDGES)
    expr = wrap("return rem * 2 + 3")
    for s in seeds(range(20)):
        rng = random.Random(s)
        tree = ast.parse(expr)
        before = [c.value for c in ast.walk(tree)
                  if isinstance(c, ast.Constant)]
        ok = mod.perturb_constant(tree, rng)
        after = [c.value for c in ast.walk(tree)
                 if isinstance(c, ast.Constant)]
        diff = [(b, a) for b, a in zip(before, after) if b != a]
        assert ok is True and len(diff) == 1, (
            f"seed {s}: perturb_constant must change exactly one "
            f"constant and return True; constants went {before} -> "
            f"{after}")
        assert diff[0][1] - diff[0][0] in NUDGES, (
            f"seed {s}: the change {diff[0]} is not one of {sorted(NUDGES)}")
    t = ast.parse(wrap("return rem - item"))
    assert mod.perturb_constant(t, random.Random(0)) is False, (
        "no constants: perturb_constant must return False")
    # swap_operator
    for s in seeds(range(20)):
        tree = ast.parse(wrap("return rem * 2 + item"))
        ops = lambda t: [type(n.op).__name__ for n in ast.walk(t)
                         if isinstance(n, ast.BinOp)]
        before = ops(tree)
        ok = mod.swap_operator(tree, random.Random(s))
        after = ops(tree)
        changed = [1 for b, a in zip(before, after) if a != b]
        assert ok is True and len(changed) == 1, (
            f"seed {s}: swap_operator must change exactly one operator; "
            f"{before} -> {after}")
        assert set(after) <= {"Add", "Sub", "Mult"}, (
            f"only + - * may appear, got {after}")
    t = ast.parse(wrap("return 5"))
    assert mod.swap_operator(t, random.Random(0)) is False, (
        "no binary operator: swap_operator must return False")
    # wrap_expression
    forms = set()
    for s in seeds(range(40)):
        tree = ast.parse(wrap("return rem - item"))
        assert mod.wrap_expression(tree, random.Random(s)) is True
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree)
        forms.add(text.split("return ")[1])
        mod.validate(text)
    legal = {"abs(rem - item)", "(rem - item) * (rem - item)"}
    assert forms <= legal and (ONLY_SEED is not None or forms == legal), (
        "wrapping `rem - item` should give abs(...) or the square; "
        f"got {sorted(forms)}")
    big = wrap("return (rem - item) * (rem + item) + (item - 1) * rem")
    size = nodes(ast.parse(big))
    for s in seeds(range(40)):
        tree = ast.parse(big)
        mod.wrap_expression(tree, random.Random(s))
        assert nodes(tree) <= size + 3, (
            f"seed {s}: a large expression must be wrapped in abs, "
            f"never squared (the tree grew from {size} to {nodes(tree)})."
            "\n      Hint: skip the square above SQUARE_LIMIT nodes.")
    # mutate
    seen = set()
    for s in seeds(range(150)):
        for src in (SEED, FF, BF):
            out = mod.mutate(src, random.Random(s))
            again = mod.mutate(src, random.Random(s))
            assert out == again, (
                f"seed {s}: mutate is not deterministic for the same rng")
            assert isinstance(out, str)
            canon = ast.unparse(ast.parse(src))
            assert out != canon, f"seed {s}: mutate returned its input"
            try:
                mod.validate(out)
            except mod.Rejected as e:
                raise AssertionError(
                    f"seed {s}: mutate produced an invalid program "
                    f"({e}):\n{out}")
            if src == SEED:
                seen.add(out)
    assert ONLY_SEED is not None or len(seen) >= 10, (
        f"only {len(seen)} different mutants of the seed program in 150 "
        "tries; are all three operators in use?")
    rng_a, rng_b = random.Random(7), random.Random(7)
    chain_a = chain_b = SEED
    for _ in range(10):
        chain_a = mod.mutate(chain_a, rng_a)
        chain_b = mod.mutate(chain_b, rng_b)
    assert chain_a == chain_b, "a chain of mutations must replay exactly"
    return f"{len(seen)} different valid mutants of the seed in 150 draws"


# ── Milestone 4 ─────────────────────────────────────────────────────────
def milestone4():
    a = "def priority(item, rem):\n    return -(rem - item)\n"
    b = ("def priority(item,rem):\n"
         "    # best fit\n"
         "    return   -(rem-item)\n")
    h = mod.canonical_hash(a)
    assert isinstance(h, str) and len(h) == 12, (
        f"expected a 12-character string, got {h!r}")
    assert all(c in "0123456789abcdef" for c in h), f"{h!r} is not hex"
    assert h == mod.canonical_hash(b), (
        "spacing and comments must not change the hash.\n"
        "      Hint: hash ast.unparse(ast.parse(src)), not src.")
    assert h != mod.canonical_hash(FF), "different programs, same hash"
    assert mod.canonical_hash(wrap("return 1")) != \
        mod.canonical_hash(wrap("return 2"))
    arch = mod.Archive()
    assert arch.best() is None, "an empty archive has no best"
    assert arch.add(a, "", 88.5) is True
    assert arch.add(b, "zzz", 1.0) is False, (
        "the same program in other formatting is a duplicate: return "
        "False and store nothing")
    assert len(arch.entries) == 1 and len(arch.lines) == 1
    assert b in arch and wrap("return 7") not in arch
    e = arch.entries[h]
    assert (e.hash, e.parent, e.score) == (h, "", 88.5)
    assert e.src == ast.unparse(ast.parse(a)), "store the canonical source"
    arch.add(FF, h, 90.0)
    arch.add(wrap("return rem * 1"), h, 88.5)
    best = arch.best()
    assert best.score == 88.5 and best.hash != "", "lowest score wins"
    assert len(best.src) == min(len(x.src) for x in arch.entries.values()
                                if x.score == 88.5), (
        "on equal scores the shorter source is the best")
    rows = [json.loads(line) for line in arch.lines]
    assert [sorted(r) for r in rows] == [["hash", "parent", "score", "src"]
                                         ] * 3, (
        f"each line needs the keys hash, parent, score, src; got "
        f"{[sorted(r) for r in rows]}")
    assert rows[1]["parent"] == h and rows[1]["score"] == 90.0
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "archive.jsonl")
        arch2 = mod.Archive(path)
        arch2.add(a, "", 88.5)
        arch2.add(a, "", 88.5)
        arch2.add(FF, h, 90.0)
        with open(path) as f:
            lines = f.read().splitlines()
        assert lines == arch2.lines and len(lines) == 2, (
            f"the file must hold exactly the archive's lines, one per "
            f"new program; got {len(lines)} lines")
    return "hash ignores layout; the archive keeps one line per new program"


# ── Milestone 5 ─────────────────────────────────────────────────────────
GENERATIONS, POP = 30, 12


def milestone5():
    train = mod.make_instances(mod.TRAIN_SEEDS)
    test = mod.make_instances(mod.TEST_SEEDS)
    ff_test = mod.score(FF, test)
    bf_test = mod.score(BF, test)
    note = ""
    for s in seeds((0, 1, 2)):
        arch = mod.evolve(s, GENERATIONS, POP)
        best = arch.best()
        start = mod.score(SEED, train)
        assert mod.score(best.src, train) == best.score, (
            f"seed {s}: the archive's best score does not match a fresh "
            "score of its source")
        assert best.score <= start - 2.0, (
            f"seed {s}: expected the best training score to beat the seed "
            f"program ({start}) by 2 bins or more, got {best.score}.\n"
            "      Hint: are children being scored and added, and do the "
            "elites carry over?")
        held = mod.score(best.src, test)
        assert held < ff_test, (
            f"seed {s}: on held-out instances the best program uses "
            f"{held} bins, first fit {ff_test}. It should beat first fit.")
        assert held <= bf_test + 1e-9, (
            f"seed {s}: held-out {held} bins against best fit's "
            f"{bf_test}. Within this budget the search should match it.")
        # archive structure
        assert arch.lines[0] and json.loads(arch.lines[0])["parent"] == ""
        for h, e in arch.entries.items():
            assert h == mod.canonical_hash(e.src)
            assert e.parent == "" or e.parent in arch.entries, (
                f"seed {s}: entry {h} names a parent {e.parent!r} that "
                "is not in the archive")
        assert len(arch.lines) == len(arch.entries), "one line per entry"
        # exact reproducibility
        again = mod.evolve(s, GENERATIONS, POP)
        assert again.best().hash == best.hash and \
            again.lines == arch.lines, (
            f"seed {s}: the same seed gave a different run.\n"
            "      Hint: take every random number from one "
            "random.Random(seed), and never iterate over a set.")
        note = note or (f"seed {s}: train {start:g} -> {best.score:g} bins; "
                f"held-out {held:.2f} (first fit {ff_test:.2f}, best fit "
                f"{bf_test:.2f}); {len(arch.entries)} programs tried")
    a, b = mod.evolve(0, GENERATIONS, POP), mod.evolve(1, GENERATIONS, POP)
    assert ONLY_SEED is not None or a.lines != b.lines, (
        "seeds 0 and 1 produced identical runs; is the seed used?")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "run.jsonl")
        arch = mod.evolve(0, 5, 8, path=path)
        with open(path) as f:
            assert f.read().splitlines() == arch.lines, (
                "evolve(path=...) must write the archive's log to the file")
    return note


t0 = time.time()
print(f"Lab 6 checks against {target}.py\n")
check(1, "Milestone 1: validate and compile a candidate", milestone1)
check(2, "Milestone 2: pack and score, every outcome a number", milestone2)
check(3, "Milestone 3: mutate the syntax tree", milestone3)
check(4, "Milestone 4: canonical hash and the archive", milestone4)
check(5, "Milestone 5: the evolution loop", milestone5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing  "
      f"({time.time() - t0:.1f} s)")
