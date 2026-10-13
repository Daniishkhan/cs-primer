"""Self-check for Lab 3: A Linearizability Checker.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Everything is in-process and seeded: no network, no threads, the same result on every run, a few
seconds at most. Prints a tick, a cross, or "not implemented yet" for each milestone.
When a check fails it names the history (or the seed) so you can replay it.
"""
import importlib
import itertools
import os
import random
import signal
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
if target not in ("starter", "solution"):
    sys.exit("usage: python3 check.py [starter|solution]")
mod = importlib.import_module(target)
ref = importlib.import_module("solution")      # the oracle for "is this really not linearizable?"

INF = float("inf")
results = []
notes = []


def note(text):
    notes.append(text)


def _alarm(signum, frame):
    raise AssertionError("this took more than 40 seconds: is your search missing its memo, or looping?")


def check(name, fn):
    del notes[:]
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(40)
    try:
        fn()
        print(f"  ✔ {name}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
    for line in notes:
        print(line)


# ---- helpers: build histories, and an independent verifier ------------------------------

def ev(type_, process, f, value, time):
    return mod.Event(type_, process, f, value, time)


def op(i, process, f, arg, result, call, ret, indet=False):
    return mod.Op(i, process, f, arg, result, call, ret, indet)


def W(i, v, call, ret):
    return op(i, i, "write", v, None, call, ret)


def R(i, v, call, ret):
    return op(i, i, "read", None, v, call, ret)


def C(i, old, new, call, ret):
    return op(i, i, "cas", (old, new), None, call, ret)


def IW(i, v, call):
    return op(i, i, "write", v, None, call, INF, True)


def verify_order(ops, order):
    """Independent of the learner's code: is `order` (a list of op ids) a legal linearization?"""
    by_id = {o.id: o for o in ops}
    assert order is not None, "returned None for a history that is linearizable"
    assert len(set(order)) == len(order), "the order repeats an operation"
    for i in order:
        assert i in by_id, f"the order mentions op {i}, which is not in the history"
    placed = set(order)
    for o in ops:
        if not o.indeterminate:
            assert o.id in placed, f"the order leaves out op {o.id} ({o.f}), which definitely happened"
    seq = [by_id[i] for i in order]
    for a in range(len(seq)):
        for b in range(a + 1, len(seq)):
            assert not (seq[b].ret < seq[a].call), \
                f"op {seq[b].id} returned (t={seq[b].ret}) before op {seq[a].id} was called (t={seq[a].call}), yet your order puts it after"
    state = None
    for o in seq:
        if o.f == "write":
            state = o.arg
        elif o.f == "read":
            assert o.indeterminate or o.result == state, \
                f"in your order, read op {o.id} returns {o.result} but the register holds {state}"
        else:
            assert state == o.arg[0], f"in your order, cas op {o.id} expects {o.arg[0]} but the register holds {state}"
            state = o.arg[1]


# (name, history, linearizable?)
def small_cases():
    return [
        ("empty history", [], True),
        ("write then read it back", [W(0, 1, 0, 2), R(1, 1, 3, 5)], True),
        ("read of the initial value", [R(0, None, 0, 2)], True),
        ("stale read: write(1) finished, then a read returns None", [W(0, 1, 0, 2), R(1, None, 3, 5)], False),
        ("a read that overlaps a write may return the old value", [W(0, 1, 0, 10), R(1, None, 2, 4)], True),
        ("a read that overlaps a write may return the new value", [W(0, 1, 0, 10), R(1, 1, 2, 4)], True),
        ("new-old inversion: one read sees 1, a later read sees None",
         [W(0, 1, 0, 20), R(1, 1, 2, 4), R(2, None, 6, 8)], False),
        ("two writes, then the older value is read",
         [W(0, 1, 0, 2), W(1, 2, 3, 5), R(2, 1, 6, 8)], False),
        ("two overlapping writes: either may win", [W(0, 1, 0, 10), W(1, 2, 1, 9), R(2, 1, 11, 12)], True),
        ("a read of a value nobody wrote", [W(0, 1, 0, 2), R(1, 7, 3, 5)], False),
        ("cas succeeds when the value matches", [W(0, 1, 0, 2), C(1, 1, 2, 3, 5), R(2, 2, 6, 8)], True),
        ("cas that 'succeeded' on a register holding something else", [C(0, 1, 2, 0, 2)], False),
        ("a timed-out write may have taken effect", [W(0, 1, 0, 2), IW(1, 2, 3), R(2, 2, 10, 12)], True),
        ("a timed-out write may also never have happened", [W(0, 1, 0, 2), IW(1, 2, 3), R(2, 1, 10, 12)], True),
        ("a timed-out write cannot happen before it was invoked", [W(0, 1, 0, 2), R(1, 2, 3, 5), IW(2, 2, 6)], False),
        ("a timed-out write cannot be both applied and not", [W(0, 1, 0, 2), IW(1, 2, 3), R(2, 2, 10, 12), R(3, 1, 14, 16)], False),
        ("three clients: reads see writes in a consistent order",
         [W(0, 1, 0, 4), W(1, 2, 1, 5), R(2, 1, 6, 7), R(3, 1, 8, 9)], True),
        ("three clients: reads disagree about the order of two finished writes",
         [W(0, 1, 0, 4), W(1, 2, 1, 5), R(2, 1, 6, 7), R(3, 2, 8, 9), R(4, 1, 10, 11)], False),
    ]


def random_history(rng):
    n = rng.randint(3, 7)
    values = [None]
    ops = []
    for i in range(n):
        call = rng.randint(0, 14)
        ret = call + rng.randint(1, 8)
        r = rng.random()
        if r < 0.40:
            ops.append(R(i, rng.choice(values), call, ret))
        elif r < 0.85:
            v = len(values)
            values.append(v)
            ops.append(W(i, v, call, ret))
        else:
            v = len(values)
            values.append(v)
            ops.append(C(i, rng.choice(values[:-1]), v, call, ret))
        if rng.random() < 0.12 and ops[-1].f != "read":
            o = ops[-1]
            ops[-1] = o._replace(ret=INF, indeterminate=True)
    return ops


# ---- Milestone 1 ----------------------------------------------------------------------

def m1():
    events = [
        ev("invoke", 0, "write", 1, 1),
        ev("invoke", 1, "read", None, 2),
        ev("ok", 0, "write", 1, 3),
        ev("ok", 1, "read", 1, 5),
        ev("invoke", 0, "cas", (1, 2), 6),
        ev("fail", 0, "cas", (1, 2), 7),
    ]
    ops = mod.to_operations(events)
    want = [mod.Op(0, 0, "write", 1, None, 1, 3, False), mod.Op(1, 1, "read", None, 1, 2, 5, False)]
    assert ops == want, f"two ok operations should become\n    {want}\n  got\n    {ops}\n  (a `fail` operation did not happen, so it is left out)"

    events = [
        ev("invoke", 0, "write", 5, 1),
        ev("invoke", 1, "cas", (5, 6), 2),
        ev("invoke", 2, "read", None, 3),
        ev("info", 0, "write", 5, 61),
        ev("ok", 1, "cas", (5, 6), 8),
        ev("info", 2, "read", None, 63),
        ev("invoke", 3, "write", 9, 70),            # never answered at all
    ]
    ops = mod.to_operations(events)
    want = [
        mod.Op(0, 0, "write", 5, None, 1, INF, True),
        mod.Op(1, 1, "cas", (5, 6), None, 2, 8, False),
        mod.Op(2, 3, "write", 9, None, 70, INF, True),
    ]
    assert ops == want, ("an `info` write has ret=INF and indeterminate=True; an `info` read is dropped; an invoke with no"
                         f" completion counts as `info`. Expected\n    {want}\n  got\n    {ops}")

    events = [
        ev("invoke", 4, "read", None, 10),
        ev("invoke", 2, "write", 3, 12),
        ev("ok", 4, "read", None, 14),
        ev("ok", 2, "write", 3, 15),
    ]
    ops = mod.to_operations(events)
    assert [(o.id, o.process) for o in ops] == [(0, 4), (1, 2)], "ids are 0, 1, 2, ... in the order of the invoke events"
    assert ops[0].result is None and ops[0].arg is None

    for bad, why in [
        ([ev("invoke", 0, "write", 1, 1), ev("invoke", 0, "read", None, 2)], "a process invoked twice without completing"),
        ([ev("ok", 0, "read", 1, 2)], "a completion with no invoke"),
        ([ev("invoke", 0, "write", 1, 1), ev("ok", 0, "read", 1, 2)], "a completion for a different kind of operation"),
    ]:
        try:
            mod.to_operations(bad)
        except ValueError:
            continue
        raise AssertionError(f"should raise ValueError for {why}")

    total = 0
    for seed in range(20):
        ev_list = mod.simulate(mod.LeaderStore, seed)
        ops = mod.to_operations(ev_list)
        assert [o.id for o in ops] == list(range(len(ops))), "ids must be 0..n-1"
        assert all(o.call <= o.ret for o in ops)
        assert [o.call for o in ops] == sorted(o.call for o in ops), "ops must be in invocation order"
        assert not any(o.indeterminate and o.f == "read" for o in ops)
        total += len(ops)
    note(f"      converted 20 simulated histories ({total} operations in all)")


# ---- Milestone 2 ----------------------------------------------------------------------

def m2():
    M = mod.RegisterModel
    s0 = M.init()
    assert s0 is None, f"a fresh register holds None, not {s0!r}"
    assert M.step(s0, W(0, 5, 0, 1)) == (True, 5), "write(5) is always legal and the register becomes 5"
    assert M.step(5, R(0, 5, 0, 1)) == (True, 5), "read -> 5 on a register holding 5 is legal and changes nothing"
    legal, _ = M.step(5, R(0, 6, 0, 1))
    assert legal is False, "read -> 6 on a register holding 5 is not legal"
    legal, new = M.step(None, R(0, None, 0, 1))
    assert legal is True and new is None, "reading the initial None is legal"
    assert M.step(5, C(0, 5, 7, 0, 1)) == (True, 7), "cas(5 -> 7) on 5 is legal and gives 7"
    legal, new = M.step(4, C(0, 5, 7, 0, 1))
    assert legal is False and new == 4, "cas(5 -> 7) on 4 is not legal; return the old state unchanged"
    legal, _ = M.step(3, op(0, 0, "read", None, None, 0, INF, True))
    assert legal is True, "an indeterminate read is always legal"
    # replaying a sequence
    state = M.init()
    for o, expect in [(W(0, 1, 0, 1), True), (C(1, 1, 2, 0, 1), True), (R(2, 2, 0, 1), True), (R(3, 1, 0, 1), False)]:
        legal, state = M.step(state, o)
        assert legal is expect, f"replaying write(1), cas(1->2), read->2, read->1: step {o.id} should be legal={expect}"
    hash(M.step(None, W(0, 1, 0, 1))[1])


# ---- Milestone 3 ----------------------------------------------------------------------

def m3():
    for name, h, expect in small_cases():
        if len(h) > 9:
            continue
        got = mod.check_brute(h)
        if expect:
            try:
                verify_order(h, got)
            except AssertionError as e:
                raise AssertionError(f"{name}: {e}\n{mod.render(h)}")
        else:
            assert got is None, f"{name}: this history is NOT linearizable but you returned {got}\n{mod.render(h)}"
    big = [W(i, i + 1, 0, 100) for i in range(10)]
    try:
        mod.check_brute(big)
    except ValueError:
        pass
    else:
        raise AssertionError("more than 9 operations should raise ValueError (10! orders is too many)")
    note(f"      {len(small_cases())} hand-made histories decided correctly")


# ---- Milestone 4 ----------------------------------------------------------------------

def m4():
    for name, h, expect in small_cases():
        got = mod.check(h)
        if expect:
            try:
                verify_order(h, got)
            except AssertionError as e:
                raise AssertionError(f"{name}: {e}\n{mod.render(h)}")
        else:
            assert got is None, f"{name}: this history is NOT linearizable but you returned {got}\n{mod.render(h)}"

    rng = random.Random(7)
    yes = no = 0
    for k in range(400):
        h = random_history(rng)
        a = ref.check_brute(h)
        b = mod.check(h)
        if a is None:
            no += 1
            assert b is None, f"random history #{k} (seed 7) is not linearizable (brute force says so), but check returned {b}\n{mod.render(h)}"
        else:
            yes += 1
            try:
                verify_order(h, b)
            except AssertionError as e:
                raise AssertionError(f"random history #{k} (seed 7): {e}\n{mod.render(h)}")
    assert yes >= 30 and no >= 30, "internal: the random histories should include both kinds"
    note(f"      agrees with brute force on 400 random small histories ({yes} linearizable, {no} not)")

    # the memo: twelve concurrent writes, then reads that see value 1, then 2, then 1 again
    h = [W(i, i + 1, 0, 100) for i in range(12)] + [R(12, 1, 200, 201), R(13, 2, 202, 203), R(14, 1, 204, 205)]
    stats = {}
    assert mod.check(h, stats=stats) is None, "reads 1, 2, 1 after twelve one-shot writes can never be linearized"
    states = stats.get("states", 0)
    assert 0 < states <= 60000, (f"you expanded {states} search nodes. Twelve writes have 12! = 479 million orders;"
                                 " with a (linearized-set, state) memo it is about 25 thousand. Is the memo working?")
    note(f"      memo test: {states} search nodes (12! = 479001600 without a memo)")

    biggest = 0
    for seed in range(40):
        h = mod.to_operations(mod.simulate(mod.LeaderStore, seed))
        biggest = max(biggest, len(h))
        try:
            verify_order(h, mod.check(h))
        except AssertionError as e:
            raise AssertionError(f"LeaderStore history for seed {seed} must be linearizable: {e}")
    assert biggest >= 100
    note(f"      40 correct-store histories of up to {biggest} operations all linearize")


# ---- Milestone 5 ----------------------------------------------------------------------

def m5():
    assert mod.find_violation(mod.LeaderStore, range(40)) is None, \
        "the correct single-leader store was flagged. Either your checker has a bug, or to_operations does"
    found = mod.find_violation(mod.LaggingFollowerStore, range(40))
    assert found is not None, "no violation found in 40 histories of the lagging-follower store; it serves stale reads"
    seed, ops = found
    assert ref.check(ops) is None, f"you flagged seed {seed}, but a reference checker says that history IS linearizable"
    bad = sum(1 for s in range(40)
              if ref.check(ref.to_operations(ref.simulate(ref.LaggingFollowerStore, s))) is None)
    note(f"      correct store: 40 of 40 histories linearizable; lagging follower: {bad} of 40 are not")
    note(f"      first violation: seed {seed}, a history of {len(ops)} operations (replay: mod.simulate(LaggingFollowerStore, {seed}))")

    small = mod.minimal_counterexample(ops)
    ids = {o.id for o in ops}
    assert all(o.id in ids for o in small), "the counterexample must be made of operations from the history"
    assert ref.check(small) is None, "your 'counterexample' is linearizable: it is not a violation at all"
    assert ref.reads_are_explained(small), "your counterexample reads a value that no remaining write produced: keep the write"
    assert len(small) <= 6, f"the counterexample has {len(small)} operations; a stale read needs only 2 to 4. Keep shrinking"
    for i in range(len(small)):
        rest = small[:i] + small[i + 1:]
        if ref.reads_are_explained(rest):
            assert ref.check(rest) is not None, (f"op {small[i].id} ({mod.label(small[i])}) can be removed and the history still"
                                                 " fails: not minimal yet")
    note(f"      minimal counterexample ({len(small)} operations, from {len(ops)}):")
    for line in mod.render(small).split("\n"):
        note("    " + line)


print(f"Lab 3 checks against {target}.py\n")
check("Milestone 1: events to operations with intervals", m1)
check("Milestone 2: a sequential model of a register", m2)
check("Milestone 3: brute force over permutations", m3)
check("Milestone 4: Wing & Gong search with memoization", m4)
check("Milestone 5: catch the lagging follower, print a minimal counterexample", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing")
sys.exit(0 if passed == len(results) else 1)
