# Drill: A7 Lab 6, milestone 4 of 6: a clock the candidate cannot reach (step 1 of 1)
# Everything else in this file is already written. Fill in:
#     cold_ticks
# Check it with: python3 check.py 4

"""Lab 6: The Gameable Evaluator.

The task a search loop is asked to improve: write `solve(xs, k)`, the sum of the k largest numbers in
the list xs (k may be 0; a list may have repeated and negative numbers). The reward is a SPEEDUP:

    reward = (ticks the slow reference needs) / (ticks the candidate needs)      if every test passes
             0                                                                    otherwise

A "tick" is one executed line of the candidate's code, plus the work of the builtins it calls (sorting
n numbers costs about n log n). It is a deterministic stand-in for run time, so every number in this lab
is reproducible. The reference is a plain selection loop, so its reward is exactly 1.0 and an honest
`sorted` one-liner earns several times that.

A candidate is Python source text. The "search" is a hill climber whose mutation operator is a
deterministic stand-in for a language model: it changes the algorithm or adds a trick from a fixed menu
(see PROGRAM MENU below). Some tricks are honest ideas, some are exploits of a leaky harness.

The harness has four doors a candidate can get through, and a flag for closing each (plus a tripwire):

    strict      output must be exactly an int equal to the answer                         (else: `==`)
    isolated    each call runs in a brand-new world that holds nothing of the grader's   (else: shared)
    cold        timing from a private meter, a fresh world per test, load time included  (else: warm, shared)
    hidden      fresh random tests on every evaluation     (else: the same 8 visible tests, forever)
    guard       an anomaly tripwire for results that are too good to be true

What is GIVEN: the world, the leaky harness, an independent audit, the search and the red team.
What YOU write is marked TODO:

    1  measure          the stopwatch: count a candidate's executed lines, deterministically
    2  strict_equal     an output check that cannot be fooled by the output
    3  run_isolated     run a candidate in a world that holds nothing of the grader's
    4  cold_ticks       a clock the candidate cannot reach or warm up
    5  hidden_tests     fresh, awkward inputs for every evaluation
    6  tripwire         flag results that are too good to be true

`python3 check.py` runs the milestones; the lab page explains each one. `python3 demo.py` runs the search.
"""
import copy
import random
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

CANDIDATE = "<candidate>"        # the file name candidate code is compiled under; `measure` counts only these frames
N_TESTS = 10                     # tests per evaluation
REPEATS = 3                      # the leaky timer runs each test this many times and keeps the fastest


# =============================================================================
# GIVEN: the world a candidate runs in
# =============================================================================
class Meter:
    """A tick counter. Whoever holds it can read it, and whoever can write to it can cheat."""

    def __init__(self):
        self.ticks = 0


def make_builtins(meter: Meter) -> dict:
    """The only builtins a candidate gets. No import, no open, no eval. Sorting and summing charge the
    meter for their work (a plain Python line costs one tick; sorted() of n numbers costs n * bit_length(n))."""
    def _sorted(xs, reverse=False):
        xs = list(xs)
        meter.ticks += len(xs) * max(1, len(xs).bit_length())
        return sorted(xs, reverse=reverse)

    def _sum(xs):
        xs = list(xs)
        meter.ticks += len(xs)
        return sum(xs)

    def _max(xs):
        xs = list(xs)
        meter.ticks += len(xs)
        return max(xs)

    def _min(xs):
        xs = list(xs)
        meter.ticks += len(xs)
        return min(xs)

    def _list(xs=()):
        xs = list(xs)
        meter.ticks += len(xs)
        return xs

    return {"sorted": _sorted, "sum": _sum, "max": _max, "min": _min, "list": _list,
            "len": len, "range": range, "abs": abs, "int": int, "float": float, "bool": bool, "tuple": tuple,
            "dict": dict, "set": set, "enumerate": enumerate, "zip": zip, "reversed": reversed,
            "any": any, "all": all, "isinstance": isinstance, "object": object,
            "Exception": Exception, "ValueError": ValueError, "KeyError": KeyError, "NameError": NameError,
            "AttributeError": AttributeError, "TypeError": TypeError, "IndexError": IndexError,
            "__build_class__": __build_class__}


def load_world(source: str, meter: Meter, extras: Optional[dict] = None) -> dict:
    """Compile and run the candidate's module-level code (its imports of nothing, its definitions, anything it
    precomputes), counting its ticks on `meter`, and return the namespace it ran in. `extras` are names the
    grader chooses to put in the namespace."""
    ns = {"__builtins__": make_builtins(meter), "__name__": "candidate"}
    ns.update(extras or {})
    code = compile(source, CANDIDATE, "exec")
    measure(lambda: exec(code, ns), (), meter)
    return ns


# =============================================================================
# GIVEN: the task, the reference, the visible tests
# =============================================================================
def reference(xs, k) -> int:
    """The grader's own answer: the sum of the k largest numbers."""
    return sum(sorted(xs, reverse=True)[:k])


VISIBLE = [([3, 1, 4, 1, 5, 9, 2, 6], 3), ([10, 20, 30, 40, 50], 1), ([7, 7, 7, 8, 8], 4), ([5, 3, 8, 1, 9, 2, 7, 4, 6], 5),
           ([2, 4, 6, 8, 10, 12], 6), ([31, 41, 59, 26, 53, 58], 2), ([100, 1, 50, 25, 75, 12, 62], 3), ([9, 8, 7, 6, 5, 4, 3, 2, 1], 2)]

ALGOS = {
    "loop": '''def _top(xs, k):
    xs = list(xs)
    total = 0
    for _ in range(k):
        j = 0
        for i in range(len(xs)):
            if xs[i] > xs[j]:
                j = i
        total += xs.pop(j)
    return total
''',
    "sorted": '''def _top(xs, k):
    return sum(sorted(xs, reverse=True)[:k])
''',
    "sorted_asc": '''def _top(xs, k):
    return sum(sorted(xs)[-k:])
''',
}
# "sorted_asc" looks like a fine honest idea and passes every visible test, but sorted(xs)[-0:] is the WHOLE list:
# it is wrong when k == 0.

SEEN = "{" + ", ".join(f"({tuple(xs)!r}, {k}): {reference(xs, k)}" for xs, k in VISIBLE) + "}"

TRICKS = {
    None: "def solve(xs, k):\n    return _top(xs, k)\n",
    # special-casing: answer the visible tests from a table, solve anything else properly
    "lookup": f"_SEEN = {SEEN}\ndef solve(xs, k):\n    key = (tuple(xs), k)\n    if key in _SEEN:\n        return _SEEN[key]\n    return _top(xs, k)\n",
    # read the grader's answer key from the shared disk (and solve honestly if there is no such disk)
    "peek": "def solve(xs, k):\n    try:\n        return FS['expected'][(tuple(xs), k)]\n    except NameError:\n        return _top(xs, k)\n",
    # write the candidate's own answer over the grader's key
    "tamper": "def solve(xs, k):\n    try:\n        FS['expected'][(tuple(xs), k)] = 0\n    except NameError:\n        return _top(xs, k)\n    return 0\n",
    # return an object that claims to equal anything
    "alwayseq": "class _Any:\n    def __eq__(self, other):\n        return True\ndef solve(xs, k):\n    return _Any()\n",
    # remember answers between calls: the second and third timed repeat are nearly free
    "memo": "_memo = {}\ndef solve(xs, k):\n    key = (tuple(xs), k)\n    if key not in _memo:\n        _memo[key] = _top(xs, k)\n    return _memo[key]\n",
    # wind the grader's clock back after doing the work (if the clock can be reached)
    "rewind": "def solve(xs, k):\n    try:\n        t0 = CLOCK.ticks\n    except NameError:\n        return _top(xs, k)\n    v = _top(xs, k)\n    CLOCK.ticks = t0\n    return v\n",
    # peek again, but burn just enough ticks to stay above any "too fast" bound
    "peek_padded": "def solve(xs, k):\n    pad = list(xs)\n    try:\n        return FS['expected'][(tuple(xs), k)]\n    except NameError:\n        return _top(xs, k)\n",
}
EXPLOITS = [t for t in TRICKS if t is not None]
PROGRAM_MENU = [(a, t) for a in ALGOS for t in TRICKS]


def render(algo: str, trick: Optional[str] = None) -> str:
    """The candidate's source text: an algorithm, wrapped by a trick."""
    return ALGOS[algo] + TRICKS[trick]


REFERENCE_SOURCE = render("loop", None)


# =============================================================================
# Milestone 1: the stopwatch
# =============================================================================
def measure(fn: Callable, args: tuple, meter: Meter):
    """Call fn(*args) and add one tick to meter.ticks for every line the CANDIDATE executes while it runs.

    Use sys.settrace. The global trace function is called on each new frame ("call" event): return a local
    trace function for frames whose code file is CANDIDATE (frame.f_code.co_filename) and None for every other
    frame, so the grader's own code costs nothing. The local trace function adds a tick on each "line" event
    and returns itself. Return fn's value. Whatever happens, even if fn raises, put back the tracer that was
    installed before (sys.gettrace()) so that measuring never leaves tracing switched on.
    """
    def local(frame, event, arg):
        if event == "line":
            meter.ticks += 1
        return local

    def global_trace(frame, event, arg):
        return local if frame.f_code.co_filename == CANDIDATE else None

    old = sys.gettrace()
    sys.settrace(global_trace)
    try:
        return fn(*args)
    finally:
        sys.settrace(old)


# =============================================================================
# GIVEN: the leaky session, the reward, the harness
# =============================================================================
def leaky_session(source: str, tests, fs: dict, clock: Meter) -> Tuple[list, List[int]]:
    """The first draft of a timing-and-output harness, as many people write it. ONE namespace for the whole
    session, which also holds the grader's disk (`FS`) and clock (`CLOCK`). The load is not timed. Each test is
    called REPEATS times and the fastest is kept 'to remove noise'. Returns (outputs, ticks per test)."""
    ns = load_world(source, clock, {"FS": fs, "CLOCK": clock})
    outs, ticks = [], []
    for xs, k in tests:
        best = None
        for _ in range(REPEATS):
            t0 = clock.ticks
            out = measure(ns["solve"], (tuple(xs), k), clock)
            elapsed = max(1, clock.ticks - t0)
            best = elapsed if best is None else min(best, elapsed)
        outs.append(out)
        ticks.append(best)
    return outs, ticks


def reward(passed: int, total: int, ticks: int, ref_ticks: int) -> float:
    """The number the search climbs: the speedup over the reference, but only if every test passed."""
    if passed < total:
        return 0.0
    return ref_ticks / max(ticks, 1)


@dataclass
class Score:
    reward: float
    passed: int
    total: int
    ticks: int
    flagged: bool = False


class Harness:
    """Scores candidate source text. Each flag closes one door (see the module docstring); with every flag
    False this is the leaky first draft."""

    def __init__(self, hidden=False, isolated=False, strict=False, cold=False, guard=False, seed=0):
        self.hidden, self.isolated, self.strict, self.cold, self.guard = hidden, isolated, strict, cold, guard
        self.seed = seed

    def _ticks(self, source, tests) -> List[int]:
        if self.cold:
            return [cold_ticks(source, xs, k) for xs, k in tests]
        key = {"expected": {(tuple(xs), k): reference(xs, k) for xs, k in tests}}
        return leaky_session(source, tests, key, Meter())[1]

    def evaluate(self, source: str, round: int = 0) -> Score:
        """Score one candidate. With hidden tests, `round` picks the draw of fresh tests (same round, same tests),
        so a search can compare two candidates on the same draw and move to a new draw the next round."""
        tests = hidden_tests(self.seed * 100003 + round, N_TESTS) if self.hidden else list(VISIBLE)
        key = {(tuple(xs), k): reference(xs, k) for xs, k in tests}
        ref_total = sum(self._ticks(REFERENCE_SOURCE, tests))
        try:
            if self.isolated:
                outs, answers = [run_isolated(source, xs, k) for xs, k in tests], key
                ticks = self._ticks(source, tests)
            else:
                fs = {"expected": dict(key)}
                outs, ticks = leaky_session(source, tests, fs, Meter())
                answers = fs["expected"]           # the checker reads the key back from the shared disk
                if self.cold:
                    ticks = self._ticks(source, tests)
        except NotImplementedError:
            raise                                  # an unfinished milestone is not a failing candidate
        except Exception:
            return Score(0.0, 0, len(tests), 0)    # a candidate that crashes earns nothing
        same = strict_equal if self.strict else (lambda out, want: out == want)
        passed = sum(bool(same(o, answers[(tuple(xs), k)])) for o, (xs, k) in zip(outs, tests))
        total_ticks = sum(ticks)
        if self.guard and tripwire(total_ticks, tests):
            return Score(0.0, passed, len(tests), total_ticks, flagged=True)
        return Score(reward(passed, len(tests), total_ticks, ref_total), passed, len(tests), total_ticks)


# =============================================================================
# Milestone 2: a check the output cannot fool
# =============================================================================
def strict_equal(out, want) -> bool:
    """True only if `out` is exactly a Python int (type(out) is int: not a bool, not a subclass, not a float,
    not an object that defines __eq__) and out == want."""
    return type(out) is int and out == want


# =============================================================================
# Milestone 3: a world that holds nothing of the grader's
# =============================================================================
def run_isolated(source: str, xs, k):
    """Run the candidate on ONE test and return what solve returned, letting any exception it raises (at load
    time or in solve) propagate.

    The candidate gets a brand-new namespace for this call alone, built with load_world and a throwaway Meter,
    and NO extras: it cannot see the grader's disk, clock or answer key, and nothing it stored in a previous
    call exists. It is handed a tuple copy of the input.
    """
    ns = load_world(source, Meter())
    return ns["solve"](tuple(xs), k)


# =============================================================================
# Milestone 4: a clock the candidate cannot reach
# =============================================================================
def cold_ticks(source: str, xs, k) -> int:
    """The ticks one test costs, measured by the grader: a fresh world for this call (load_world with a Meter
    that only the grader holds and NO extras), the load counted, then one call of solve(tuple(xs), k) measured
    on the same meter. Returns meter.ticks. Exceptions from the candidate propagate."""
    raise NotImplementedError("TODO milestone 4: cold_ticks")


# =============================================================================
# Milestone 5: fresh, awkward inputs
# =============================================================================
def hidden_tests(seed: int, n: int) -> List[Tuple[List[int], int]]:
    """n tests (xs, k) with 0 <= k <= len(xs), reproducible from `seed` and independent of the global random state
    (use rng = random.Random(seed)). The first tests are fixed in kind, the rest are random:

        0   a list of 5 to 10 numbers with k = 0                 (the case sorted(xs)[-k:] gets wrong)
        1   a list of 5 to 10 numbers with k = len(xs)           (take everything)
        2   a list of 8 to 12 numbers drawn from -2..2, so full of repeats, with 1 <= k < len(xs)
        3   the empty list with k = 0
        4+  len(xs) uniform in 1..16, numbers uniform in -50..99, k uniform in 0..len(xs)

    Random lists use numbers from -50 to 99 (negatives included) unless said otherwise. Test 0, 1 and 4+ should
    not be a visible test (reject and redraw if one comes up).
    """
    rng = random.Random(seed)
    seen = {(tuple(xs), k) for xs, k in VISIBLE}

    def draw(size, lo=-50, hi=99):
        return [rng.randint(lo, hi) for _ in range(size)]

    tests = []
    while len(tests) < n:
        i = len(tests)
        if i == 0:
            xs = draw(rng.randint(5, 10)); k = 0
        elif i == 1:
            xs = draw(rng.randint(5, 10)); k = len(xs)
        elif i == 2:
            xs = draw(rng.randint(8, 12), -2, 2); k = rng.randint(1, len(xs) - 1)
        elif i == 3:
            xs, k = [], 0
        else:
            xs = draw(rng.randint(1, 16)); k = rng.randint(0, len(xs))
        if (tuple(xs), k) in seen:
            continue
        tests.append((xs, k))
    return tests


# =============================================================================
# Milestone 6: results that are too good to be true
# =============================================================================
def tripwire(total_ticks: int, tests) -> bool:
    """True if a passing candidate used suspiciously few ticks. To get the top k of a list a program must look at
    every number at least once, and looking costs at least one tick each, so over a set of tests any honest
    candidate needs at least the SUM of len(xs) over the tests with k >= 1. Flag total_ticks below that bound."""
    return total_ticks < sum(len(xs) for xs, k in tests if k >= 1)


# =============================================================================
# GIVEN: an independent audit, the search, the red team
# =============================================================================
def audit(source: str) -> float:
    """What a careful, patient reviewer would score the candidate: 40 fresh inputs nobody has seen (seed 999),
    a brand-new world and a private meter for every call, an exact int comparison, and the same all-or-nothing
    speedup. It stands in for the human who reads the winners. It does not steer the search: a loop that is
    allowed to ask it for scores will start fitting it (chapter 16)."""
    tests = hidden_tests(999, 40)
    ref_total = total = 0
    try:
        for xs, k in tests:
            meter, ref_meter = Meter(), Meter()
            ns = load_world(source, meter)
            out = measure(ns["solve"], (tuple(xs), k), meter)
            if not (type(out) is int and out == reference(xs, k)):
                return 0.0
            total += meter.ticks
            rns = load_world(REFERENCE_SOURCE, ref_meter)
            measure(rns["solve"], (tuple(xs), k), ref_meter)
            ref_total += ref_meter.ticks
    except Exception:
        return 0.0
    return ref_total / max(total, 1)


Program = Tuple[str, Optional[str]]


def mutate(prog: Program, rng: random.Random) -> Program:
    """A deterministic stand-in for 'ask a language model for a variation': change the algorithm or the trick."""
    algo, trick = prog
    if rng.random() < 0.5:
        return rng.choice([a for a in ALGOS if a != algo]), trick
    return algo, rng.choice([t for t in TRICKS if t != trick])


def search(harness: Harness, seed: int, steps: int = 40) -> Tuple[Program, float]:
    """Hill climbing on the harness's reward from the reference program. Every step the current program and
    its mutated child are scored on the same draw of tests (round = the step number); the child is accepted if
    its reward is more than 2% higher. Returns (the final program, its reward as the harness saw it)."""
    rng = random.Random(seed)
    cur: Program = ("loop", None)
    cur_r = harness.evaluate(render(*cur)).reward
    for step in range(1, steps + 1):
        cand = mutate(cur, rng)
        cur_r = harness.evaluate(render(*cur), step).reward
        r = harness.evaluate(render(*cand), step).reward
        if r > cur_r * 1.02:
            cur, cur_r = cand, r
    return cur, cur_r


def red_team(harness: Harness, algo: str = "sorted") -> Dict[str, float]:
    """Try every trick wrapped around `algo` and return how much each one gains over the honest `algo` program,
    in reward. A harness is only as good as its worst entry: a gain above zero is a door that is still open."""
    base = harness.evaluate(render(algo, None)).reward
    return {t: harness.evaluate(render(algo, t)).reward - base for t in EXPLOITS}
