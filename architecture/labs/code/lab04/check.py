"""Self-check for Lab 4: A Saga Orchestrator.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Everything is in-process: fake services, a sqlite file in a temp folder, seeded randomness.
No network, no threads, no timing: the same result every run, a few seconds at most.
Prints a tick, a cross, or "not implemented yet" for each milestone. Milestone 5 is optional.
"""
import importlib
import os
import random
import shutil
import signal
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
if target not in ("starter", "solution"):
    sys.exit("usage: python3 check.py [starter|solution]")
mod = importlib.import_module(target)

DATA = {"sku": "widget", "qty": 2, "account": "ana", "amount": 5000, "address": "1 Main St"}
OPS = ["inventory.reserve", "payments.charge", "courier.book"]            # the three actions, in order
COMP_OPS = ["courier.cancel", "payments.refund", "inventory.release"]     # their compensations (cancel is never needed)
STEP_NAMES = ["reserve stock", "charge payment", "book courier"]
results = []
notes = []
tmpdirs = []


def note(text):
    notes.append(text)


class Slow(Exception):
    pass


def _alarm(signum, frame):
    raise AssertionError("this took more than 20 seconds: is a loop in your orchestrator never ending?")


def check(name, fn):
    del notes[:]
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(20)
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
    except mod.Crash as e:
        print(f"  ✘ {name}: the simulated crash escaped: {e}")
        results.append(False)
    except Exception as e:
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
    for line in notes:
        print(line)


class World:
    """Fresh services plus a sqlite file. new_orch() simulates 'start the process again'."""

    def __init__(self, stock=10, balance=20000):
        self.dir = tempfile.mkdtemp(prefix="lab4-")
        tmpdirs.append(self.dir)
        self.path = os.path.join(self.dir, "sagas.db")
        self.faults = mod.Faults()
        self.inv = mod.Inventory(self.faults, stock=stock)
        self.pay = mod.Payments(self.faults, {"ana": balance})
        self.cou = mod.Courier(self.faults)
        self.stock, self.balance = stock, balance
        self.services = {"inventory": self.inv, "payments": self.pay, "courier": self.cou}
        self.orch = self.new_orch()

    def new_orch(self):
        self.orch = mod.Orchestrator(self.path, self.services, mod.default_steps())
        return self.orch

    def expect(self, completed, why=""):
        """Final state of the services if `completed` sagas finished and every other one was undone."""
        n = completed
        pre = f"{why}: " if why else ""
        assert self.inv.available == self.stock - 2 * n and self.inv.held == 2 * n, \
            f"{pre}inventory should have {self.stock - 2 * n} available and {2 * n} held, has {self.inv.available} and {self.inv.held}"
        assert self.pay.balance["ana"] == self.balance - 5000 * n, \
            f"{pre}ana's balance should be {self.balance - 5000 * n}, it is {self.pay.balance['ana']}"
        assert self.cou.active() == n, f"{pre}courier should have {n} active booking(s), has {self.cou.active()}"
        for svc in self.services.values():
            dups = sorted({a for a in svc.applied if svc.applied.count(a) > 1})
            assert not dups, f"{pre}{svc.name} applied the same request twice: {dups}"


def hist(*events):
    return [(STEP_NAMES[i], phase, state) for i, phase, state in events]


# --- Milestone 1 ---------------------------------------------------------------------
def m1():
    w = World()
    assert w.orch.status("nope") is None, "status() of an unknown saga should be None"
    st = w.orch.run_saga("s1", DATA)
    assert st == "COMPLETED", f"run_saga should return 'COMPLETED' when every step works, got {st!r}"
    assert w.orch.status("s1") == "COMPLETED", "status('s1') should be COMPLETED"
    want = hist((0, "action", "DONE"), (1, "action", "DONE"), (2, "action", "DONE"))
    assert w.orch.history("s1") == want, f"history should be {want}, got {w.orch.history('s1')}"
    assert w.inv.deliveries == [("reserve", "s1:0")], f"inventory should get one reserve with key 's1:0', got {w.inv.deliveries}"
    assert w.pay.deliveries == [("charge", "s1:1")], f"payments should get one charge with key 's1:1', got {w.pay.deliveries}"
    assert w.cou.deliveries == [("book", "s1:2")], f"courier should get one book with key 's1:2', got {w.cou.deliveries}"
    w.expect(1, "after one saga")
    other = w.new_orch()                                     # a brand-new process reading the same file
    assert other.status("s1") == "COMPLETED" and other.history("s1") == want, \
        "a new Orchestrator on the same sqlite file should see the finished saga: the state must be in sqlite, not in memory"
    before = (list(w.inv.deliveries), list(w.pay.deliveries), list(w.cou.deliveries))
    assert other.run_saga("s1", DATA) == "COMPLETED", "run_saga on a finished saga should just return its status"
    assert (w.inv.deliveries, w.pay.deliveries, w.cou.deliveries) == before, "run_saga on a finished saga must not call any service again"
    assert other.run_saga("s2", DATA) == "COMPLETED"
    w.expect(2, "after two sagas")
    note("      history of s1: " + " > ".join(f"{n} {s}" for n, _, s in want))


# --- Milestone 2 ---------------------------------------------------------------------
def m2():
    for k in range(3):
        w = World()
        w.faults.add(OPS[k], "fail")
        st = w.orch.run_saga("s1", DATA)
        assert st == "COMPENSATED", f"step {k + 1} ({STEP_NAMES[k]}) fails: the saga should end COMPENSATED, got {st!r}"
        events = [(i, "action", "DONE") for i in range(k)] + [(k, "action", "FAILED")] \
            + [(i, "compensation", "DONE") for i in range(k - 1, -1, -1)]
        want = hist(*events)
        assert w.orch.history("s1") == want, (f"step {k + 1} fails. Expected history\n        {want}\n"
                                              f"      got\n        {w.orch.history('s1')}\n"
                                              "      (undo the finished steps in REVERSE order; the failed step is not undone)")
        w.expect(0, f"after the failure of step {k + 1}")
        assert w.orch.status("s1") == "COMPENSATED"
    w = World(stock=1)                                       # a real business failure: not enough stock
    assert w.orch.run_saga("s1", DATA) == "COMPENSATED" and w.orch.history("s1") == hist((0, "action", "FAILED")), \
        "with too little stock the first step fails and there is nothing to undo"
    w = World(balance=1000)                                  # card declined at step 2
    assert w.orch.run_saga("s1", DATA) == "COMPENSATED", "a declined card should compensate the stock reservation"
    w.expect(0, "after a declined card")
    w = World()                                              # compensations must be retried until they work
    w.faults.add("courier.book", "fail")
    w.faults.add("payments.refund", "fail", "fail")
    st = w.orch.run_saga("s1", DATA)
    assert st == "COMPENSATED", f"the refund fails twice and then works: retry compensations, got {st!r}"
    w.expect(0, "after refund retries")
    assert w.pay.deliveries.count(("refund", "s1:1")) == 1, "the two failed refunds never reached the service; only one refund should have"
    note("      failure injected at each of the 3 steps: no stock held, no money taken, no booking left")


# --- Milestone 3 ---------------------------------------------------------------------
def m3():
    w = World()
    p = w.pay
    first = p.call("charge", "k1", DATA)
    again = p.call("charge", "k1", DATA)
    assert p.balance["ana"] == 15000, f"the same charge key twice must debit once: balance is {p.balance['ana']}, should be 15000"
    assert first == again, "a repeated request should get the first answer back"
    p.call("charge", "k2", DATA)
    assert p.balance["ana"] == 10000, "a different key is a different charge"
    p.call("refund", "k1", DATA)
    p.call("refund", "k1", DATA)
    assert p.balance["ana"] == 15000, f"the same refund key twice must credit once: balance is {p.balance['ana']}, should be 15000"
    assert p.status("charge", "k1") == "DONE" and p.status("charge", "zz") == "NOT_DONE", "status() reports what handle() has stored"
    w = World()
    w.inv.call("reserve", "k", DATA); w.inv.call("reserve", "k", DATA)
    w.inv.call("release", "k", DATA); w.inv.call("release", "k", DATA)
    assert w.inv.available == 10 and w.inv.held == 0, f"reserve and release twice each: stock should be back to 10, is {w.inv.available}"
    w.cou.call("book", "k", DATA); w.cou.call("book", "k", DATA)
    w.cou.call("cancel", "k", DATA); w.cou.call("cancel", "k", DATA)
    assert w.cou.active() == 0 and len(w.cou.applied) == 2, "courier: book and cancel twice each should run each effect once"
    w = World()                                              # duplicates during a successful saga
    for op in OPS:
        w.faults.add(op, "dup")
    assert w.orch.run_saga("s1", DATA) == "COMPLETED"
    assert w.pay.deliveries.count(("charge", "s1:1")) == 2, "the fault should have delivered the charge twice"
    w.expect(1, "duplicate deliveries of every action")
    w = World()                                              # duplicates during compensation
    w.faults.add("courier.book", "fail")
    w.faults.add("payments.refund", "dup")
    w.faults.add("inventory.release", "dup")
    assert w.orch.run_saga("s1", DATA) == "COMPENSATED"
    w.expect(0, "duplicate refund and release")
    assert w.pay.deliveries == [("charge", "s1:1"), ("refund", "s1:1"), ("refund", "s1:1")], \
        f"the refund must carry the same key as the charge it undoes ('s1:1'), got {w.pay.deliveries}"
    assert w.inv.deliveries[0] == ("reserve", "s1:0") and ("release", "s1:0") in w.inv.deliveries, \
        f"the release must carry the key 's1:0', got {w.inv.deliveries}"
    note("      dedupe by (operation, key): no double charge, no double refund, no double release")


# --- Milestone 4 ---------------------------------------------------------------------
def crash_and_recover(w, saga_id="s1"):
    """Run the saga; whenever it 'dies', start a new process and recover. Return the restart count."""
    restarts = 0
    try:
        w.orch.run_saga(saga_id, DATA)
        return 0
    except mod.Crash:
        pass
    for _ in range(30):
        restarts += 1
        orch = w.new_orch()
        try:
            orch.recover()
            return restarts
        except mod.Crash:
            continue
    raise AssertionError("30 restarts and the saga is still crashing: recover() must make progress")


def m4():
    w = World()                                              # unknown outcome: the reply is lost
    w.faults.add("payments.charge", "timeout_after")
    assert w.orch.run_saga("s1", DATA) == "COMPLETED", "the charge happened but its reply was lost: ask the service, then carry on"
    assert w.pay.status_calls >= 1, "after a Timeout, ask service.status(op, key) before doing anything else"
    assert w.pay.deliveries == [("charge", "s1:1")], f"status said DONE, so do not send the charge again; deliveries: {w.pay.deliveries}"
    w.expect(1, "reply lost")
    w = World()                                              # unknown outcome: the request is lost
    w.faults.add("courier.book", "timeout_before")
    assert w.orch.run_saga("s1", DATA) == "COMPLETED", "the booking never arrived: status says NOT_DONE, so retry with the same key"
    assert w.cou.status_calls >= 1 and w.cou.deliveries == [("book", "s1:2")], "ask first; then retry once"
    w.expect(1, "request lost")
    w = World()                                              # a service that never answers
    w.faults.add("courier.book", *["timeout_before"] * 5)
    st = w.orch.run_saga("s1", DATA)
    assert st == "COMPENSATED", f"five timeouts in a row (MAX_ATTEMPTS): give up on the step and compensate, got {st!r}"
    w.expect(0, "courier never answered")
    for k, op in enumerate(OPS):                             # kill the orchestrator around every action
        for kind in ("crash_before", "crash_after"):
            w = World()
            w.faults.add(op, kind)
            restarts = crash_and_recover(w)
            assert restarts >= 1, f"{kind} at {op} should have killed the first orchestrator"
            assert w.orch.status("s1") == "COMPLETED", \
                f"{kind} at {op}: after a restart the saga should COMPLETE, got {w.orch.status('s1')!r}"
            w.expect(1, f"{kind} at {op}")
    for kind in ("crash_before", "crash_after"):             # kill it while compensating
        w = World()
        w.faults.add("courier.book", "fail")
        w.faults.add("payments.refund", kind)
        crash_and_recover(w)
        assert w.orch.status("s1") == "COMPENSATED", f"{kind} during the refund: the restarted saga should finish COMPENSATED, got {w.orch.status('s1')!r}"
        w.expect(0, f"{kind} during the refund")
    w = World()                                              # recover() has nothing to do on finished sagas
    w.orch.run_saga("s1", DATA)
    assert w.new_orch().recover() == [], "recover() should return [] when every saga is finished"
    # seeded chaos: random faults of every kind, random crashes, two sagas, many restarts
    kinds = ["fail", "timeout_before", "timeout_after", "dup", "crash_before", "crash_after", None]
    crashes = 0
    outcomes = {"COMPLETED": 0, "COMPENSATED": 0}
    for seed in range(80):
        rng = random.Random(seed)
        w = World()
        for op in OPS + COMP_OPS:
            w.faults.add(op, *[rng.choice(kinds) for _ in range(rng.choice([0, 0, 1, 2, 3]))])
        w.new_orch()
        restarts = 0
        for _ in range(60):
            try:
                if restarts:
                    w.orch.recover()
                for sid in ("o1", "o2"):
                    w.orch.run_saga(sid, DATA)
                break
            except mod.Crash:
                restarts += 1
                w.new_orch()
        else:
            raise AssertionError(f"seed {seed}: still crashing after 60 restarts")
        crashes += restarts
        statuses = [w.orch.status(s) for s in ("o1", "o2")]
        assert all(s in ("COMPLETED", "COMPENSATED") for s in statuses), f"seed {seed}: sagas ended as {statuses}, not finished"
        for s in statuses:
            outcomes[s] += 1
        w.expect(statuses.count("COMPLETED"), f"seed {seed} ({statuses}, {restarts} restarts)")
    note(f"      80 seeded runs, {crashes} simulated crashes, {outcomes['COMPLETED']} sagas completed, "
         f"{outcomes['COMPENSATED']} compensated, every one consistent")


# --- Milestone 5 (optional) ----------------------------------------------------------
def m5():
    w = World()
    assert w.orch.order_status("o1") is None, "an order that does not exist has status None"
    assert w.orch.cancel_order("o1") == "UNKNOWN_ORDER"
    seen = []
    w.faults.add("payments.charge", lambda: seen.append(w.orch.order_status("o1")))
    assert w.orch.run_saga("o1", DATA) == "COMPLETED"
    assert seen == ["PENDING"], f"while the saga runs the order must be PENDING, was {seen}"
    assert w.orch.order_status("o1") == "CONFIRMED", "a completed saga confirms the order"
    assert w.orch.cancel_order("o1") == "TOO_LATE", "cancelling a confirmed order is too late for this saga"
    w.expect(1, "a late cancel changes nothing")
    for k, op in enumerate(OPS):                             # a cancel request arrives while step k is running
        w = World()
        replies = []
        w.faults.add(op, lambda: replies.append(w.orch.cancel_order("o1")))  # returns None: no extra fault
        st = w.orch.run_saga("o1", DATA)
        assert replies == ["CANCEL_REQUESTED"], f"cancel during step {k + 1}: expected CANCEL_REQUESTED, got {replies}"
        assert st == "COMPENSATED" and w.orch.order_status("o1") == "CANCELLED", \
            f"cancel during step {k + 1}: the saga should end COMPENSATED and the order CANCELLED, got {st!r} / {w.orch.order_status('o1')!r}"
        w.expect(0, f"cancel during step {k + 1}")
        assert w.orch.cancel_order("o1") == "ALREADY_CANCELLED", "cancelling twice is harmless"
    w = World()                                              # the cancel survives a crash, even a half-done step
    w.faults.add("payments.charge", lambda: (w.orch.cancel_order("o1"), "crash_after")[1])
    restarts = 0
    try:
        w.orch.run_saga("o1", DATA)
    except mod.Crash:
        restarts += 1
        w.new_orch().recover()
    assert restarts == 1, "the crash should have happened once"
    assert w.orch.order_status("o1") == "CANCELLED" and w.orch.status("o1") == "COMPENSATED", \
        "the cancel flag must be saved in sqlite: after the restart the order should end CANCELLED"
    w.expect(0, "cancel + crash during the charge (the half-done charge must be refunded)")
    w = World()                                              # a failing saga also releases the lock
    w.faults.add("courier.book", "fail")
    w.orch.run_saga("o1", DATA)
    assert w.orch.order_status("o1") == "CANCELLED", "a saga that failed and was undone leaves the order CANCELLED"
    note("      cancel is saved, applied at the next step boundary, and never leaves money or stock behind")


print(f"Lab 4 checks against {target}.py\n")
check("Milestone 1: the happy path", m1)
check("Milestone 2: compensation in reverse order", m2)
check("Milestone 3: idempotency keys and duplicate deliveries", m3)
check("Milestone 4: crash recovery and unknown outcomes", m4)
check("Milestone 5 (optional): a semantic lock on the order", m5)
for d in tmpdirs:
    shutil.rmtree(d, ignore_errors=True)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
