"""Self-check for Lab 6: The Gameable Evaluator.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 5 3     # milestone 5, replaying ONLY the random cases of seed 3

Everything is deterministic: "time" is a count of executed lines (no clock), the tests are drawn from
seeded random.Random generators, and the search is a seeded hill climber. There is no network and no
real sandbox: candidates are Python source run in-process by exec, with a restricted set of builtins.
The whole check finishes in a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
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


H = mod.Harness
HONEST = mod.render("sorted")
LOOP = mod.render("loop")
BUGGY = mod.render("sorted_asc")
EXPLOITS = mod.EXPLOITS


def src(*lines):
    return "\n".join(lines) + "\n"


def compiled(source, name):
    """Compile source as candidate code, run it (untraced) and return one function from it."""
    ns = {}
    exec(compile(source, mod.CANDIDATE, "exec"), ns)
    return ns[name]


def gains(harness, algo="sorted"):
    return mod.red_team(harness, algo)


def fmt_gains(g):
    return "  ".join(f"{k} {v:+.1f}" for k, v in g.items())


# =============================================================================
# Milestone 1: the stopwatch
# =============================================================================
def m1():
    # --- hand-counted: one tick per executed line of candidate code
    straight = compiled(src("def f(x):", "    a = x + 1", "    b = a * 2", "    return b"), "f")
    m = mod.Meter()
    out = mod.measure(straight, (4,), m)
    assert out == 10, f"measure must return the value fn returned (10), got {out!r}"
    assert m.ticks == 3, f"a function with three statements executes three lines: expected 3 ticks, got {m.ticks}"
    mod.measure(straight, (1,), m)
    assert m.ticks == 6, f"the meter accumulates across calls (3 + 3 = 6), got {m.ticks}"

    loop = compiled(src("def f(n):", "    s = 0", "    for i in range(n):", "        s += i", "    return s"), "f")
    t = {}
    for n in (0, 10, 20, 30):
        mm = mod.Meter()
        mod.measure(loop, (n,), mm)
        t[n] = mm.ticks
    assert t[10] > t[0] and t[20] - t[10] == t[30] - t[20] == t[10] - t[0], (
        f"a loop body that runs n times costs the same extra ticks per iteration: ticks for n = 0, 10, 20, 30 were {t}, which is not linear")

    helper = compiled(src("def g(x):", "    t = x", "    return t", "def f(x):", "    a = g(1)", "    b = g(2)", "    return a + b"), "f")
    m = mod.Meter()
    mod.measure(helper, (0,), m)
    assert m.ticks == 3 + 2 * 2, (f"lines of helper functions the candidate calls count too: f has 3 lines and calls g (2 lines) twice, so 7 ticks; got {m.ticks}. "
                                  "The global trace function must return the local tracer for EVERY frame whose co_filename is CANDIDATE, not only the first.")

    # --- the grader's own code costs nothing
    def grader_work():
        return sum(i * i for i in range(500))
    m = mod.Meter()
    assert mod.measure(grader_work, (), m) == sum(i * i for i in range(500))
    assert m.ticks == 0, f"lines outside candidate code must not be counted (the grader's own work cost {m.ticks} ticks): compare frame.f_code.co_filename with CANDIDATE"
    mixed = compiled(src("def f(cb):", "    x = cb()", "    return x"), "f")
    m = mod.Meter()
    mod.measure(mixed, (grader_work,), m)
    assert m.ticks == 2, f"a candidate that calls grader code is charged for its own two lines only, got {m.ticks}"

    # --- the tracer is put back, always
    before = sys.gettrace()
    mod.measure(straight, (1,), mod.Meter())
    assert sys.gettrace() is before, "measure must restore the previous tracer (sys.gettrace()) when it finishes"

    def other(frame, event, arg):
        return None
    sys.settrace(other)
    try:
        mod.measure(straight, (1,), mod.Meter())
        assert sys.gettrace() is other, "measure must restore whatever tracer was installed before it, not switch tracing off"
    finally:
        sys.settrace(before)
    boom = compiled(src("def f():", "    a = 1", "    raise ValueError('boom')"), "f")
    m = mod.Meter()
    try:
        mod.measure(boom, (), m)
    except ValueError:
        pass
    else:
        raise AssertionError("an exception raised by the candidate must propagate out of measure")
    assert sys.gettrace() is before, "measure must restore the tracer even when the candidate raises (use try/finally)"
    assert m.ticks == 2, f"ticks spent before the exception still count (2 lines ran), got {m.ticks}"

    # --- the leaky first draft is gameable (this is the harness you will spend the lab hardening)
    leaky = H()
    honest, slow = leaky.evaluate(HONEST), leaky.evaluate(LOOP)
    assert abs(slow.reward - 1.0) < 1e-9, f"the reference program defines reward 1.0; got {slow.reward:.3f}"
    assert honest.passed == honest.total and honest.reward > 1.8, f"an honest sorted() one-liner should be about 2x faster than the loop, got reward {honest.reward:.2f}"
    wins = {}
    for t_ in EXPLOITS:
        sc = leaky.evaluate(mod.render("sorted", t_))
        assert sc.passed == sc.total, f"against the leaky harness the '{t_}' trick should pass every test, it passed {sc.passed} of {sc.total}"
        wins[t_] = sc.reward
    weak = [k for k, v in wins.items() if v < 2 * honest.reward]
    assert not weak, f"every trick should beat the honest program by far on the leaky harness; these did not: {weak} ({ {k: round(v, 1) for k, v in wins.items()} } against honest {honest.reward:.1f})"
    bug = leaky.evaluate(BUGGY)
    assert bug.passed == bug.total and mod.audit(BUGGY) == 0.0, "the sorted(xs)[-k:] program passes all 8 visible tests, yet the audit finds it wrong"
    won = []
    for s in seeds(range(5)):
        prog, r = mod.search(H(seed=s), s)
        won.append((prog, r, mod.audit(mod.render(*prog))))
    assert all(p[1] is not None and p[1] in EXPLOITS for p, _, _ in won), f"the search on the leaky harness should end on an exploit every time, got {[p for p, _, _ in won]}"
    mean_r, mean_a = sum(r for _, r, _ in won) / len(won), sum(a for _, _, a in won) / len(won)
    assert mean_r > 20 * max(mean_a, 0.1), "the harness score of the winners should be wildly higher than their audit score"
    kinds = ", ".join(sorted({p[1] for p, _, _ in won}))
    return (f"measure counts lines exactly, restores the tracer, and ignores grader code\n"
            f"leaky harness, {len(won)} searches: winners [{kinds}] score {mean_r:.1f} by the harness and {mean_a:.1f} by the audit (honest sorted: {honest.reward:.1f})")


# =============================================================================
# Milestone 2: a check the output cannot fool
# =============================================================================
class AlwaysEqual:
    def __eq__(self, other):
        return True


class LyingInt(int):
    def __eq__(self, other):
        return True


def m2():
    good = [(5, 5), (0, 0), (-7, -7), (10 ** 12, 10 ** 12)]
    for out, want in good:
        assert mod.strict_equal(out, want) is True, f"strict_equal({out!r}, {want!r}) should be True"
    bad = [(5, 6), (-5, 5), (0, 1)]
    for out, want in bad:
        assert mod.strict_equal(out, want) is False, f"strict_equal({out!r}, {want!r}) should be False (different numbers)"
    tricks = [(AlwaysEqual(), 5, "an object whose __eq__ always says True"), (LyingInt(5), 5, "an int subclass with a lying __eq__"),
              (True, 1, "True, which equals 1 in Python"), (False, 0, "False, which equals 0"), (5.0, 5, "the float 5.0"),
              ("5", 5, "the string '5'"), (None, 0, "None"), ([5], 5, "a list"), ((5,), 5, "a tuple")]
    for out, want, what in tricks:
        got = mod.strict_equal(out, want)
        assert got is False, (f"strict_equal must reject {what} (type {type(out).__name__}) even though it may compare equal to {want}; got {got!r}. "
                              "Check type(out) is int BEFORE comparing, so the candidate's own __eq__ never runs.")
    # at the level of the harness: the always-equal trick passes the lenient check and fails the strict one
    lenient, strict = H(), H(strict=True)
    a = mod.render("sorted", "alwayseq")
    sl, ss = lenient.evaluate(a), strict.evaluate(a)
    assert sl.passed == sl.total and sl.reward > 20, f"setup: against the lenient `==` check the trick should pass everything (reward {sl.reward:.1f})"
    assert ss.passed == 0 and ss.reward == 0.0, f"with strict_equal the always-equal trick must pass no test and earn 0, it passed {ss.passed} of {ss.total} (reward {ss.reward:.1f})"
    h_l, h_s = lenient.evaluate(HONEST), strict.evaluate(HONEST)
    assert h_s.passed == h_s.total and abs(h_s.reward - h_l.reward) < 1e-9, "an honest program must score exactly the same under the strict check"
    return (f"exact ints pass; {len(tricks)} impostors (always-equal object, int subclass, True, 5.0, '5', ...) are rejected\n"
            f"always-equal trick: reward {sl.reward:.1f} with `==`, {ss.reward:.1f} with strict_equal; honest program unchanged at {h_s.reward:.2f}")


# =============================================================================
# Milestone 3: a world that holds nothing of the grader's
# =============================================================================
BLIND_PEEK = mod.ALGOS["sorted"] + src("def solve(xs, k):", "    return FS['expected'][(tuple(xs), k)]")
BLIND_TAMPER = mod.ALGOS["sorted"] + src("def solve(xs, k):", "    FS['expected'][(tuple(xs), k)] = 0", "    return 0")
BLIND_CLOCK = mod.ALGOS["sorted"] + src("def solve(xs, k):", "    CLOCK.ticks = 0", "    return _top(xs, k)")


def m3():
    for xs, k in [([5, 1, 9, 3], 2), ([], 0), ([4, 4, 4], 3), ([-3, -8, 0], 1)]:
        for source in (HONEST, LOOP):
            got = mod.run_isolated(source, xs, k)
            assert got == sum(sorted(xs, reverse=True)[:k]) and type(got) is int, f"run_isolated of an honest program on {(xs, k)} should return {sum(sorted(xs, reverse=True)[:k])}, got {got!r}"
    # the candidate receives a tuple copy
    kind = src("def solve(xs, k):", "    return 1 if isinstance(xs, tuple) else 0")
    assert mod.run_isolated(kind, [1, 2, 3], 1) == 1, "the candidate must be handed a tuple copy of the input (tuple(xs))"
    # no grader names in the world
    for name, source in [("the answer key (FS)", BLIND_PEEK), ("the grader's disk (FS)", BLIND_TAMPER), ("the clock (CLOCK)", BLIND_CLOCK)]:
        try:
            mod.run_isolated(source, [5, 1, 9], 2)
        except NameError:
            pass
        except Exception as e:
            raise AssertionError(f"a candidate that touches {name} should fail with NameError in an isolated world (nothing of the grader's exists there); it raised {type(e).__name__}: {e}")
        else:
            raise AssertionError(f"a candidate that touches {name} got an answer: its world still contains the grader's objects. Call load_world with NO extras.")
    # nothing survives from one call to the next
    counter = src("_n = 0", "def solve(xs, k):", "    global _n", "    _n += 1", "    return _n")
    a, b = mod.run_isolated(counter, [1], 1), mod.run_isolated(counter, [1], 1)
    assert (a, b) == (1, 1), f"each call must start in a brand-new world: a counter the candidate keeps between calls returned {a} and then {b} (expected 1 and 1)"
    # errors come out, they are not hidden
    for source, exc in [(src("def solve(xs, k):", "    raise ValueError('no')"), ValueError), (src("import os", "def solve(xs, k):", "    return 0"), ImportError),
                        (src("def solve(xs, k:", "    return 0"), SyntaxError)]:
        try:
            mod.run_isolated(source, [1], 1)
        except exc:
            pass
        except Exception as e:
            raise AssertionError(f"expected {exc.__name__} to propagate, got {type(e).__name__}: {e}")
        else:
            raise AssertionError(f"run_isolated must let the candidate's {exc.__name__} propagate (the harness decides what a crash is worth)")
    # at the level of the harness: answers read from the key no longer pass
    leaky, shut = H(strict=True), H(strict=True, isolated=True)
    rows = []
    for name, source in [("peek (no fallback)", BLIND_PEEK), ("tamper (no fallback)", BLIND_TAMPER)]:
        sl, ss = leaky.evaluate(source), shut.evaluate(source)
        assert sl.passed == sl.total and sl.reward > 20, f"setup: against a shared disk the '{name}' program should pass every test, it passed {sl.passed}"
        assert ss.passed == 0, f"in an isolated world the '{name}' program must fail every test, it passed {ss.passed} of {ss.total}"
        rows.append(f"{name}: reward {sl.reward:.1f} shared, {ss.reward:.1f} isolated")
    hs = shut.evaluate(HONEST)
    assert hs.passed == hs.total and hs.reward > 1.8, f"an honest program must still pass under isolation (reward {hs.reward:.2f})"
    # ... but the stopwatch is a second channel, still shared
    leak = shut.evaluate(mod.render("sorted", "peek"))
    return ("each call gets a fresh world with no FS and no CLOCK; errors propagate\n" + "\n".join(rows) +
            f"\ntwo-faced `peek` (honest when it cannot see the key): still earns {leak.reward:.1f} because the TIMING session is not isolated yet (milestone 4)")


# =============================================================================
# Milestone 4: a clock the candidate cannot reach
# =============================================================================
def m4():
    zero = src("def solve(xs, k):", "    return 0")
    assert mod.cold_ticks(zero, [1, 2, 3], 1) == 2, (f"one definition line at load time plus one `return` line in the call is 2 ticks, got {mod.cold_ticks(zero, [1, 2, 3], 1)}. "
                                                     "Count the load (it runs under measure inside load_world) AND the call, on the same meter.")
    two = src("x = 1", "def solve(xs, k):", "    y = x", "    return y")
    assert mod.cold_ticks(two, [1], 1) == 4, f"load: `x = 1` and `def` (2 ticks); call: two lines (2 ticks); expected 4, got {mod.cold_ticks(two, [1], 1)}"
    xs, k = [5, 3, 9, 1, 7, 2, 8], 3
    a = mod.cold_ticks(HONEST, xs, k)
    assert a == mod.cold_ticks(HONEST, xs, k) and a > len(xs), f"cold_ticks is deterministic and at least n ticks for sorting n numbers; got {a}"
    assert mod.cold_ticks(LOOP, xs, k) > 2 * a, "the selection loop should cost more than twice what sorted() costs on this input"
    # setup work is charged
    pre = src("_t = 0", "for _i in range(50):", "    _t += _i", "def solve(xs, k):", "    return 0")
    c = mod.cold_ticks(pre, [1], 1)
    assert c >= 100, f"work done at import time (here a 50-iteration loop, about 100 lines) is part of the cost; cold_ticks returned {c}. Load inside the measured region."
    # no warm cache
    memo = mod.render("loop", "memo")
    plain = mod.render("loop", None)
    m1_, m2_, p_ = mod.cold_ticks(memo, xs, k), mod.cold_ticks(memo, xs, k), mod.cold_ticks(plain, xs, k)
    assert m1_ == m2_, f"every call starts cold, so the memoising program must cost the same each time; got {m1_} then {m2_}"
    assert m1_ >= p_, f"a memoising program must cost at least as much as the same algorithm without the memo when nothing is ever repeated: {m1_} < {p_}"
    # the clock is not in the world
    rw = mod.cold_ticks(mod.render("loop", "rewind"), xs, k)
    assert rw >= p_, f"the rewind trick cannot find a clock to wind back in a cold world (it falls back to honest work): expected at least {p_} ticks, got {rw}"
    try:
        mod.cold_ticks(BLIND_CLOCK, xs, k)
    except NameError:
        pass
    else:
        raise AssertionError("a candidate that writes to CLOCK must fail in the cold world: it holds no names of the grader's")
    # at the level of the harness, with the other doors already shut
    pre_door = H(strict=True, isolated=True)
    cold = H(strict=True, isolated=True, cold=True)
    before, after = gains(pre_door), gains(cold)
    for t_ in ("peek", "tamper", "memo", "rewind", "peek_padded"):
        assert before[t_] > 1.5, f"setup: with the stopwatch still shared, '{t_}' should still pay (gain {before[t_]:+.1f})"
        assert after[t_] < 0.25, f"with cold timing '{t_}' should no longer pay, but it gains {after[t_]:+.2f} reward points over the honest program"
    base = cold.evaluate(HONEST)
    assert base.passed == base.total and base.reward > 1.5, f"an honest program must keep a healthy reward under cold timing, got {base.reward:.2f}"
    left = after["lookup"]
    assert left > 3, f"the lookup of visible answers is not a timing trick; with the tests still fixed it should pay (gain {left:+.1f})"
    return (f"one test costs its load plus its call, measured on a meter only the grader holds\n"
            f"gain over honest before/after cold timing: " + ", ".join(f"{t_} {before[t_]:+.1f}/{after[t_]:+.1f}" for t_ in ("peek", "tamper", "memo", "rewind")) +
            f"\nstill open: lookup {left:+.1f} (the tests never change)")


# =============================================================================
# Milestone 5: fresh, awkward inputs
# =============================================================================
def m5():
    for s in seeds(range(1, 6)):
        t = mod.hidden_tests(s, 10)
        assert len(t) == 10, f"seed {s}: asked for 10 tests, got {len(t)}"
        for xs, k in t:
            assert isinstance(xs, list) and all(type(v) is int for v in xs) and type(k) is int and 0 <= k <= len(xs), f"seed {s}: every test needs a list of ints and 0 <= k <= len(xs); got {(xs, k)}"
        (x0, k0), (x1, k1), (x2, k2), (x3, k3) = t[:4]
        assert k0 == 0 and 5 <= len(x0) <= 10, f"seed {s}: test 0 is a list of 5 to 10 numbers with k = 0; got {(x0, k0)}"
        assert k1 == len(x1) and 5 <= len(x1) <= 10, f"seed {s}: test 1 takes everything (k = len); got {(x1, k1)}"
        assert 8 <= len(x2) <= 12 and set(x2) <= {-2, -1, 0, 1, 2} and 1 <= k2 < len(x2) and len(set(x2)) < len(x2), f"seed {s}: test 2 is 8 to 12 numbers from -2..2 (so it has repeats) with 1 <= k < len; got {(x2, k2)}"
        assert (x3, k3) == ([], 0), f"seed {s}: test 3 is the empty list with k = 0; got {(x3, k3)}"
        assert all(1 <= len(xs) <= 16 and all(-50 <= v <= 99 for v in xs) for xs, _ in t[4:]), f"seed {s}: the random tests have 1 to 16 numbers from -50 to 99"
        vis = {(tuple(a), b) for a, b in mod.VISIBLE}
        assert not any((tuple(xs), k) in vis for xs, k in t), f"seed {s}: a hidden test coincides with a visible one"
        assert mod.hidden_tests(s, 10) == t, f"seed {s}: the same seed must give the same tests"
        random.seed(12345)
        a = mod.hidden_tests(s, 10)
        random.seed(999)
        assert a == mod.hidden_tests(s, 10) == t, "hidden_tests must use its own random.Random(seed), not the global generator"
    assert mod.hidden_tests(1, 10) != mod.hidden_tests(2, 10), "different seeds must give different tests"
    ks = [k for s in range(60) for xs, k in mod.hidden_tests(s, 10)[4:]]
    zeros = sum(k == 0 for k in ks)
    assert len(set(ks)) >= 12 and zeros > 0, f"the random tests should spread k over many values including 0; got {sorted(set(ks))}"
    assert len(mod.hidden_tests(5, 3)) == 3 and mod.hidden_tests(5, 3) == mod.hidden_tests(5, 10)[:3], "the first n tests are a prefix of any longer list for the same seed"
    # at the level of the harness: the table of answers stops paying, and so does an honest-looking bug
    fixed, fresh = H(strict=True, isolated=True, cold=True), H(strict=True, isolated=True, cold=True, hidden=True)
    before, after = gains(fixed), gains(fresh)
    assert before["lookup"] > 3 and after["lookup"] < 0.25, f"the lookup trick should pay on fixed tests ({before['lookup']:+.1f}) and not on fresh ones ({after['lookup']:+.2f})"
    bug_fixed, bug_fresh = fixed.evaluate(BUGGY), fresh.evaluate(BUGGY)
    assert bug_fixed.passed == bug_fixed.total and bug_fixed.reward > 1.5, f"setup: sorted(xs)[-k:] passes all 8 visible tests (reward {bug_fixed.reward:.1f})"
    assert bug_fresh.reward == 0.0 and bug_fresh.passed < bug_fresh.total, f"the hidden tests include k = 0, so the sorted(xs)[-k:] bug must be caught; it passed {bug_fresh.passed} of {bug_fresh.total}"
    good = fresh.evaluate(HONEST)
    assert good.passed == good.total and good.reward > 1.8, f"an honest program must still pass on fresh tests (reward {good.reward:.2f})"
    rounds = [fresh.evaluate(HONEST, r).reward for r in range(6)]
    assert max(rounds) - min(rounds) > 1e-6 and min(rounds) > 1.5, f"each round draws new tests, so the honest reward varies a little but stays healthy: {[round(x, 2) for x in rounds]}"
    return (f"every hidden test list has the awkward cases first (k = 0, k = len, repeats, empty), reproducible from its seed\n"
            f"lookup of visible answers: {before['lookup']:+.1f} on fixed tests, {after['lookup']:+.2f} on fresh ones; the k = 0 bug (passes all 8 visible tests) earns {bug_fresh.reward:.1f}")


# =============================================================================
# Milestone 6: results that are too good to be true
# =============================================================================
def m6():
    T = [([1, 2, 3], 1), ([4, 5], 0), ([6, 7, 8, 9], 2)]            # a bound of 3 + 4 = 7: the k = 0 test needs no reading
    for ticks, want in [(6, True), (7, False), (8, False), (0, True)]:
        got = mod.tripwire(ticks, T)
        assert got is want, f"tripwire({ticks}, tests) over lists of 3, 2 and 4 numbers (k = 1, 0, 2): the bound is 3 + 4 = 7 (the k = 0 test needs no reading), so it should be {want}; got {got!r}"
    assert mod.tripwire(0, [([1, 2, 3], 0), ([], 0)]) is False, "with k = 0 everywhere nothing must be read, so no result is too good to be true"
    assert mod.tripwire(1, [([9], 1)]) is False, "reading one number costs at least one tick: exactly at the bound is not flagged"
    # honest programs are never flagged, on any draw of hidden tests
    worst = 1e9
    for s in seeds(range(40)):
        tests = mod.hidden_tests(s, mod.N_TESTS)
        bound = sum(len(xs) for xs, k in tests if k >= 1)
        for algo in ("loop", "sorted"):
            total = sum(mod.cold_ticks(mod.render(algo), xs, k) for xs, k in tests)
            assert not mod.tripwire(total, tests), f"seed {s}: the honest '{algo}' program used {total} ticks over tests that need at least {bound}, and was flagged"
            worst = min(worst, total / max(bound, 1))
    # on its own, against the leaky harness, it catches the cheap tricks and misses the padded one
    only = H(guard=True)
    sc = {t_: only.evaluate(mod.render("sorted", t_)) for t_ in EXPLOITS}
    cheap = [t_ for t_ in EXPLOITS if t_ != "peek_padded"]
    missed = [t_ for t_ in cheap if not sc[t_].flagged]
    assert not missed, f"with only the tripwire on, these cheap tricks should be flagged (reward 0): {missed}"
    assert all(sc[t_].reward == 0.0 for t_ in cheap)
    pad = sc["peek_padded"]
    assert not pad.flagged and pad.reward > 1.5 * only.evaluate(HONEST).reward, (
        f"peek_padded burns just enough ticks to stay above the bound; the tripwire must NOT flag it, and it still beats the honest program ({pad.reward:.1f}). A tripwire is a net, not a wall.")
    honest = only.evaluate(HONEST)
    assert not honest.flagged and honest.passed == honest.total, "the honest program must pass the tripwire"

    # everything together
    full = H(strict=True, isolated=True, cold=True, hidden=True, guard=True)
    g = gains(full)
    assert max(g.values()) < 0.3, f"with every door shut no trick may pay; gains over the honest program: {fmt_gains(g)}"
    base = full.evaluate(HONEST)
    assert base.passed == base.total and base.reward > 1.8 and not base.flagged, f"the honest program must earn a healthy reward from the full harness (got {base.reward:.2f})"
    assert full.evaluate(BUGGY).reward == 0.0, "the full harness must also reject the k = 0 bug"
    assert abs(full.evaluate(LOOP).reward - 1.0) < 1e-9
    rows = []
    for s in seeds(range(8)):
        prog, r = mod.search(H(seed=s, strict=True, isolated=True, cold=True, hidden=True, guard=True), s)
        a = mod.audit(mod.render(*prog))
        assert prog == ("sorted", None), f"seed {s}: against the hardened harness the search should end on the honest sorted program, got {prog}"
        assert abs(r - a) / a < 0.35, f"seed {s}: the harness ({r:.2f}) and the audit ({a:.2f}) should agree within about 35% on the winner"
        rows.append((r, a))
    lines = ["exploit gains over the honest program (reward points), by harness:"]
    levels = [("leaky", dict()), ("strict", dict(strict=True)), ("+isolated", dict(strict=True, isolated=True)),
              ("+cold", dict(strict=True, isolated=True, cold=True)), ("+hidden", dict(strict=True, isolated=True, cold=True, hidden=True)),
              ("+tripwire", dict(strict=True, isolated=True, cold=True, hidden=True, guard=True)), ("tripwire only", dict(guard=True))]
    table = [gains(H(**f)) for _, f in levels]
    lines.append(f"  {'trick':12s}" + "".join(f"{n:>14s}" for n, _ in levels))
    for t_ in EXPLOITS:
        lines.append(f"  {t_:12s}" + "".join(f"{col[t_]:14.1f}" for col in table))
    lines.append(f"fully hardened: {len(rows)} searches all end on honest sorted; harness {sum(r for r, _ in rows) / len(rows):.2f}, audit {sum(a for _, a in rows) / len(rows):.2f}")
    return "\n".join(lines)


MILESTONES = [
    (1, "Milestone 1: the stopwatch", m1),
    (2, "Milestone 2: a check the output cannot fool", m2),
    (3, "Milestone 3: a world that holds nothing of the grader's", m3),
    (4, "Milestone 4: a clock the candidate cannot reach", m4),
    (5, "Milestone 5: fresh, awkward inputs", m5),
    (6, "Milestone 6: results that are too good to be true", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 6 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
