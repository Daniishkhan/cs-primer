"""Self-check for Lab 3.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Every milestone runs in a daemon thread with a time limit, so a deadlock in YOUR code
shows up as a failure message instead of a frozen terminal.
Prints ✔ / ✘ / … (not implemented yet).
"""
import importlib
import os
import queue
import random
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
        print(f"  ✘ {name}: still running after {limit} s (is something deadlocked or waiting forever?)")
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
    assert not stuck, f"{stuck} of the {what} were still running after {limit} s (deadlock or lost wakeup?)"


def hammer(counter, n_threads, n_incr):
    def work():
        for _ in range(n_incr):
            counter.increment()
    ts = [spawn(work) for _ in range(n_threads)]
    join_all(ts, 30, "counter threads")
    return counter.value


# --- Milestone 1 ---------------------------------------------------------------------

def m1():
    lost_runs = 0
    worst = 0
    for seed in range(5):
        rng = random.Random(seed)
        n_threads, n_incr = rng.randint(4, 8), rng.randint(500, 1000)
        expected = n_threads * n_incr
        got = hammer(mod.UnsafeCounter(), n_threads, n_incr)
        assert got <= expected, f"counter went ABOVE {expected} (got {got}); updates can only be lost, not invented"
        assert got >= 1, "the counter never moved; does increment() write the value back?"
        if got < expected:
            lost_runs += 1
            worst = max(worst, expected - got)
    assert lost_runs >= 1, ("5 runs and not a single lost update. Is increment() really "
                            "read, then time.sleep(0), then write, with no lock?")
    return f"{lost_runs}/5 runs lost updates; worst run lost {worst}"


# --- Milestone 2 ---------------------------------------------------------------------

def m2():
    for seed in range(5):
        rng = random.Random(seed)
        n_threads, n_incr = rng.randint(4, 8), rng.randint(300, 600)
        got = hammer(mod.SafeCounter(), n_threads, n_incr)
        assert got == n_threads * n_incr, (f"run {seed}: expected {n_threads * n_incr}, got {got}; "
                                           "the read-sleep-write must all happen inside the lock")


# --- Milestone 3 ---------------------------------------------------------------------

def two_way_transfer(fn, pause, timeout):
    """Thread 1 sends A->B while thread 2 sends B->A. Returns (a, b, outcomes)."""
    a, b = mod.Account(1, 100), mod.Account(2, 100)
    outcomes = {}

    def go(name, x, y):
        try:
            outcomes[name] = fn(x, y, 10, pause=pause, timeout=timeout)
        except mod.LockTimeout:
            outcomes[name] = "timeout"

    ts = [spawn(go, "t1", a, b), spawn(go, "t2", b, a)]
    join_all(ts, timeout + pause + 8, "transfer threads")
    return a, b, outcomes


def m3():
    # (a) the naive version must deadlock, which we notice because acquire() times out
    a, b, out = two_way_transfer(mod.transfer_naive, pause=0.3, timeout=1.0)
    assert "timeout" in out.values(), (
        f"expected at least one LockTimeout from the opposite-order transfers, got {out}. "
        "Does transfer_naive lock src first and dst second, with the pause in between?")
    assert not a.lock.locked() and not b.lock.locked(), \
        "a lock was never released after the timeout: release in `finally:` blocks"
    assert a.balance + b.balance == 200, f"money not conserved after timeouts: {a.balance + b.balance}"

    # (b) the ordered version survives the exact same opposite-order transfers
    a, b, out = two_way_transfer(mod.transfer_ordered, pause=0.3, timeout=5.0)
    assert out == {"t1": True, "t2": True}, f"ordered transfers should both succeed, got {out}"
    assert (a.balance, b.balance) == (100, 100), f"balances should end at 100/100, got {a.balance}/{b.balance}"

    # (c) thousands of random transfers among several threads: no hang, no money created or lost
    rng = random.Random(7)
    accounts = [mod.Account(i, 1000) for i in range(6)]
    n_threads, n_each = 8, 2500
    done = []
    timeouts = []

    def worker(seed):
        r = random.Random(seed)
        for _ in range(n_each):
            src, dst = r.sample(accounts, 2)
            try:
                mod.transfer_ordered(src, dst, r.randint(1, 60), timeout=10.0)
            except mod.LockTimeout:
                timeouts.append(1)
                return
        done.append(1)

    ts = [spawn(worker, rng.randrange(10 ** 6)) for _ in range(n_threads)]
    join_all(ts, 40, "transfer threads")
    assert not timeouts, "a transfer timed out among random transfers: that is a deadlock"
    assert len(done) == n_threads, "some transfer threads did not finish"
    total = sum(x.balance for x in accounts)
    assert total == 6000, f"total money should stay 6000, got {total}"
    assert all(x.balance >= 0 for x in accounts), "an account went negative"
    assert not any(x.lock.locked() for x in accounts), "a lock was left locked"
    return f"{n_threads * n_each:,} transfers, total still {total}"


# --- Milestone 4 ---------------------------------------------------------------------

def m4():
    q = mod.BoundedQueue(3)
    for i in range(3):
        q.put(i, timeout=1)
    assert q.qsize() == 3, f"qsize should be 3, got {q.qsize()}"
    t = time.monotonic()
    try:
        q.put("overflow", timeout=0.3)
    except queue.Full:
        pass
    else:
        raise AssertionError("put() into a full queue should raise queue.Full after the timeout")
    assert 0.1 <= time.monotonic() - t < 5, "put(timeout=0.3) should wait about 0.3 s before raising Full"
    assert [q.get(timeout=1) for _ in range(3)] == [0, 1, 2], "items must come out in FIFO order"
    t = time.monotonic()
    try:
        q.get(timeout=0.3)
    except queue.Empty:
        pass
    else:
        raise AssertionError("get() from an empty queue should raise queue.Empty after the timeout")
    assert 0.1 <= time.monotonic() - t < 5, "get(timeout=0.3) should wait about 0.3 s before raising Empty"

    # a blocked put() wakes up when a consumer makes room
    q = mod.BoundedQueue(1)
    q.put("first")
    blocked = spawn(lambda: q.put("second", timeout=10))
    time.sleep(0.3)
    assert blocked.is_alive(), "put() on a full queue returned without waiting"
    assert q.get(timeout=1) == "first"
    join_all([blocked], 5, "blocked put")
    assert q.get(timeout=1) == "second"

    # three consumers are waiting, one item arrives: exactly one may take it (needs the while loop)
    q = mod.BoundedQueue(5)
    got, errors = [], []

    def consumer():
        try:
            got.append(q.get(timeout=1.5))
        except queue.Empty:
            pass
        except BaseException as e:
            errors.append(e)

    ts = [spawn(consumer) for _ in range(3)]
    time.sleep(0.3)
    q.put("only-one")
    join_all(ts, 10, "consumers")
    assert not errors, f"a consumer crashed with {errors[0]!r}: re-check the condition in a `while` loop after waking"
    assert got == ["only-one"], f"exactly one consumer should get the single item, got {got}"

    # producers and consumers hammering a small queue
    q = mod.BoundedQueue(4)
    n_prod, n_cons, per = 4, 3, 400
    consumed = []
    clock = threading.Lock()
    peak = [0]
    stop_monitor = threading.Event()

    def producer(pid):
        for i in range(per):
            q.put((pid, i), timeout=20)

    def cons():
        mine = []
        while True:
            item = q.get(timeout=20)
            if item is None:
                break
            mine.append(item)
        with clock:
            consumed.extend(mine)

    def monitor():
        while not stop_monitor.is_set():
            peak[0] = max(peak[0], q.qsize())
            time.sleep(0.0005)

    spawn(monitor)
    cs = [spawn(cons) for _ in range(n_cons)]
    ps = [spawn(producer, p) for p in range(n_prod)]
    join_all(ps, 30, "producers")
    for _ in range(n_cons):
        q.put(None, timeout=20)              # one "stop" marker per consumer
    join_all(cs, 30, "consumers")
    stop_monitor.set()
    expected = {(p, i) for p in range(n_prod) for i in range(per)}
    assert len(consumed) == len(expected), f"expected {len(expected)} items, consumers got {len(consumed)}"
    assert set(consumed) == expected and len(set(consumed)) == len(consumed), "items were lost or duplicated"
    assert peak[0] <= 4, f"queue held {peak[0]} items but the bound is 4"
    return f"{len(consumed)} items through a queue of 4, peak size {peak[0]}"


# --- Milestone 5 (optional) ----------------------------------------------------------

def race_for_seat(method, seat, n=8):
    seats = mod.SeatMap()
    barrier = threading.Barrier(n, timeout=10)
    wins = []

    def go(i):
        barrier.wait()
        if getattr(seats, method)(seat, f"user{i}"):
            wins.append(i)

    join_all([spawn(go, i) for i in range(n)], 15, "booking threads")
    return seats, wins


def m5():
    # the given buggy version double-books (this part runs even before you start)
    double = 0
    for r in range(10):
        _, wins = race_for_seat("reserve_unsafe", r)
        double += len(wins) > 1
    assert double >= 1, "expected reserve_unsafe to double-book at least once in 10 rounds"
    # your version never does
    for r in range(20):
        seats, wins = race_for_seat("reserve", r)
        assert len(wins) == 1, f"round {r}: {len(wins)} threads were told they got seat {r}; exactly 1 may win"
        assert seats.owner(r) == f"user{wins[0]}", "the seat's owner must be the one thread that was told True"
    return f"unsafe version double-booked in {double}/10 rounds; yours in 0/20"


print(f"Lab 3 checks against {target}.py\n")
check("Milestone 1: make a lost update happen", m1)
check("Milestone 2: fix the counter with a lock", m2)
check("Milestone 3: bank transfers, deadlock and lock ordering", m3, limit=55)
check("Milestone 4: BoundedQueue from a Condition", m4)
check("Milestone 5 (optional): check-then-act seat reservation", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.stdout.flush()
os._exit(0 if passed == len(results) else 1)     # daemon threads may still be stuck; don't wait for them
