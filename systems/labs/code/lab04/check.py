"""Self-check for Lab 4.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Every milestone runs in a daemon thread with a time limit, so a bug that blocks forever
shows up as a failure message instead of a frozen terminal.
Prints ✔ / ✘ / … (not implemented yet).
"""
import importlib
import os
import sys
import threading
import time

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
thread_errors = []      # exceptions that escaped from threads


def _hook(args):
    thread_errors.append(args.exc_value)


threading.excepthook = _hook


class NotStarted(Exception):
    pass


def check(name, fn, limit=45):
    thread_errors.clear()
    box = {}

    def run():
        try:
            box["note"] = fn()
        except BaseException as e:          # report everything, including NotImplementedError
            box["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(limit)
    err = box.get("error")
    for e in [err] + thread_errors:         # "not implemented" in any thread wins over follow-on failures
        if isinstance(e, (NotImplementedError, NotStarted)):
            err = e
            break
    if t.is_alive():
        print(f"  ✘ {name}: still running after {limit} s (is something blocked forever?)")
        results.append(False)
    elif err is None and not thread_errors:
        note = f"  ({box['note']})" if box.get("note") else ""
        print(f"  ✔ {name}{note}")
        results.append(True)
    else:
        inner = err if err is not None else thread_errors[0]
        if isinstance(inner, (NotImplementedError, NotStarted)):
            print(f"  … {name}: not implemented yet ({inner})")
        elif isinstance(inner, AssertionError):
            print(f"  ✘ {name}: {inner}")
        else:
            print(f"  ✘ {name}: {type(inner).__name__}: {inner}")
        results.append(False)


def spawn(fn, *args):
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()
    return t


def join_all(threads, limit, what="threads"):
    deadline = time.monotonic() + limit
    for t in threads:
        t.join(max(0.0, deadline - time.monotonic()))
    stuck = sum(t.is_alive() for t in threads)
    assert not stuck, f"{stuck} of the {what} were still running after {limit} s"


def quiet_shutdown(pool):
    """Best-effort cleanup that never raises or blocks (workers are daemon threads anyway)."""
    try:
        pool.shutdown(wait=False)
    except Exception:
        pass


def raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type as e:
        return e
    except NotImplementedError:
        raise
    except BaseException as e:
        raise AssertionError(f"expected {exc_type.__name__}, got {type(e).__name__}: {e}")
    raise AssertionError(f"expected {exc_type.__name__}, but nothing was raised")


# --- Milestone 1 ---------------------------------------------------------------------

def m1():
    f = mod.Future()
    assert f.done() is False, "a new Future must not be done"
    t = time.monotonic()
    raises(TimeoutError, f.result, timeout=0.3)
    assert 0.1 <= time.monotonic() - t < 5, "result(timeout=0.3) should wait about 0.3 s, then raise TimeoutError"
    assert f.done() is False, "a timed-out result() must not mark the Future done"

    got = []
    waiters = [spawn(lambda: got.append(f.result(timeout=10))) for _ in range(3)]
    time.sleep(0.2)
    assert not got, "result() returned before set_result was called"
    f.set_result(42)
    join_all(waiters, 5, "waiting threads")
    assert got == [42, 42, 42], f"all three waiters should get 42, got {got} (notify_all, not notify)"
    assert f.done() is True
    t = time.monotonic()
    assert f.result(timeout=0) == 42, "result() on a finished Future returns immediately"
    assert time.monotonic() - t < 1

    g = mod.Future()
    err = ValueError("boom")
    spawn(lambda: (time.sleep(0.1), g.set_exception(err)))
    caught = raises(ValueError, g.result, timeout=10)
    assert caught is err, "result() should re-raise the very exception that was set"
    assert g.done() is True


# --- Milestone 2 ---------------------------------------------------------------------

def m2():
    pool = mod.ThreadPool(3)
    try:
        assert len(pool.threads) == 3 and all(t.daemon for t in pool.threads), \
            "pool.threads should be a list of 3 daemon threads"
        futs = [pool.submit(pow, i, 2) for i in range(20)]
        assert [f.result(timeout=10) for f in futs] == [i * i for i in range(20)], "wrong results"

        # three tasks that can only finish if three workers run AT THE SAME TIME
        barrier = threading.Barrier(3, timeout=5)
        futs = [pool.submit(barrier.wait) for _ in range(3)]
        for f in futs:
            f.result(timeout=10)                 # BrokenBarrierError here means fewer than 3 ran at once

        # exceptions travel to result(), and the worker survives
        bad = pool.submit(lambda: 1 / 0)
        raises(ZeroDivisionError, bad.result, timeout=10)
        later = [pool.submit(lambda i=i: i + 100) for i in range(10)]
        assert [f.result(timeout=10) for f in later] == list(range(100, 110)), "workers died after a failing task"
        assert all(t.is_alive() for t in pool.threads), "a failing task killed a worker thread"

        # submit passes positional arguments
        assert pool.submit(max, 3, 9, 4).result(timeout=10) == 9
    finally:
        quiet_shutdown(pool)


# --- Milestone 3 ---------------------------------------------------------------------

def m3():
    done = []
    pool = mod.ThreadPool(2)
    futs = [pool.submit(lambda i=i: (time.sleep(0.02), done.append(i))) for i in range(20)]
    stopper = spawn(pool.shutdown, True)
    join_all([stopper], 20, "shutdown call")
    assert len(done) == 20, f"shutdown(wait=True) returned with only {len(done)} of 20 queued tasks finished"
    assert all(f.done() for f in futs)
    assert not any(t.is_alive() for t in pool.threads), "all workers must have exited after shutdown(wait=True)"
    raises(RuntimeError, pool.submit, len, "abc")
    pool.shutdown()                                   # a second call is harmless

    # wait=False returns at once; queued work still finishes; then every worker exits
    gate, started, ran = threading.Event(), threading.Event(), []
    pool = mod.ThreadPool(2)
    try:
        for _ in range(2):
            pool.submit(lambda: (started.set(), gate.wait(10)))
        assert started.wait(5)
        for i in range(5):
            pool.submit(ran.append, i)
        t = time.monotonic()
        pool.shutdown(wait=False)
        assert time.monotonic() - t < 2, "shutdown(wait=False) must not wait for the workers"
        assert not ran, "queued tasks should not run before the gate opens"
        gate.set()
        join_all(pool.threads, 10, "worker threads")
        assert sorted(ran) == list(range(5)), f"queued work must finish before workers stop, got {ran}"
    finally:
        gate.set()
        quiet_shutdown(pool)


# --- Milestone 4 ---------------------------------------------------------------------

def saturated_pool(policy):
    """1 worker busy on a task that waits for `gate`, plus a full queue of 2. Next submit overflows."""
    gate, started = threading.Event(), threading.Event()
    pool = mod.ThreadPool(1, max_queue=2, policy=policy)
    first = pool.submit(lambda: (started.set(), gate.wait(10), "first")[2])
    assert started.wait(5), "the first task never started"
    queued = [pool.submit(lambda i=i: f"queued{i}") for i in range(2)]
    return pool, gate, [first] + queued


def m4():
    raises(ValueError, mod.ThreadPool, 1, 1, "explode")

    # reject: instant Rejected, counted
    pool, gate, accepted = saturated_pool("reject")
    try:
        t = time.monotonic()
        raises(mod.Rejected, pool.submit, lambda: "overflow")
        assert time.monotonic() - t < 2, "policy 'reject' must refuse immediately, not wait"
        assert pool.rejected == 1, f"pool.rejected should be 1, got {pool.rejected}"
        gate.set()
        assert [f.result(timeout=10) for f in accepted] == ["first", "queued0", "queued1"]
    finally:
        gate.set()
        quiet_shutdown(pool)

    # caller_runs: the producer does the work itself
    pool, gate, accepted = saturated_pool("caller_runs")
    try:
        ran_in = []
        f = pool.submit(lambda: ran_in.append(threading.current_thread()) or "mine")
        assert ran_in == [threading.current_thread()], "policy 'caller_runs' should run the task in the submitting thread"
        assert f.done() and f.result(timeout=0) == "mine", "the returned Future should already be finished"
        assert pool.caller_ran == 1, f"pool.caller_ran should be 1, got {pool.caller_ran}"
        gate.set()
        assert [x.result(timeout=10) for x in accepted] == ["first", "queued0", "queued1"]
    finally:
        gate.set()
        quiet_shutdown(pool)

    # block: the producer is stuck until room appears
    pool, gate, accepted = saturated_pool("block")
    try:
        box = {}
        producer = spawn(lambda: box.setdefault("f", pool.submit(lambda: "late")))
        time.sleep(0.4)
        assert producer.is_alive(), "policy 'block' should make submit() wait while the queue is full"
        gate.set()
        join_all([producer], 10, "blocked producer")
        assert box["f"].result(timeout=10) == "late"
        assert [x.result(timeout=10) for x in accepted] == ["first", "queued0", "queued1"]
    finally:
        gate.set()
        quiet_shutdown(pool)

    # max_queue=0 means unbounded: nothing is ever rejected
    gate = threading.Event()
    pool = mod.ThreadPool(1, max_queue=0, policy="reject")
    try:
        for _ in range(50):
            pool.submit(gate.wait, 10)
        assert pool.rejected == 0
    finally:
        gate.set()
        quiet_shutdown(pool)


# --- Milestone 5 ---------------------------------------------------------------------

def m5():
    workers, svc, n = 4, 0.02, 400
    capacity = workers / svc
    rows = {}
    for label, util, kw in (("50% load", 0.5, {}), ("95% load", 0.95, {}),
                            ("200% load, reject", 2.0, {"max_queue": 5, "policy": "reject"})):
        r = mod.run_load(util * capacity, n, svc, workers, seed=int(util * 100), **kw)
        for key in ("submitted", "completed", "rejected", "avg", "p95", "L", "lambda_W", "throughput"):
            assert key in r, f"run_load's result is missing the key {key!r}"
        rows[label] = r
    print(f"      {workers} workers x {svc * 1000:.0f} ms tasks -> capacity {capacity:.0f} tasks/s")
    print("      %-22s %8s %8s %9s %7s %6s" % ("scenario", "avg ms", "p95 ms", "L (meas)", "lam*W", "rej"))
    for label, r in rows.items():
        print("      %-22s %8.1f %8.1f %9.2f %7.2f %6d" % (
            label, r["avg"] * 1000, r["p95"] * 1000, r["L"], r["lambda_W"], r["rejected"]))
    lo, hi, over = rows["50% load"], rows["95% load"], rows["200% load, reject"]
    assert lo["completed"] == n and hi["completed"] == n, "with an unbounded queue every task must complete"
    assert lo["avg"] >= svc * 0.8, "a task cannot finish faster than its service time; is the latency measured from ARRIVAL?"
    assert hi["avg"] > lo["avg"], (f"latency at 95% load ({hi['avg'] * 1000:.0f} ms) should be higher than "
                                   f"at 50% ({lo['avg'] * 1000:.0f} ms): that is the knee")
    assert over["rejected"] > 0, "at twice the capacity with policy 'reject' some submits must be rejected"
    assert over["completed"] + over["rejected"] == n, "every task must be either completed or rejected"
    return f"latency at 95% load is {hi['avg'] / lo['avg']:.1f}x the latency at 50%"


# --- Milestone 6 (optional) ----------------------------------------------------------

def m6():
    gate, started, ran = threading.Event(), threading.Event(), []
    pool = mod.ThreadPool(1)
    try:
        pool.submit(lambda: (started.set(), gate.wait(10)))
        assert started.wait(5)
        soon = [pool.submit(ran.append, i, deadline=time.monotonic() + 0.1) for i in range(5)]
        no_deadline = pool.submit(lambda: "no deadline")
        far = pool.submit(lambda: "far", deadline=time.monotonic() + 60)
        time.sleep(0.4)                              # by now the five short deadlines have passed
        gate.set()
        for f in soon:
            raises(mod.DeadlineExceeded, f.result, timeout=10)
        assert not ran, f"expired tasks must not run, but these did: {ran}"
        assert no_deadline.result(timeout=10) == "no deadline"
        assert far.result(timeout=10) == "far"
        assert pool.expired == 5, f"pool.expired should be 5, got {pool.expired}"
    finally:
        gate.set()
        quiet_shutdown(pool)


print(f"Lab 4 checks against {target}.py\n")
check("Milestone 1: Future", m1)
check("Milestone 2: ThreadPool with submit() and exceptions", m2)
check("Milestone 3: graceful shutdown with poison pills", m3)
check("Milestone 4: bounded queue and rejection policies", m4)
check("Milestone 5: measuring latency under load", m5, limit=55)
check("Milestone 6 (optional): deadlines", m6)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.stdout.flush()
os._exit(0 if passed == len(results) else 1)     # daemon threads may still be blocked; don't wait for them
