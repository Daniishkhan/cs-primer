"""Self-check for Lab 6.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Time is simulated: a FakeClock moves forward when code "sleeps", so a minute-long outage
runs in milliseconds, nothing really waits and every run is identical. Randomness is
seeded. The only real threads are in the bulkhead test, and they are released by events,
not by timing. No network. Prints a tick, a cross, or "not implemented yet" per milestone.
"""
import importlib
import os
import random
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
notes = []


def note(text):
    notes.append(text)


def check(name, fn):
    del notes[:]
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
    for line in notes:
        print(line)


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def raises(exc, fn, msg):
    try:
        fn()
    except exc:
        return
    except NotImplementedError:
        raise
    except Exception as e:
        raise AssertionError(f"{msg} (got {type(e).__name__}: {e} instead)")
    raise AssertionError(msg)


Phase, FlakyDependency, FakeClock = mod.Phase, mod.FlakyDependency, mod.FakeClock


# --- Milestone 1 ---------------------------------------------------------------------
def m1():
    c = FakeClock()
    assert c.now() == 0.0
    r = mod.with_timeout(c, lambda: (c.sleep(0.3), "fast")[1], 0.5)
    assert r == "fast" and close(c.now(), 0.3), f"a call that takes 0.3 s inside a 0.5 s timeout should return its result at t=0.3, now={c.now()}"

    c = FakeClock()
    raises(TimeoutError, lambda: mod.with_timeout(c, lambda: c.sleep(2.0), 0.5),
           "a call that would take 2 s with a 0.5 s timeout must raise TimeoutError")
    assert close(c.now(), 0.5), f"the caller stops waiting at start+timeout: expected t=0.5, got t={c.now()} (the 2 s are not 'spent')"

    c = FakeClock(100.0)
    mod.with_timeout(c, lambda: c.sleep(0.5), 0.5)
    assert close(c.now(), 100.5), "a call that takes exactly the timeout is not a timeout"

    c = FakeClock()

    def two_steps():
        c.sleep(0.3)
        c.sleep(0.3)
    raises(TimeoutError, lambda: mod.with_timeout(c, two_steps, 0.5), "the timeout covers the whole call: 0.3 + 0.3 > 0.5")
    assert close(c.now(), 0.5), f"time must stop at the deadline in the middle of the second sleep: t={c.now()}"

    # Deadline state is cleaned up, even after an exception, and nested deadlines can only tighten.
    c.sleep(100)                                                    # would raise if a stale deadline was left behind
    c = FakeClock()
    with c.deadline(1.0):
        raises(TimeoutError, lambda: mod.with_timeout(c, lambda: c.sleep(5.0), 10.0),
               "an inner timeout of 10 s inside an outer deadline of 1 s must still stop at 1 s")
        assert close(c.now(), 1.0)
    c.sleep(50)

    class Boom(Exception):
        pass

    def boom():
        raise Boom()
    raises(Boom, lambda: mod.with_timeout(c, boom, 1.0), "exceptions from the call must pass through untouched")
    c.sleep(50)

    # With the fake dependency.
    c = FakeClock()
    dep = FlakyDependency(c, [Phase(0, latency=3.0)])
    raises(TimeoutError, lambda: mod.with_timeout(c, dep.call, 0.5), "a 3 s dependency call with a 0.5 s timeout must time out")
    assert dep.calls == 1 and close(c.now(), 0.5), "the call reached the dependency (it will keep working on it), but we waited only 0.5 s"
    dep2 = FlakyDependency(c, [Phase(0, latency=0.05)])
    t0 = c.now()
    assert mod.with_timeout(c, dep2.call, 0.5) == "ok" and close(c.now() - t0, 0.05), "a healthy call costs exactly its latency"
    note("      a 3.0 s call under a 0.5 s timeout: TimeoutError at t=0.5, and the dependency still counted the call")


# --- Milestone 2 ---------------------------------------------------------------------
def m2():
    pol = mod.RetryPolicy(max_attempts=4, base=0.1, cap=2.0)
    rng = random.Random(1)
    for n in range(8):
        bound = min(pol.cap, pol.base * 2 ** n)
        ds = [mod.backoff_delay(n, pol, rng) for _ in range(2000)]
        assert all(0 <= d <= bound + 1e-12 for d in ds), f"retry {n}: delays must lie in [0, {bound}], saw {min(ds)}..{max(ds)}"
        assert max(ds) > 0.9 * bound and min(ds) < 0.1 * bound, f"retry {n}: full jitter should use the whole range [0, {bound}], saw {min(ds):.3f}..{max(ds):.3f}"
        mean = sum(ds) / len(ds)
        assert 0.4 * bound < mean < 0.6 * bound, f"retry {n}: the mean of full jitter is bound/2 = {bound / 2:.3f}, got {mean:.3f}"
    assert max(mod.backoff_delay(20, pol, rng) for _ in range(500)) <= pol.cap + 1e-12, "the cap must hold for large retry numbers"
    note("      full jitter: delay n is uniform in [0, min(2.0, 0.1 * 2^n)]; bounds and means verified")

    def run(failures, exc, seed=3, policy=pol, budget=None):
        c = FakeClock()
        left = [failures]
        seen = []

        def fn():
            seen.append(c.now())
            if left[0] > 0:
                left[0] -= 1
                raise exc()
            return "ok"
        try:
            res = mod.retry(c, random.Random(seed), fn, policy, budget)
        except Exception as e:
            res = e
        return res, seen, c

    res, seen, c = run(2, mod.TransientError)
    assert res == "ok" and len(seen) == 3, f"two 503s then success: expect 3 calls and 'ok', got {len(seen)} calls and {res!r}"
    assert len(c.sleeps) == 2 and 0 <= c.sleeps[0] <= 0.1 and 0 <= c.sleeps[1] <= 0.2, f"backoff sleeps should be in [0,0.1] then [0,0.2], got {c.sleeps}"
    assert close(seen[1] - seen[0], c.sleeps[0]) and close(seen[2] - seen[1], c.sleeps[1]), "the delays must really be slept on the clock"
    assert run(2, mod.TransientError, seed=3)[2].sleeps == c.sleeps, "same seed, same delays"
    assert run(2, mod.TransientError, seed=4)[2].sleeps != c.sleeps, "a different seed should give different delays"

    res, seen, c = run(99, mod.TransientError)
    assert isinstance(res, mod.TransientError) and len(seen) == 4, f"always failing: exactly max_attempts=4 calls, then the error; got {len(seen)} calls, {res!r}"
    assert len(c.sleeps) == 3, "no sleep after the last attempt"
    res, seen, c = run(99, mod.PermanentError)
    assert isinstance(res, mod.PermanentError) and len(seen) == 1 and c.sleeps == [], "a permanent (400-style) error must not be retried at all"
    res, seen, c = run(99, mod.CircuitOpenError)
    assert isinstance(res, mod.CircuitOpenError) and len(seen) == 1, "a rejection (breaker open) must not be retried"
    res, seen, c = run(2, TimeoutError)
    assert res == "ok" and len(seen) == 3, "timeouts are retryable"
    res, seen, c = run(5, ValueError)
    assert isinstance(res, ValueError) and len(seen) == 1, "unknown exceptions are bugs, not transient faults: do not retry them"
    res, seen, c = run(1, mod.TransientError, policy=mod.RetryPolicy(max_attempts=1))
    assert isinstance(res, mod.TransientError) and len(seen) == 1, "max_attempts=1 means no retries"

    # The budget: retries <= 10% of calls in the window.
    c = FakeClock()
    b = mod.RetryBudget(c, window=10.0, ratio=0.1, min_retries=0)
    assert not b.can_retry(), "no calls recorded yet: no retries allowed"
    for _ in range(100):
        b.record_call()
    granted = 0
    while b.can_retry():
        b.record_retry()
        granted += 1
        assert granted <= 100, "can_retry() never said no"
    assert granted == 10, f"100 calls at ratio 0.1 allow exactly 10 retries, got {granted}"
    c.sleep(10.5)
    assert not b.can_retry(), "after the window passes, old calls and old retries are forgotten"
    for _ in range(30):
        b.record_call()
    n = 0
    while b.can_retry():
        b.record_retry()
        n += 1
    assert n == 3, f"30 fresh calls allow 3 retries, got {n}"
    b2 = mod.RetryBudget(c, window=10.0, ratio=0.1, min_retries=3)
    n = 0
    while b2.can_retry():
        b2.record_retry()
        n += 1
    assert n == 3, "min_retries=3 lets a quiet service retry 3 times with no traffic"

    # retry() honours the budget: 50 hopeless calls would cost 200 attempts without one.
    for with_budget in (False, True):
        c = FakeClock()
        budget = mod.RetryBudget(c, window=10_000.0, ratio=0.1) if with_budget else None
        attempts = [0]

        def always_503():
            attempts[0] += 1
            raise mod.TransientError()
        rng = random.Random(5)
        for _ in range(50):
            raises(mod.TransientError, lambda: mod.retry(c, rng, always_503, pol, budget), "the last error must be re-raised")
        if with_budget:
            assert 50 <= attempts[0] <= 55, f"50 calls with a 10% budget: at most 5 retries, so at most 55 attempts; got {attempts[0]}"
            assert attempts[0] > 50, "the budget should still allow some retries"
            note(f"      50 hopeless calls: {attempts[0]} attempts with a 10% retry budget, 200 without")
        else:
            assert attempts[0] == 200


# --- Milestone 3 ---------------------------------------------------------------------
def m3():
    # Scripted outage: healthy until t=10, failing 10..30, healthy again. One call per second.
    c = FakeClock()
    dep = FlakyDependency(c, [Phase(0, 0.0), Phase(10, 0.0, "transient"), Phase(30, 0.0)])
    br = mod.CircuitBreaker(c, window=10.0, min_calls=5, failure_rate=0.5, open_duration=5.0, half_open_max=2)
    assert br.state == "closed"
    log = []
    for t in range(60):
        c.sleep(max(0.0, t - c.now()))
        try:
            br.call(dep.call)
            log.append((t, "ok"))
        except mod.CircuitOpenError:
            log.append((t, "short"))
        except mod.TransientError:
            log.append((t, "fail"))
    expected = [(14, "closed", "open"), (19, "open", "half-open"), (19, "half-open", "open"),
                (24, "open", "half-open"), (24, "half-open", "open"), (29, "open", "half-open"),
                (29, "half-open", "open"), (34, "open", "half-open"), (35, "half-open", "closed")]
    got = [(round(t, 6), a, b) for t, a, b in br.transitions]
    assert got == expected, ("state transitions differ.\n      expected (time, from, to):\n        " + "\n        ".join(map(str, expected))
                             + "\n      got:\n        " + "\n        ".join(map(str, got)))
    arrivals = [int(t) for t in dep.arrivals]
    assert arrivals == list(range(0, 15)) + [19, 24, 29, 34, 35] + list(range(36, 60)), \
        f"while the breaker is open no call may reach the dependency. Calls reached it at t = {arrivals}"
    shorts = [t for t, r in log if r == "short"]
    assert shorts == [15, 16, 17, 18, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33], f"short-circuited at {shorts}"
    assert br.short_circuited == 16
    note("      outage 10..30: closed->open at t=14, probes fail at 19/24/29, probes succeed at 34/35, closed at 35; 16 calls short-circuited")

    # Limited half-open probes, driven through before_call/on_success/on_failure.
    c = FakeClock()
    br = mod.CircuitBreaker(c, window=10.0, min_calls=5, failure_rate=0.5, open_duration=5.0, half_open_max=2)
    for _ in range(5):
        br.before_call()
        br.on_failure()
    assert br.state == "open", "5 failures out of 5 calls in the window must open the circuit"
    raises(mod.CircuitOpenError, br.before_call, "an open circuit refuses calls")
    c.sleep(4.9)
    assert br.state == "open", "still open 4.9 s later"
    c.sleep(0.2)
    assert br.state == "half-open", "5 s after opening the circuit goes half-open"
    br.before_call()
    br.before_call()
    raises(mod.CircuitOpenError, br.before_call, "half_open_max=2: a third probe while two are undecided must be refused")
    br.on_success()
    assert br.state == "half-open", "one successful probe is not enough"
    br.on_success()
    assert br.state == "closed", "all probes succeeded: closed again"
    assert br.window_counts() == (0, 0), "a closed-again breaker starts with a clean window"
    for _ in range(5):
        br.before_call()
        br.on_failure()
    c.sleep(5)
    assert br.state == "half-open"
    br.before_call()
    br.on_failure()
    assert br.state == "open", "one failed probe re-opens the circuit"
    c.sleep(4.0)
    assert br.state == "open", "and the full open_duration starts again from the failed probe"
    c.sleep(1.0)
    assert br.state == "half-open"

    # What does not trip it.
    c = FakeClock()
    br = mod.CircuitBreaker(c, window=5.0, min_calls=5, failure_rate=0.5, open_duration=5.0, half_open_max=2)
    for _ in range(4):
        raises(mod.TransientError, lambda: br.call(lambda: (_ for _ in ()).throw(mod.TransientError())), "errors pass through")
    assert br.state == "closed", "4 failures is below min_calls=5: not enough evidence"
    c.sleep(6)                                              # the 4 failures leave the 5 s window
    raises(mod.TransientError, lambda: br.call(lambda: (_ for _ in ()).throw(mod.TransientError())), "errors pass through")
    assert br.state == "closed" and br.window_counts() == (1, 1), "failures older than the window must be forgotten"
    for _ in range(30):
        raises(mod.PermanentError, lambda: br.call(lambda: (_ for _ in ()).throw(mod.PermanentError())), "errors pass through")
    assert br.state == "closed", "400-style errors say the dependency is alive: they must not open the circuit"
    br2 = mod.CircuitBreaker(c, window=5.0, min_calls=5, failure_rate=0.5)
    for i in range(12):
        try:
            br2.call(lambda: (_ for _ in ()).throw(mod.TransientError()) if i % 3 == 0 else "ok")
        except mod.TransientError:
            pass
    assert br2.state == "closed", "1 failure in 3 calls (33%) is below the 50% threshold"


# --- Milestone 4 ---------------------------------------------------------------------
def m4():
    b = mod.Bulkhead(3, name="payments")
    for _ in range(3):
        b.acquire()
    assert b.in_flight == 3
    raises(mod.BulkheadFullError, b.acquire, "a 4th concurrent call must be rejected at once, not queued")
    assert b.in_flight == 3 and b.rejected == 1, f"a rejection must not change in_flight (got {b.in_flight}) and must be counted (rejected={b.rejected})"
    assert issubclass(mod.BulkheadFullError, mod.RejectedError)
    b.release()
    b.acquire()                                             # a slot freed up
    for _ in range(3):
        b.release()
    assert b.in_flight == 0
    raises(RuntimeError, b.release, "releasing a slot nobody holds is a bug: raise RuntimeError")
    assert b.in_flight == 0

    assert b.call(lambda: "result") == "result" and b.in_flight == 0
    raises(ZeroDivisionError, lambda: b.call(lambda: 1 / 0), "errors pass through")
    assert b.in_flight == 0, "call() must release the slot even when the call raises"
    full = mod.Bulkhead(1)
    full.acquire()
    ran = []
    raises(mod.BulkheadFullError, lambda: full.call(lambda: ran.append(1)), "call() on a full bulkhead must reject")
    assert ran == [], "the function must not run when the bulkhead is full"
    assert full.in_flight == 1, "a rejected call() must not release somebody else's slot"

    # One bulkhead per dependency: a full one does not affect another.
    slow, other = mod.Bulkhead(2, "slow"), mod.Bulkhead(2, "other")
    slow.acquire()
    slow.acquire()
    raises(mod.BulkheadFullError, slow.acquire, "slow is full")
    other.acquire()
    other.release()

    # Real threads, released by events (no timing assumptions): 12 callers, 4 slots.
    bh = mod.Bulkhead(4, "threads")
    gate = threading.Event()
    inside = []
    out = {"ok": 0, "rejected": 0, "other": []}
    lock = threading.Lock()

    def worker():
        def work():
            with lock:
                inside.append(1)
            gate.wait(20)
            return "done"
        try:
            bh.call(work)
            with lock:
                out["ok"] += 1
        except mod.BulkheadFullError:
            with lock:
                out["rejected"] += 1
        except Exception as e:
            with lock:
                out["other"].append(e)
            if isinstance(e, NotImplementedError):
                gate.set()

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(12)]
    for t in ts:
        t.start()
    deadline = time.monotonic() + 15
    try:
        while time.monotonic() < deadline:
            with lock:
                settled = out["rejected"] + len(inside) + len(out["other"])
            if settled >= 12:
                break
            time.sleep(0.005)
        with lock:
            others = list(out["other"])
        for e in others:
            if isinstance(e, NotImplementedError):
                raise e
        assert not others, f"a worker crashed: {others[0]!r}"
        assert len(inside) == 4 and bh.in_flight == 4, f"exactly 4 calls should be inside the bulkhead, saw {len(inside)} (in_flight={bh.in_flight})"
        assert out["rejected"] == 8, f"the other 8 must be rejected immediately, got {out['rejected']}"
    finally:
        gate.set()
        for t in ts:
            t.join(20)
    assert out["ok"] == 4 and bh.in_flight == 0, f"after the gate opens all 4 finish and the slots come back: ok={out['ok']} in_flight={bh.in_flight}"
    assert bh.max_seen <= 4, f"never more than 4 at once, saw {bh.max_seen}"
    note("      12 threads, 4 slots: 4 ran, 8 rejected instantly, slots returned after finishing")


# --- Milestone 5 ---------------------------------------------------------------------
def make_toolkit(phases, seed=1, **kw):
    c = FakeClock()
    dep = FlakyDependency(c, phases)
    return mod.Toolkit(c, random.Random(seed), **kw), dep, c


def m5():
    # Order matters, part 1: an open breaker is a rejection, and rejections are not retried or slept on.
    tk, dep, c = make_toolkit([Phase(0, 0.05)])
    tk.breaker._transition("open")
    raises(mod.CircuitOpenError, lambda: tk.call(dep.call), "with the circuit open the toolkit must raise CircuitOpenError")
    assert dep.calls == 0, "nothing may reach the dependency while the circuit is open"
    assert c.sleeps == [], "a rejection must not be retried: no backoff sleep"
    assert tk.breaker.short_circuited == 1, f"the breaker must be asked exactly once, saw {tk.breaker.short_circuited} short-circuits"

    # Part 2: a full bulkhead rejects before the breaker is even consulted, so it cannot be mistaken for a dependency failure.
    tk, dep, c = make_toolkit([Phase(0, 0.05)], bulkhead=mod.Bulkhead(2))
    tk.bulkhead.acquire()
    tk.bulkhead.acquire()
    raises(mod.BulkheadFullError, lambda: tk.call(dep.call), "with a full bulkhead the toolkit must raise BulkheadFullError")
    assert dep.calls == 0 and c.sleeps == [], "no call, no retry"
    assert tk.breaker.window_counts() == (0, 0), "a bulkhead rejection must not be recorded as a failure by the breaker (put the bulkhead outside the breaker)"

    # Part 3: timeouts are enforced and retried; each attempt gets a fresh timeout.
    tk, dep, c = make_toolkit([Phase(0, 2.0), Phase(1.0, 0.05)], timeout=0.5)
    assert tk.call(dep.call) == "ok", "slow, slow, then healthy: the third attempt should succeed"
    assert dep.calls == 3, f"expected 3 attempts (two timeouts, then success), got {dep.calls}"
    assert tk.bulkhead.in_flight == 0, "the bulkhead slot must be released after every attempt"

    # Part 4: permanent errors are not retried and do not count against the dependency.
    tk, dep, c = make_toolkit([Phase(0, 0.05, "permanent")])
    raises(mod.PermanentError, lambda: tk.call(dep.call), "a 400 must reach the caller")
    assert dep.calls == 1 and c.sleeps == [0.05], "a 400 is never retried (one call, no backoff sleep)"
    assert tk.breaker.window_counts() == (1, 0), f"a 400 must not count as a failure, window = {tk.breaker.window_counts()}"

    # Part 5: a hopeless dependency costs at most max_attempts calls per request.
    tk, dep, c = make_toolkit([Phase(0, 0.05, "transient")])
    raises(mod.TransientError, lambda: tk.call(dep.call), "the 503 reaches the caller after the attempts are used up")
    assert dep.calls == tk.policy.max_attempts == 3

    # The scenario: 60 s, one request every 0.5 s, dependency down from t=10 to t=40.
    rows = {}
    for seed in (1, 2, 3, 4, 5):
        naive = mod.run_scenario("naive", seed)
        tool = mod.run_scenario("toolkit", seed)
        rows[seed] = (naive, tool)
        assert tool["calls_to_dependency"] * 4 < naive["calls_to_dependency"], \
            (f"seed {seed}: the toolkit sent {tool['calls_to_dependency']} calls to the failing dependency, naive retries sent "
             f"{naive['calls_to_dependency']}. Expect the toolkit to send less than a quarter.")
        assert tool["ok"] > naive["ok"], f"seed {seed}: the toolkit should serve more requests successfully ({tool['ok']} vs {naive['ok']})"
        assert tool["recovery_seconds"] is not None and tool["recovery_seconds"] <= 15, \
            f"seed {seed}: the toolkit should be serving again within 15 s of the outage ending, got {tool['recovery_seconds']}"
        assert naive["recovery_seconds"] is None or naive["recovery_seconds"] > tool["recovery_seconds"] + 10, \
            f"seed {seed}: naive retries should recover much later than the toolkit"
    naive, tool = rows[1]
    again = mod.run_scenario("toolkit", 1)
    assert {k: v for k, v in again.items() if k != "toolkit"} == {k: v for k, v in tool.items() if k != "toolkit"}, "the scenario must be deterministic"
    br = tool["toolkit"].breaker
    assert any(a == "closed" and b == "open" for _, a, b in br.transitions) and br.state == "closed", "the breaker should trip during the outage and be closed again at the end"
    assert br.short_circuited > 0
    rec = naive["recovery_seconds"]
    note(f"      naive retries: {naive['calls_to_dependency']} calls to the dependency, {naive['ok']} requests served, "
         f"recovery {'never (the retries kept it overloaded)' if rec is None else '%.1f s' % rec}")
    note(f"      toolkit:       {tool['calls_to_dependency']} calls to the dependency, {tool['ok']} requests served, "
         f"{tool['rejected']} rejected fast, recovery {tool['recovery_seconds']:.1f} s after the outage ended")


print(f"Lab 6 checks against {target}.py\n")
check("Milestone 1: timeouts in simulated time", m1)
check("Milestone 2: retries with backoff, jitter and a budget", m2)
check("Milestone 3: the circuit breaker", m3)
check("Milestone 4: the bulkhead", m4)
check("Milestone 5: composing the toolkit", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
