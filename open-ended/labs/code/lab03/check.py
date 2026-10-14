"""Self-check for Lab 3: A Mini FunSearch.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY the random cases of seed 7

Everything is seeded: the instances, the mutations, the searches. There is no network and no clock
(fuel, not seconds, limits a candidate), so the same code gives the same result on every run. The whole
check finishes in well under a minute (about twenty seconds for the reference solution).
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import ast
import importlib
import math
import os
import random
import sys
import time
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)    # random character flips make odd literals like 1abc

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


def fn_src(*body, args="item, rem"):
    """A candidate program from body lines."""
    return f"def priority({args}):\n" + "".join(f"    {line}\n" for line in body)


# An independent, deliberately plain packer, for cross-checking pack().
def oracle_pack(items, pr, calls=None):
    rems = []
    for it in items:
        cand = []
        for i, r in enumerate(rems):
            if r >= it:
                if calls is not None:
                    calls.append(1)
                cand.append((pr(it, r), -i))
        if cand:
            rems[-max(cand)[1]] -= it
        else:
            rems.append(100 - it)
    return len(rems)


RICH = fn_src("gap = rem - item", "if gap == 0:", "    return 1000", "if gap < 20 and item > 3:", "    return -gap - 50",
              "x = abs(gap - 26) * 2 // 3 % 7", "k = 0", "while k < 3:", "    k += 1",
              "return -min(x, 30) if gap > 5 else max(gap, 1) / 2 + k")


# =============================================================================
# Milestone 1: run untrusted code with a whitelist and a fuel budget
# =============================================================================
ATTACKS = [
    ("import statement", "import os\n" + fn_src("return 1")),
    ("import in the body", fn_src("import os", "return 1")),
    ("__import__", fn_src("return __import__('os').getpid()")),
    ("attribute access", fn_src("return (1).__class__")),
    ("class-hierarchy escape", fn_src("return ().__class__.__bases__[0]")),
    ("open", fn_src("return open('/etc/passwd')")),
    ("eval", fn_src("return eval('1')")),
    ("exec", fn_src("exec('x = 1')", "return 1")),
    ("lambda", fn_src("return (lambda: 1)()")),
    ("comprehension", fn_src("return sum([x for x in (1, 2)])")),
    ("power", fn_src("return item ** rem")),
    ("string constant", fn_src("return 'tight'")),
    ("f-string", fn_src("return f'{item}'")),
    ("constant just over 1e9", fn_src("return 1000000001")),
    ("extra argument", fn_src("return 1", args="item, rem, extra")),
    ("default argument", fn_src("return 1", args="item, rem=3")),
    ("wrong function name", "def score(item, rem):\n    return 1\n"),
    ("decorator", "@abs\n" + fn_src("return 1")),
    ("two functions", "def helper():\n    return 1\n" + fn_src("return 1")),
    ("nested function", fn_src("def f():", "    return 1", "return 1")),
    ("nested class", fn_src("class A:", "    pass", "return 1")),
    ("global statement", fn_src("global x", "return 1")),
    ("for loop", fn_src("for x in item:", "    pass", "return 1")),
    ("try", fn_src("try:", "    return 1", "except Exception:", "    return 2")),
    ("raise", fn_src("raise ValueError", "return 1")),
    ("assert", fn_src("assert item", "return 1")),
    ("del", fn_src("x = 1", "del x", "return 1")),
    ("yield", fn_src("yield 1")),
    ("subscript", fn_src("return rem[0]")),
    ("starred call", fn_src("return max(*[1, 2])")),
    ("keyword argument", fn_src("return max(item, rem, key=abs)")),
    ("call to something else", fn_src("return pow(item, 2)")),
    ("recursion", fn_src("return priority(item, rem)")),
    ("the hidden _tick", fn_src("_tick()", "return 1")),
    ("borrowing the hidden _tick", fn_src("t = _tick", "return 1")),
    ("unknown name", fn_src("return gap")),
    ("syntax error", "def priority(item, rem) return 1\n"),
    ("empty source", ""),
    ("null byte", fn_src("return 1") + "\x00"),
    ("too long", "# " + "x" * 2100 + "\n" + fn_src("return 1")),
    ("too many nodes", fn_src("return " + " + ".join(["item"] * 100))),
    ("deeply nested", fn_src("return " + "-" * 1500 + "item")),
]


def m1():
    fuel = mod.Fuel(10 ** 6)
    # ---- accepted programs
    for src in (mod.SEED_SRC, mod.FIRST_FIT_SRC, RICH, fn_src("return 1000000000"), fn_src("pass")):
        tree = mod.validate(src)
        assert isinstance(tree, ast.Module), f"validate must return the ast.Module it parsed; got {type(tree).__name__}"
    # ---- rejected programs
    for label, src in ATTACKS:
        try:
            mod.validate(src)
        except mod.Rejected:
            continue
        raise AssertionError(f"validate accepted the {label}: {src[:90]!r}. It must raise Rejected before anything runs")
    # ---- instrument: ticks and floats, original untouched
    tree = mod.validate(RICH)
    before = ast.dump(tree)
    new = mod.instrument(tree)
    assert ast.dump(tree) == before, "instrument must return a NEW tree and leave the one you passed in unchanged"
    ticks = [n for n in ast.walk(new) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_tick"]
    assert len(ticks) == 2, (f"RICH has one function and one while-loop, so two _tick() calls are expected "
                             f"(function entry, start of the loop body); found {len(ticks)}")
    ints = [n.value for n in ast.walk(new) if isinstance(n, ast.Constant) and type(n.value) is int]
    assert not ints, f"every int constant must become a float in the instrumented tree; still ints: {ints[:5]}"
    # ---- running it: same answers as plain Python, and the right number of ticks
    plain = {}
    exec(RICH, {}, plain)
    f = mod.compile_restricted(RICH, fuel)
    for item, rem in [(40.0, 66.0), (30.0, 30.0), (25.0, 40.0), (55.0, 100.0), (20.0, 23.0)]:
        want, got = plain["priority"](item, rem), f(item, rem)
        assert near(want, got), f"priority({item}, {rem}) should be {want} (plain Python), got {got}"
    f1 = mod.Fuel(100)
    g = mod.compile_restricted(RICH, f1)
    g(40.0, 66.0)
    assert f1.used == 4, (f"one call of RICH with gap = 26 runs the function once and the loop body three times: "
                          f"4 ticks expected, fuel.used is {f1.used}")
    f2 = mod.Fuel(100)
    h = mod.compile_restricted(mod.SEED_SRC, f2)
    assert h(40.0, 70.0) == -30.0 and h(30.0, 30.0) == -0.0
    assert f2.used == 2, "each call of a loop-free function costs exactly one tick"
    # ---- loops that do not stop
    for label, body in [("while True", ["while True:", "    pass"]),
                        ("a counter that never reaches its limit", ["x = 0", "while x >= 0:", "    x += 1"]),
                        ("a squaring loop (ints would grow without bound)", ["x = 9", "while x > 0:", "    x = x * x"])]:
        fz = mod.Fuel(1000)
        loop = mod.compile_restricted(fn_src(*body, "return 1"), fz)
        try:
            loop(1.0, 2.0)
        except mod.OutOfFuel:
            assert fz.used == 1001, f"{label}: OutOfFuel must be raised by the tick that crosses the budget (used 1001), used {fz.used}"
        else:
            raise AssertionError(f"{label}: the loop returned instead of running out of fuel")
    # ---- rejected before exec: the attacks never run
    try:
        mod.compile_restricted(fn_src("return __import__('os').getpid()"), mod.Fuel(10))
    except mod.Rejected:
        pass
    else:
        raise AssertionError("compile_restricted must call validate first and let Rejected through")
    return f"{len(ATTACKS)} attack programs rejected before they run; a squaring loop runs out of fuel instead of growing an integer"


# =============================================================================
# Milestone 2: a total evaluator
# =============================================================================
def m2():
    hashy = lambda it, rem: (it * 2654435761 + rem * 40503) % 1009
    # ---- pack by hand
    ff, bf = (lambda it, rem: 0), (lambda it, rem: -(rem - it))
    assert mod.pack([], ff) == 0, "no items, no bins"
    assert mod.pack([60, 40, 50, 50], ff) == 2, "60+40 and 50+50: two bins"
    assert mod.pack([60, 70, 30, 40], ff) == 3, "first fit: 60 | 70 | 30 goes to bin 0 | 40 fits nowhere -> a third bin"
    assert mod.pack([60, 70, 30, 40], bf) == 2, "best fit: 30 goes beside the 70, then 40 completes the 60: two bins"
    seen = []

    def spy(it, rem):
        seen.append((it, rem))
        return 0
    mod.pack([60, 70, 30, 40], spy)
    assert all(rem >= it for it, rem in seen), f"priority must only be asked about bins the item fits in; asked {[s for s in seen if s[1] < s[0]]}"
    assert seen == [(30, 40), (30, 30)], f"priority calls should be (item, rem) for feasible bins only, in bin order (the final 40 fits nowhere and is never scored); got {seen}"
    assert mod.pack([20, 20, 20], lambda it, rem: rem) == 1 and mod.pack([20, 20, 20, 20, 20, 20], lambda it, rem: -rem) == 2
    # ties go to the earliest bin
    order = []
    mod.pack([60, 60, 20], lambda it, rem: order.append(rem) or 7)
    assert order == [40, 40], f"with equal priorities the first (earliest) bin must win; priority calls saw {order}"
    # ---- pack against the oracle, with pseudo-random priorities
    for s in seeds(range(1, 9)):
        items = mod.instance(s)
        for pr in (ff, bf, hashy, lambda it, rem: -rem, lambda it, rem: (rem - it) % 7):
            a, b = mod.pack(items, pr), oracle_pack(items, pr)
            assert a == b, f"seed {s}: pack gives {a} bins, the independent packer gives {b}"
        assert mod.pack(items, bf) >= math.ceil(mod.lower_bound(items)), "no packing beats total size / capacity"
    # ---- evaluate: the numbers of chapter 9
    train = mod.make_instances(mod.TRAIN_SEEDS)
    best_fit = mod.evaluate(mod.SEED_SRC, train)
    first_fit = mod.evaluate(mod.FIRST_FIT_SRC, train)
    assert best_fit.status == "ok" and near(best_fit.score, 130.3), f"best fit on the 10 training instances uses 130.3 bins (chapter 9); got {best_fit}"
    assert near(first_fit.score, 130.7), f"first fit uses 130.7; got {first_fit.score}"
    assert best_fit.bins == tuple(oracle_pack(i, bf) for i in train), "bins is the per-instance bin count, in order (the signature)"
    assert near(best_fit.fitness, -130.3) and mod.Outcome("timeout").fitness == -math.inf
    # steps = priority calls: one shared Fuel across ALL instances
    calls = []
    for items in train[:3]:
        oracle_pack(items, bf, calls)
    out3 = mod.evaluate(mod.SEED_SRC, train[:3])
    assert out3.steps == len(calls), f"steps should be the fuel used, one tick per priority call: expected {len(calls)}, got {out3.steps}"
    assert mod.evaluate(mod.SEED_SRC, train[:3], fuel_budget=len(calls)).status == "ok", "a budget exactly equal to the steps used is enough"
    t = mod.evaluate(mod.SEED_SRC, train[:3], fuel_budget=len(calls) - 1)
    assert t.status == "timeout", ("one step short must be a timeout: the budget is shared by all instances, "
                                   f"not given afresh to each; got {t.status}")
    # ---- every outcome becomes a result
    blow = " * ".join(["1000000000"] * 40)
    cases = [
        ("best fit", mod.SEED_SRC, "ok"),
        ("division by zero", fn_src("return -(rem - item) / (item - item)"), "error"),
        ("read before assignment", fn_src("if rem < 0:", "    gap = 1", "return gap"), "error"),
        ("infinite loop", fn_src("while True:", "    pass", "return 1"), "timeout"),
        ("slow but finite", fn_src("i = 0", "while i < 2000:", "    i += 1", "return -rem"), "timeout"),
        ("returns a boolean", fn_src("return item < rem"), "bad_value"),
        ("returns True", fn_src("return True"), "bad_value"),
        ("returns None", fn_src("pass"), "bad_value"),
        ("returns infinity", fn_src(f"return {blow}"), "bad_value"),
        ("returns nan", fn_src(f"x = {blow}", "return x - x"), "bad_value"),
        ("imports a module", fn_src("import os", "return 1"), "rejected"),
        ("returns a string", fn_src("return 'tight'"), "rejected"),
        ("syntax error", "def priority(item, rem) return 1", "rejected"),
    ]
    note = []
    for label, src, want in cases:
        out = mod.evaluate(src, train[:1])
        assert out.status == want, f"{label}: expected status {want!r}, got {out.status!r} ({out.detail})"
        if want == "ok":
            assert out.ok and out.detail == ""
        else:
            assert not out.ok and out.score == math.inf and out.bins == () and out.detail, f"{label}: a failed outcome needs score inf, empty bins and a detail message; got {out}"
        note.append(f"{label:24s} {out.status:10s} {out.detail[:60]}")
    for junk in ("", "\x00", "def", "def priority(item, rem):\n", "((((((((((", "💥"):
        assert mod.evaluate(junk, train[:1]).status == "rejected", f"evaluate({junk!r}) must return a rejected outcome, not raise"
    assert mod.evaluate(mod.SEED_SRC, train[:2]) == mod.evaluate(mod.SEED_SRC, train[:2]), "evaluation must not depend on earlier evaluations"
    return "best fit 130.3 bins, first fit 130.7 on the training set (chapter 9)\n" + "\n".join(note[1:])


# =============================================================================
# Milestone 3: the mutation operator
# =============================================================================
SMALL = fn_src("gap = rem - item", "if gap < 20:", "    return -gap - 50", "return -gap")


def consts(tree):
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)]


def ops(tree):
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.BinOp, ast.UnaryOp)):
            out.append(type(n.op).__name__)
        elif isinstance(n, ast.Compare):
            out.append("/".join(type(o).__name__ for o in n.ops))
    return out


def char_flip(src, rng):
    i = rng.randrange(len(src))
    return src[:i] + rng.choice("0123456789+-*<>=() abcdefg\n") + src[i + 1:]


def m3():
    # ---- edit_constant
    t0 = ast.parse(SMALL)
    hit, deltas = set(), set()
    for s in seeds(range(200)):
        t = ast.parse(SMALL)
        assert mod.edit_constant(t, random.Random(s)) is True, "a tree with constants: edit_constant must return True"
        a, b = consts(t0), consts(t)
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        assert len(diff) == 1, f"seed {s}: exactly one constant must change; constants went from {a} to {b}"
        d = b[diff[0]] - a[diff[0]]
        assert d in (-2, -1, 1, 2), f"seed {s}: a constant must move by -2, -1, +1 or +2; it moved by {d}"
        hit.add(diff[0])
        deltas.add(d)
        again = ast.parse(SMALL)
        mod.edit_constant(again, random.Random(s))
        assert ast.dump(again) == ast.dump(t), f"seed {s}: the same rng state must give the same edit"
    assert len(hit) == len(consts(t0)) and deltas == {-2, -1, 1, 2}, \
        f"over 200 seeds every constant and every nudge should occur; constants hit {sorted(hit)}, nudges {sorted(deltas)}"
    zero_one = {}
    for s in seeds(range(100)):
        t = ast.parse(fn_src("return 1"))
        mod.edit_constant(t, random.Random(s))
        v = consts(t)[0]
        zero_one[v] = zero_one.get(v, 0) + 1
    assert min(zero_one) >= 0 and set(zero_one) == {0, 2, 3}, \
        f"1 nudged by -2, -1, +1, +2 gives 0 (twice, clamped), 0, 2, 3 and never a negative number; got {sorted(zero_one)}"
    t = ast.parse(mod.SEED_SRC)
    d = ast.dump(t)
    assert mod.edit_constant(t, random.Random(0)) is False and ast.dump(t) == d, "no constant: return False and leave the tree alone"

    # ---- edit_operator
    fams = set()
    for s in seeds(range(200)):
        t = ast.parse(SMALL)
        assert mod.edit_operator(t, random.Random(s)) is True
        a, b = ops(t0), ops(t)
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        assert len(diff) == 1, f"seed {s}: exactly one operator must change; operators went from {a} to {b}"
        x, y = a[diff[0]], b[diff[0]]
        arith, cmp_ = {"Add", "Sub", "Mult"}, {"Lt", "LtE", "Gt", "GtE"}
        assert (x in arith and y in arith) or (x in cmp_ and y in cmp_), f"seed {s}: {x} became {y}; swap within a family (+ - *) or (< <= > >=)"
        assert "USub" not in a[:0] and a.count("USub") == b.count("USub"), "unary minus must not be touched"
        fams.add("arith" if x in arith else "cmp")
    assert fams == {"arith", "cmp"}, f"over 200 seeds both arithmetic and comparison operators should be swapped; saw {fams}"
    for src in (fn_src("if rem == 3:", "    return 1", "return 2"), fn_src("return item % 7"), mod.FIRST_FIT_SRC):
        t = ast.parse(src)
        d = ast.dump(t)
        assert mod.edit_operator(t, random.Random(0)) is False and ast.dump(t) == d, \
            f"{src!r} has no + - * or < <= > >= to swap: return False and leave the tree alone (== and % are not in the families)"

    # ---- mutate
    rich = mod.canonical(RICH)
    for start in (mod.SEED_SRC, SMALL, rich):
        base = mod.canonical(start)
        kids, changed = set(), 0
        for s in seeds(range(150)):
            kid = mod.mutate(start, random.Random(s))
            assert isinstance(kid, str) and mod.is_valid(kid), f"seed {s}: mutate returned a program that validate rejects:\n{kid}"
            assert kid == mod.canonical(kid), f"seed {s}: mutate must return canonical text (ast.unparse of the tree)"
            assert kid == mod.mutate(start, random.Random(s)), f"seed {s}: mutate must be deterministic given the rng state"
            changed += kid != base
            kids.add(kid)
        assert changed >= 0.97 * len(list(seeds(range(150)))), f"mutate returned the parent unchanged {len(list(seeds(range(150)))) - changed} times out of 150"
        assert ONLY_SEED is not None or len(kids) >= 60, f"150 seeds gave only {len(kids)} different children: the edits are not varied enough"
    kids = [mod.mutate(mod.SEED_SRC, random.Random(s)) for s in seeds(range(300))]
    assert any("if " in k for k in kids) and any(("min(" in k or "max(" in k or "abs(" in k or "%" in k) for k in kids) \
        and any(k.count("gap") < 2 for k in kids), "300 children of the seed should include inserted rules, reshaped returns and name changes: use every function in EDITS"
    # an invalid or empty edit is never returned
    saved = mod.EDITS

    def corrupt(tree, rng):
        tree.body[0].body.insert(0, ast.Expr(ast.Constant("x")))
        return True

    def nothing(tree, rng):
        return True
    try:
        for bad in (corrupt, nothing, lambda t, r: False):
            mod.EDITS = (bad,)
            got = mod.mutate(SMALL, random.Random(0))
            assert got == mod.canonical(SMALL), "when no attempt gives a valid, different program, mutate returns canonical(src) unchanged"
    finally:
        mod.EDITS = saved
    assert mod.mutate(SMALL, random.Random(0), attempts=0) == mod.canonical(SMALL)

    # ---- a scenario: edits on the tree vs edits on the text
    base = mod.canonical(RICH)
    rng = random.Random(0)
    ok_tree = sum(mod.is_valid(mod.mutate(base, rng)) for _ in range(300))
    ok_text = sum(mod.is_valid(char_flip(base, rng)) for _ in range(300))
    assert ok_tree == 300, f"every tree edit must give a valid program; {300 - ok_tree} did not"
    assert ok_text < 240, "sanity check of the check: random character flips should often break the program"
    train = mod.make_instances(mod.TRAIN_SEEDS)
    note = [f"valid children of a 14-line program: tree edits {ok_tree}/300, random character flips {ok_text}/300"]

    finals, flips = [], []
    for s in seeds((1, 2, 3)):
        for fn, bucket in ((mod.mutate, finals), (char_flip, flips)):
            rng = random.Random(s)
            cur = mod.canonical(mod.SEED_SRC)
            cur_s = mod.evaluate(cur, train).score
            for _ in range(500):
                kid = fn(cur, rng)
                o = mod.evaluate(kid, train)
                if o.ok and o.score <= cur_s:
                    cur, cur_s = kid, o.score
            bucket.append(cur_s)
    assert all(f <= 130.3 + 1e-9 for f in finals), f"a hill climber that only accepts ties and improvements cannot end worse than best fit; got {finals}"
    mean_tree, mean_flip = sum(finals) / len(finals), sum(flips) / len(flips)
    if ONLY_SEED is None:
        assert mean_tree <= 130.3 - 0.4, (f"a plain hill climber using your mutate for 500 steps should beat best fit (130.3) by 0.4 bins on the "
                                          f"training set on average over seeds 1 to 3; it averaged {mean_tree:.2f}: {[round(f, 2) for f in finals]}")
        assert mean_tree < mean_flip, "tree edits should climb further than random character flips"
    note.append(f"hill climbing 500 steps from best fit (130.3 bins), mean of 3 seeds: tree edits {mean_tree:.2f}, character flips {mean_flip:.2f}")
    return "\n".join(note)


# =============================================================================
# Milestone 4: an island of clusters
# =============================================================================
def ok(score, *bins):
    return mod.Outcome("ok", score, tuple(bins))


def m4():
    # ---- softmax_weights
    w = mod.softmax_weights([0.0, 0.0], 1.0)
    assert near(w[0], 0.5) and near(w[1], 0.5), f"equal values get equal weight; got {w}"
    w = mod.softmax_weights([0.0, math.log(3)], 1.0)
    assert near(w[0], 0.25) and near(w[1], 0.75), f"softmax([0, ln 3], 1) = [0.25, 0.75]; got {w}"
    w = mod.softmax_weights([0.0, 1.0], 0.5)
    assert near(w[1], math.exp(2) / (1 + math.exp(2))), "dividing by a temperature of 0.5 doubles the gap: weight exp(2)/(1+exp(2))"
    w = mod.softmax_weights([-1000.0, -1001.0], 1.0)
    assert near(w[0], 1 / (1 + math.exp(-1))) and near(sum(w), 1.0), "subtract the maximum first, or exp(-1000) underflows to 0 and the sum is 0"
    assert near(mod.softmax_weights([5.0], 3.0)[0], 1.0)
    w = mod.softmax_weights([0.0, 1.0], 1e-3)
    assert w[0] < 1e-6 and w[1] > 1 - 1e-6, "a tiny temperature puts all the weight on the maximum"
    w = mod.softmax_weights([0.0, 1.0], 1e6)
    assert abs(w[0] - 0.5) < 1e-5, "a huge temperature is uniform"

    # ---- Island.add
    isl = mod.Island(max_clusters=3)
    assert len(isl) == 0 and isl.best() is None
    isl.add("bad", mod.Outcome("error", detail="x"))
    assert len(isl) == 0 and not isl.clusters, "only 'ok' outcomes are stored"
    a, b, c = "def priority(item, rem):\n    return -rem\n", "def priority(item, rem):\n    return -rem + 0\n", "def priority(item, rem):\n    return -(rem + 0)\n"
    isl.add(b, ok(129.0, 129, 129))
    isl.add(a, ok(129.0, 129, 129))
    isl.add(a, ok(129.0, 129, 129))
    assert len(isl) == 2 and len(isl.clusters) == 1, f"same signature = same cluster; duplicates are ignored (got {len(isl)} programs in {len(isl.clusters)} clusters)"
    assert isl.best() == (a, -129.0), f"best() is the SHORTEST program of the best cluster with its fitness; got {isl.best()}"
    for i in range(6):
        isl.add(f"def priority(item, rem):\n    return -rem + {i}\n", ok(129.0, 129, 129)) if False else None
    big = mod.Island(max_clusters=5)
    for i in range(7):
        big.add("def priority(item, rem):\n    return -rem" + " + 0" * i + "\n", ok(130.0, 130, 130))
    assert len(big) == mod.MAX_PER_CLUSTER, f"a cluster keeps at most MAX_PER_CLUSTER = {mod.MAX_PER_CLUSTER} programs; has {len(big)}"
    kept = big.clusters[(130, 130)]["programs"]
    assert kept == sorted(kept, key=lambda p: (len(p), p)) and len(kept[-1]) == len(kept[0]) + 3 * 4, f"the shortest programs are kept, sorted by length; got lengths {[len(p) for p in kept]}"
    isl2 = mod.Island(max_clusters=3)
    for i, f in enumerate([-130.0, -129.0, -131.0, -128.0]):
        isl2.add(f"p{i}", mod.Outcome("ok", -f, (i,)))
    assert len(isl2.clusters) == 3 and (2,) not in isl2.clusters, \
        f"with max_clusters = 3 the fourth cluster evicts the one with the lowest fitness (p2, fitness -131); clusters left: {list(isl2.clusters)}"
    isl3 = mod.Island(max_clusters=2)
    for i in range(3):
        isl3.add(f"q{i}", mod.Outcome("ok", 130.0, (i,)))
    assert list(isl3.clusters) == [(1,), (2,)], f"on a fitness tie the earliest-created cluster is evicted; left: {list(isl3.clusters)}"

    # ---- sample: frequencies match the two-stage softmax
    isl = mod.Island()
    P = {-130.0: ["xxxxxxxxxx"], -129.0: ["yyyyyyyyyy"], -128.0: ["zzzzzzzzzz"]}
    for i, (f, progs) in enumerate(P.items()):
        for p in progs:
            isl.add(p, mod.Outcome("ok", -f, (i,)))
    for temp, want in [(0.5, [math.exp(0), math.exp(2), math.exp(4)]), (1.0, [1, math.e, math.e ** 2]), (1000.0, [1, 1, 1])]:
        tot = sum(want)
        want = [x / tot for x in want]
        for s in seeds((5,)):
            rng = random.Random(s)
            count = {"xxxxxxxxxx": 0, "yyyyyyyyyy": 0, "zzzzzzzzzz": 0}
            N = 4000
            for _ in range(N):
                got = isl.sample(rng, 1, cluster_temp=temp)
                assert len(got) == 1, f"k = 1 must return one program, got {got}"
                count[got[0]] += 1
            freq = [count[p] / N for p in ("xxxxxxxxxx", "yyyyyyyyyy", "zzzzzzzzzz")]
            assert all(abs(f - w) < 0.04 for f, w in zip(freq, want)), \
                f"seed {s}: at cluster_temp = {temp} the clusters should be drawn with probabilities {[round(x, 3) for x in want]}, observed {[round(x, 3) for x in freq]}"
    short, long_ = "def priority(item, rem):\n    return -rem\n", "def priority(item, rem):\n    return -rem + 1 + 1 + 1 + 1\n"
    one = mod.Island()
    one.add(short, ok(130.0, 1))
    one.add(long_, ok(130.0, 1))
    d = len(long_) - len(short)
    want_short = 1 / (1 + math.exp(-d / 5.0))
    rng = random.Random(1)
    n_short = sum(one.sample(rng, 1, length_temp=5.0)[0] == short for _ in range(4000)) / 4000
    assert abs(n_short - want_short) < 0.04, f"inside a cluster, shorter programs are preferred with softmax over minus the length (length_temp = 5 -> P(short) = {want_short:.3f}); observed {n_short:.3f}"
    # ---- sample: k programs, distinct, sorted worst to best
    for s in seeds(range(20)):
        rng = random.Random(s)
        got = isl.sample(rng, 3, cluster_temp=1.0)
        assert 1 <= len(got) <= 3 and len(set(got)) == len(got), f"seed {s}: sample must return 1 to k DISTINCT programs; got {got}"
        rank = {"xxxxxxxxxx": 0, "yyyyyyyyyy": 1, "zzzzzzzzzz": 2}
        assert [rank[g] for g in got] == sorted(rank[g] for g in got), f"seed {s}: programs must be sorted from worst cluster to best, got {got}"
        assert got == isl.sample(random.Random(s), 3, cluster_temp=1.0), "sample must be deterministic given the rng state"
    # ---- a scenario with real programs
    train = mod.make_instances(mod.TRAIN_SEEDS)
    dead_gap = fn_src("gap = rem - item", "if gap == 0:", "    return 1000", "if gap < 20:", "    return -gap - 50", "return -abs(gap - 26)")
    real = mod.Island()
    names = {}
    for label, src in [("first fit", mod.FIRST_FIT_SRC), ("best fit", mod.SEED_SRC), ("best fit, spelled differently", fn_src("return -(rem - item)")),
                       ("dead-gap rule", dead_gap)]:
        out = mod.evaluate(src, train)
        real.add(mod.canonical(src), out)
        names[label] = out.score
    assert len(real.clusters) == 3 and len(real) == 4, (f"first fit, best fit (two spellings) and the dead-gap rule are 3 behaviours but 4 programs; "
                                                        f"got {len(real.clusters)} clusters, {len(real)} programs")
    top, fit = real.best()
    assert near(-fit, names["dead-gap rule"]) and top == mod.canonical(dead_gap)
    return (f"mean bins: first fit {names['first fit']:.1f}, best fit {names['best fit']:.1f}, dead-gap rule {names['dead-gap rule']:.2f}\n"
            f"4 programs fall into 3 clusters; the two spellings of best fit share one")


# =============================================================================
# Milestone 5: islands, and replacing the weakest
# =============================================================================
def build_db(fitnesses):
    """A Database whose island i has best score fitnesses[i] (one program each)."""
    db = mod.Database(len(fitnesses), "seed", mod.Outcome("ok", 130.0, (0,)))
    for i, sc in enumerate(fitnesses):
        db.islands[i] = mod.Island()
        db.islands[i].add(f"prog{i}", mod.Outcome("ok", sc, (i + 10,)))
    return db


def snapshot(isl):
    return {sig: (c["fitness"], list(c["programs"])) for sig, c in isl.clusters.items()}


def m5():
    db = mod.Database(4, "seed", mod.Outcome("ok", 130.3, (1, 2)))
    assert len(db.islands) == 4 and all(len(i) == 1 for i in db.islands), "every island starts with the seed program"
    assert db.best() == ("seed", -130.3)
    db.add(2, "better", mod.Outcome("ok", 129.0, (3, 4)))
    db.add(0, "worse", mod.Outcome("ok", 130.5, (5, 6)))
    assert db.best() == ("better", -129.0), f"best() looks at every island; got {db.best()}"
    db.add(3, "tie", mod.Outcome("ok", 129.0, (7, 8)))
    assert db.best()[0] == "better", "on a tie the lowest island index wins"
    assert len(db.islands[2]) == 2 and len(db.islands[0]) == 2 and len(db.islands[1]) == 1

    # ---- reseed by hand
    db = build_db([130.0, 128.0, 129.0, 127.0, 129.5, 126.0])     # ranks: 5 (126), 3 (127), 1 (128), 2 (129), 4 (129.5), 0 (130)
    before = [snapshot(i) for i in db.islands]
    moves = db.reseed(random.Random(0))
    assert [m[0] for m in moves] == [2, 4, 0], f"the weakest half (islands 2, 4, 0, in rank order) is replaced; got {[m[0] for m in moves]}"
    assert all(m[1] in (5, 3, 1) for m in moves), f"the source must be a surviving island (5, 3 or 1); got {moves}"
    for i, j in moves:
        assert snapshot(db.islands[i]) == {(j + 10,): (before[j][(j + 10,)][0], [f"prog{j}"])}, f"island {i} should now hold only island {j}'s best program"
    for i in (5, 3, 1):
        assert snapshot(db.islands[i]) == before[i], f"surviving island {i} must not change"
    assert db.best() == ("prog5", -126.0) and len(db.islands) == 6
    # ---- counts and edge cases
    for n, replaced in [(1, 0), (2, 1), (3, 1), (5, 2), (8, 4)]:
        d = build_db([130.0 - i for i in range(n)])
        mv = d.reseed(random.Random(1))
        assert len(mv) == replaced == n // 2 and len(d.islands) == n, f"{n} islands: {n // 2} should be replaced, got {len(mv)}"
    fresh = mod.Database(4, "seed", mod.Outcome("ok", 130.0, (0,)))
    assert [m[0] for m in fresh.reseed(random.Random(0))] == [2, 3], "with all islands tied, rank order is index order, so the last half is replaced"
    # ---- determinism, and every survivor can be a source
    srcs = set()
    for s in seeds(range(60)):
        d = build_db([130.0, 128.0, 129.0, 127.0, 129.5, 126.0])
        d2 = build_db([130.0, 128.0, 129.0, 127.0, 129.5, 126.0])
        m1_, m2_ = d.reseed(random.Random(s)), d2.reseed(random.Random(s))
        assert m1_ == m2_, "same rng state, same reseed"
        srcs.update(j for _, j in m1_)
    assert ONLY_SEED is not None or srcs == {5, 3, 1}, f"over 60 seeds every surviving island should be a source at least once; saw {sorted(srcs)}"
    # ---- a scenario: a real database, reseeded, keeps the best program
    train = mod.make_instances(mod.TRAIN_SEEDS)
    seed_out = mod.evaluate(mod.SEED_SRC, train)
    db = mod.Database(4, mod.canonical(mod.SEED_SRC), seed_out)
    rng = random.Random(3)
    for step in range(120):
        i = step % 4
        parents = db.islands[i].sample(rng, 2)
        kid = mod.stand_in_llm(parents, rng)
        db.add(i, kid, mod.evaluate(kid, train))
    best_before = db.best()
    scores = sorted(-isl.best()[1] for isl in db.islands)
    moves = db.reseed(rng)
    assert db.best() == best_before, "reseeding must never lose the best program"
    after = sorted(-isl.best()[1] for isl in db.islands)
    assert min(after) == min(scores) and len(moves) == 2
    return (f"4 islands after 120 steps, best score per island {', '.join(f'{x:.2f}' for x in scores)}\n"
            f"after reseed (islands {moves[0][0]} and {moves[1][0]} replaced):   {', '.join(f'{x:.2f}' for x in after)}")


# =============================================================================
# Milestone 6: the whole loop, and an honest report
# =============================================================================
def m6():
    train = mod.make_instances(mod.TRAIN_SEEDS)
    # ---- the bookkeeping, on a short run
    for s in seeds((1, 2)):
        r = mod.funsearch(120, s)
        assert r.calls == 120 and len(r.trace) == 120, f"seed {s}: calls and trace must both have length budget = 120; got {r.calls}, {len(r.trace)}"
        assert all(r.trace[i] <= r.trace[i + 1] for i in range(119)), f"seed {s}: the best fitness can never go down"
        assert near(r.trace[-1], r.best_outcome.fitness), "the last trace entry is the best fitness"
        assert r.evaluations == sum(r.statuses.values()) and 1 < r.evaluations <= 121, \
            f"seed {s}: evaluations counts distinct programs evaluated (including the seed) and equals the sum of statuses; got {r.evaluations}, {r.statuses}"
        assert mod.is_valid(r.best_src) and r.best_src == mod.canonical(r.best_src)
        again = mod.evaluate(r.best_src, train)
        assert again.ok and near(again.score, r.best_outcome.score), "best_outcome must be the evaluation of best_src on the training instances"
        assert r.best_outcome.fitness >= -130.3 - 1e-9, "the search can never end worse than its seed"
        r2 = mod.funsearch(120, s)
        assert (r2.best_src, r2.trace, r2.statuses) == (r.best_src, r.trace, r.statuses), f"seed {s}: the same seed must reproduce the whole run"
    assert mod.funsearch(120, 1).trace != mod.funsearch(120, 2).trace, "different seeds should give different runs"

    # ---- the mutator is pluggable, and nothing it does can break the loop
    seen = []

    def spy(parents, rng):
        seen.append(list(parents))
        return mod.mutate(parents[-1], rng)
    mod.funsearch(60, 4, mutator=spy, k=3)
    assert seen[0] == [mod.canonical(mod.SEED_SRC)], f"the first call sees only the seed program; got {seen[0]}"
    for ps in seen:
        assert 1 <= len(ps) <= 3 and len(set(ps)) == len(ps)
        sc = [mod.evaluate(p, train).score for p in ps]
        assert all(sc[i] >= sc[i + 1] for i in range(len(sc) - 1)), f"parents must come worst first, best last (mean bins non-increasing); got {sc}"
    r = mod.funsearch(40, 0, mutator=lambda parents, rng: parents[-1])
    assert r.evaluations == 1 and r.statuses == {"ok": 1} and r.calls == 40, f"a mutator that returns its parent finds nothing new: 1 evaluation (the seed), got {r.evaluations} {r.statuses}"
    r = mod.funsearch(40, 0, mutator=lambda parents, rng: f"import os  # {rng.random()}")
    assert r.statuses == {"ok": 1, "rejected": 40} and r.best_outcome.score == 130.3, f"40 garbage programs must be 40 rejections and change nothing; got {r.statuses}"
    r = mod.funsearch(30, 0, mutator=lambda parents, rng: fn_src("while True:", "    pass", f"return {rng.randint(0, 10 ** 9)}"), fuel_budget=3000)
    assert r.statuses.get("timeout", 0) >= 29 and r.best_src == mod.canonical(mod.SEED_SRC), f"infinite loops must be timeouts that cost nothing but fuel; got {r.statuses}"
    # islands take turns; reseeding happens on schedule
    added, reseeds = [], []
    orig_add, orig_reseed = mod.Database.add, mod.Database.reseed

    def spy_add(self, i, src, outcome):
        added.append(i)
        return orig_add(self, i, src, outcome)

    def spy_reseed(self, rng):
        reseeds.append(len(added))
        return orig_reseed(self, rng)
    mod.Database.add, mod.Database.reseed = spy_add, spy_reseed
    try:
        mod.funsearch(30, 0, n_islands=3, reseed_every=10, mutator=lambda parents, rng: parents[-1] + f"# {rng.random()}\n")
    finally:
        mod.Database.add, mod.Database.reseed = orig_add, orig_reseed
    assert added == [i % 3 for i in range(30)], f"call i must work on island i % n_islands and add its child there; islands used: {added}"
    assert reseeds == [10, 20, 30], f"Database.reseed must run after calls 10, 20 and 30; it ran after {reseeds} children had been added"

    # ---- report
    rp = mod.report(mod.SEED_SRC)
    assert near(rp["train"], 130.3) and near(rp["base_train"], 130.3) and near(rp["gain_train"], 0.0) and near(rp["gain_test"], 0.0)
    assert near(rp["test"], 130.7667, 1e-3) and near(rp["lower_test"], 120.24, 0.01), f"best fit on the 30 held-out instances is 130.77 bins, lower bound 120.24; got {rp}"
    rp = mod.report(mod.FIRST_FIT_SRC)
    assert near(rp["gain_train"], 130.3 - 130.7), f"gain is baseline minus program, so first fit's gain is -0.4; got {rp['gain_train']}"
    assert set(rp) == {"train", "test", "base_train", "base_test", "gain_train", "gain_test", "lower_test"}

    # ---- the scenario: a real search, reported on held-out instances
    note = []
    gains = []
    for s in seeds((1, 2, 3)):
        r = mod.funsearch(500, s)
        rp = mod.report(r.best_src)
        assert rp["gain_train"] >= 1.2, f"seed {s}: 500 calls should save at least 1.2 bins on the training set (best fit 130.3); got {rp['gain_train']:.2f}"
        assert rp["gain_test"] >= 0.7, f"seed {s}: the evolved rule should still save at least 0.7 bins on instances it never saw; got {rp['gain_test']:.2f}"
        assert r.statuses["ok"] >= 0.8 * r.evaluations
        gains.append((rp["gain_train"], rp["gain_test"]))
        note.append(f"seed {s}: {r.evaluations} programs evaluated {r.statuses}; train {rp['train']:.2f}  held-out {rp['test']:.2f}  (best fit {rp['base_train']:.2f} / {rp['base_test']:.2f}, bound {rp['lower_test']:.1f})")
    if ONLY_SEED is None:
        r = mod.funsearch(500, 1, train_seeds=(0, 1))
        rp = mod.report(r.best_src, train_seeds=(0, 1))
        note.append(f"searching on only 2 instances (seed 1): saves {rp['gain_train']:.2f} bins on them, but {rp['gain_test']:.2f} on the held-out 30")
        assert rp["gain_train"] > rp["gain_test"], "a search on 2 instances should look better on them than on held-out instances"
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: a sandbox with a whitelist and a fuel budget", m1),
    (2, "Milestone 2: an evaluator that never raises", m2),
    (3, "Milestone 3: a mutation operator on the syntax tree", m3),
    (4, "Milestone 4: an island of clusters", m4),
    (5, "Milestone 5: islands, and replacing the weakest", m5),
    (6, "Milestone 6: the loop, and a held-out report", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 3 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
