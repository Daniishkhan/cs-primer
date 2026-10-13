"""Self-check for Lab 5.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Everything is in-process and deterministic: a fake clock, seeded randomness, sqlite files
in a temporary directory, and a race between two threads whose outcome does not depend on
who wins. Standard library only, no network, about a second to run. Prints a tick, a cross,
or "not implemented yet" for each milestone.
"""
import importlib
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
notes = []
TMP = tempfile.mkdtemp(prefix="lab05-")
_n = [0]


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


class Clock:
    """A fake clock: every call to it returns the next tick (default: +10 each time)."""

    def __init__(self, start=100.0, step=10.0):
        self.t = start - step
        self.step = step

    def __call__(self):
        self.t += self.step
        return self.t


def new_path():
    _n[0] += 1
    return os.path.join(TMP, "store%d.db" % _n[0])


def new_store(path=None, clock=None):
    return mod.EventStore(path or new_path(), clock=clock or Clock())


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


def dep(cents):
    return ("Deposited", {"v": 2, "amount_cents": cents})


def wd(cents):
    return ("Withdrawn", {"amount_cents": cents})


def opened(owner):
    return ("AccountOpened", {"owner": owner})


# --- Milestone 1 ---------------------------------------------------------------------
def m1():
    s = new_store()
    out = s.append("acc-1", 0, [opened("ada"), dep(500)])
    assert [e.version for e in out] == [1, 2], f"append should return the stored events with versions 1 and 2, got {[e.version for e in out]}"
    s.append("acc-2", 0, [opened("bob")])
    s.append("acc-1", 2, [wd(200)])
    evs = s.read_stream("acc-1")
    assert [(e.version, e.type) for e in evs] == [(1, "AccountOpened"), (2, "Deposited"), (3, "Withdrawn")], \
        f"read_stream('acc-1') returned {[(e.version, e.type) for e in evs]}"
    assert evs[1].data == {"v": 2, "amount_cents": 500}, f"data must round-trip as a dict, got {evs[1].data!r}"
    assert evs[0].recorded_at < evs[2].recorded_at, "recorded_at should come from the injected clock"
    assert [e.version for e in s.read_stream("acc-1", after_version=1)] == [2, 3], "after_version must skip older events"
    assert s.read_stream("nobody") == [], "an unknown stream has no events"
    allev = s.read_all()
    assert [e.stream_id for e in allev] == ["acc-1", "acc-1", "acc-2", "acc-1"], \
        f"read_all is the global log in append order, got {[e.stream_id for e in allev]}"
    seqs = [e.seq for e in allev]
    assert seqs == sorted(seqs) and len(set(seqs)) == 4, "seq must be unique and increasing across streams"
    assert [e.seq for e in s.read_all(after_seq=seqs[1])] == seqs[2:], "read_all(after_seq=n) returns events with seq > n"
    assert len(s.read_all(limit=2)) == 2, "read_all(limit=2) returns at most 2 events"

    # Optimistic concurrency: a stale expected_version is refused, and nothing is written.
    before = len(s.read_all())
    raises(mod.ConcurrencyError, lambda: s.append("acc-1", 2, [dep(1)]),
           "stream is at version 3 but the writer expected 2: expected ConcurrencyError")
    raises(mod.ConcurrencyError, lambda: s.append("acc-1", 5, [dep(1)]),
           "expecting a version in the future is also a mismatch: expected ConcurrencyError")
    raises(mod.ConcurrencyError, lambda: s.append("acc-new", 3, [dep(1), dep(2)]),
           "a new stream must be appended with expected_version 0")
    assert len(s.read_all()) == before, "a rejected append must write nothing"

    # Two writers who both loaded version 3 (two EventStore objects = two processes).
    path = new_path()
    a, b = new_store(path), new_store(path)
    a.append("race", 0, [opened("x")])
    a.append("race", 1, [dep(1), dep(2)])
    b.append("race", 3, [dep(3)])
    raises(mod.ConcurrencyError, lambda: a.append("race", 3, [dep(99)]),
           "writer A also read version 3 but B appended first: A must get ConcurrencyError")
    assert [e.version for e in b.read_stream("race")] == [1, 2, 3, 4]

    # The database itself must forbid duplicates, whatever the Python code does.
    try:
        s.conn.execute("INSERT INTO events (stream_id, version, type, data, recorded_at) VALUES ('acc-1', 1, 'X', '{}', 0)")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("the events table needs UNIQUE (stream_id, version): inserting a duplicate version succeeded")

    # A real race: 25 rounds, two threads each, released at the same instant by a barrier.
    rounds = 25
    outcomes = {i: [] for i in range(rounds)}
    errors = []
    start = threading.Barrier(2, timeout=20)

    def writer(store, who):
        try:
            for i in range(rounds):
                start.wait()
                try:
                    store.append("round-%d" % i, 0, [("Won", {"by": who})])
                    outcomes[i].append("ok")
                except mod.ConcurrencyError:
                    outcomes[i].append("conflict")
        except NotImplementedError as e:
            errors.append(e)
        except Exception as e:
            errors.append(e)
            start.abort()

    path = new_path()
    s1, s2 = new_store(path), new_store(path)
    s1.append("init", 0, [("Init", {})])        # creates the schema in both before the race
    threads = [threading.Thread(target=writer, args=(s1, "A"), daemon=True),
               threading.Thread(target=writer, args=(s2, "B"), daemon=True)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    for e in errors:
        if isinstance(e, NotImplementedError):
            raise e
        if isinstance(e, sqlite3.OperationalError):
            raise AssertionError(f"a writer got '{e}': start your transaction with BEGIN IMMEDIATE so a competing writer waits instead of failing")
        raise AssertionError(f"a writer thread crashed: {type(e).__name__}: {e}")
    for i in range(rounds):
        assert sorted(outcomes[i]) == ["conflict", "ok"], \
            f"round {i}: exactly one of two racing appends to version 1 must win, got {outcomes[i]}"
        assert len(s1.read_stream("round-%d" % i)) == 1
    note(f"      {rounds} rounds of two racing appends: {rounds} winners, {rounds} ConcurrencyErrors, no lost or duplicated version")


# --- Milestone 2 ---------------------------------------------------------------------
def m2():
    s = new_store()
    A = mod.Account
    execute = mod.execute
    execute(s, "a", lambda acct: acct.open("ada"))
    execute(s, "a", lambda acct: acct.deposit(10_000))
    execute(s, "a", lambda acct: acct.withdraw(2_500))
    acct = A.load(s, "a")
    assert acct.balance == 7_500, f"balance after +10000 -2500 should be 7500, got {acct.balance}"
    assert acct.version == 3 and acct.opened and acct.owner == "ada", \
        f"expected version 3, opened, owner ada; got version={acct.version} opened={acct.opened} owner={acct.owner}"
    fresh = A.load(mod.EventStore(s.path), "a")
    assert (fresh.balance, fresh.version) == (7_500, 3), "state must be derivable from the stored events alone"
    ghost = A.load(s, "never-seen")
    assert (ghost.version, ghost.opened, ghost.balance) == (0, False, 0), "an account with no events is empty, not an error"

    # Invariants. A refused command writes nothing.
    def refused(exc, account_id, decide, msg):
        n = len(s.read_all())
        raises(exc, lambda: execute(s, account_id, decide), msg)
        assert len(s.read_all()) == n, "a refused command must not append any event"

    refused(mod.InsufficientFunds, "a", lambda x: x.withdraw(7_501), "withdrawing more than the balance must raise InsufficientFunds")
    execute(s, "a", lambda x: x.withdraw(7_500))             # exactly the balance is fine
    assert A.load(s, "a").balance == 0
    refused(mod.AccountNotOpen, "b", lambda x: x.deposit(100), "depositing to an account that was never opened: AccountNotOpen")
    refused(mod.AccountNotOpen, "b", lambda x: x.withdraw(100), "withdrawing from an unopened account: AccountNotOpen")
    refused(mod.AlreadyOpen, "a", lambda x: x.open("eve"), "opening an open account: AlreadyOpen")
    refused(mod.InvalidAmount, "a", lambda x: x.deposit(0), "a zero deposit must raise InvalidAmount")
    refused(mod.InvalidAmount, "a", lambda x: x.deposit(-5), "a negative deposit must raise InvalidAmount")
    refused(mod.InvalidAmount, "a", lambda x: x.withdraw(0), "a zero withdrawal must raise InvalidAmount")
    assert issubclass(mod.InsufficientFunds, mod.DomainError)

    # Commands decide, they do not mutate: calling one twice gives the same answer.
    x = A.load(s, "a")
    assert x.deposit(5) == x.deposit(5) and x.balance == 0 and x.version == 4, "commands must return events without changing the aggregate"
    assert x.deposit(5)[0][0] == "Deposited" and x.deposit(5)[0][1]["amount_cents"] == 5

    # The invariant under concurrency: two clients both see 100 and both try to withdraw 80.
    execute(s, "c", lambda x: x.open("cy"))
    execute(s, "c", lambda x: x.deposit(100))
    one, two = A.load(s, "c"), A.load(s, "c")
    s.append("c", one.version, one.withdraw(80))
    raises(mod.ConcurrencyError, lambda: s.append("c", two.version, two.withdraw(80)),
           "the second client decided on stale state: its append must raise ConcurrencyError")
    assert A.load(s, "c").balance == 20, "only one withdrawal may have been recorded"
    raises(mod.InsufficientFunds, lambda: execute(s, "c", lambda x: x.withdraw(80)),
           "retrying on fresh state must now be refused: only 20 left")

    # execute() reloads and decides again after a conflict (so decide() runs twice here).
    calls = []

    def decide(acct):
        calls.append(acct.version)
        if len(calls) == 1:                         # a rival sneaks in between our load and our append
            s.append("c", acct.version, acct.deposit(1_000))
        return acct.deposit(7)

    execute(s, "c", decide)
    assert len(calls) == 2 and calls[1] == calls[0] + 1, f"decide should run again on the fresh state, versions seen: {calls}"
    assert A.load(s, "c").balance == 1_027, "the rival's deposit and the retried one must both be there"
    note("      the second of two stale withdrawals got ConcurrencyError, and the retry was refused for lack of funds")


# --- shared builder for milestones 3-5 ----------------------------------------------
def build_history(store, seed=7, accounts=("a1", "a2", "a3", "a4"), steps=240):
    """Raw appends only (milestone 1), with a seeded random mix of small and large amounts.
    Returns the truth: {account: (owner, balance)} and the list of large transactions' (stream, kind, cents)."""
    rng = random.Random(seed)
    bal, owner, ver, large = {}, {}, {}, []
    for a in accounts:
        store.append(a, 0, [opened("owner-" + a)])
        bal[a], owner[a], ver[a] = 0, "owner-" + a, 1
    for _ in range(steps):
        a = rng.choice(accounts)
        if rng.random() < 0.6 or bal[a] < 100:
            c = rng.choice([500, 2_500, 15_000, 120_000, 250_000])
            ev = dep(c)
            bal[a] += c
        else:
            c = min(bal[a], rng.choice([300, 4_000, 100_000, 180_000]))
            ev = wd(c)
            bal[a] -= c
        store.append(a, ver[a], [ev])
        ver[a] += 1
        if c >= 100_000:
            large.append((a, ev[0], c))
    return bal, owner, large


# --- Milestone 3 ---------------------------------------------------------------------
def m3():
    s = new_store()
    bal, owner, large = build_history(s)
    P = mod.Projector(s)
    assert P.position() == 0, "a new projector has processed nothing: position 0"
    assert P.all_balances() == {} and P.balance_of("a1") is None, "before catch_up the read model is empty (eventual consistency)"
    n = P.catch_up()
    total = len(s.read_all())
    assert n == total, f"catch_up should report how many events it handled ({total}), got {n}"
    assert P.position() == s.read_all()[-1].seq, "position must be the seq of the last event processed"
    assert P.all_balances() == bal, "account_balances differs from the balances computed straight from the events"
    for a in bal:
        assert P.balance_of(a) == bal[a]
    got = [(a, k, c) for (_, a, k, c) in P.large_transactions()]
    assert got == large, f"large_transactions should list every deposit/withdrawal of 100000 cents or more in log order: {len(got)} rows, expected {len(large)}"
    assert P.catch_up() == 0, "nothing new: catch_up must return 0"

    # Lag: new events are invisible to the read side until the projector catches up.
    s.append("a1", len(s.read_stream("a1")), [dep(777)])
    assert P.balance_of("a1") == bal["a1"], "the read model should still be stale before catch_up"
    assert P.catch_up() == 1 and P.balance_of("a1") == bal["a1"] + 777, "after catch_up the new deposit must show"
    bal["a1"] += 777

    # Idempotence: re-deliver the entire log (a crash after updating tables, before saving the position).
    before = (P.all_balances(), P.large_transactions(), P.position())
    P.catch_up(from_seq=0)
    assert (P.all_balances(), P.large_transactions(), P.position()) == before, \
        "replaying events the projector already applied changed the read model: make every handler idempotent"
    P.catch_up(from_seq=100)
    assert P.all_balances() == before[0] and P.position() == before[2], "a partial replay must not move the position backwards or double count"

    # Small batches reach the same place.
    Q = mod.Projector(s)
    steps = 0
    while Q.catch_up(limit=7):
        steps += 1
        assert steps < 1000, "catch_up(limit=7) never ran out of events"
    assert Q.all_balances() == bal and Q.large_transactions() == P.large_transactions(), "batched catch-up must equal one big catch-up"
    assert steps == -(-len(s.read_all()) // 7), f"expected {-(-len(s.read_all()) // 7)} batches of at most 7 events, got {steps}"

    # Rebuild from zero: identical.
    snapshot = (P.all_balances(), P.large_transactions(), P.position())
    P.rebuild()
    assert (P.all_balances(), P.large_transactions(), P.position()) == snapshot, "rebuild() from event 1 must give exactly the same read model"
    note(f"      {total + 1} events -> {len(bal)} balances + {len(large)} large transactions; replay and rebuild gave identical tables")


# --- Milestone 4 ---------------------------------------------------------------------
def m4():
    s = new_store()
    snaps = mod.SnapshotStore(s)
    A = mod.Account
    assert snaps.latest("a") is None, "no snapshot yet"
    mod.execute(s, "a", lambda x: x.open("ada"), snapshots=snaps, snapshot_every=50)
    for i in range(236):                                    # events 2..237
        mod.execute(s, "a", lambda x, i=i: x.deposit(1 + i % 5), snapshots=snaps, snapshot_every=50)
    expected = sum(1 + i % 5 for i in range(236))
    snap = snaps.latest("a")
    assert snap is not None and snap[0] == 200, f"snapshots every 50 events: the latest for a 237-event stream is at version 200, got {snap and snap[0]}"
    assert mod.Account.from_state("a", snap[1]).version == 200

    s.events_read = 0
    plain = mod.load_account(s, "a")
    full_reads = s.events_read
    s.events_read = 0
    fast = mod.load_account(s, "a", snaps)
    tail_reads = s.events_read
    assert plain.to_state() == fast.to_state(), f"snapshot + tail must equal a full replay: {fast.to_state()} vs {plain.to_state()}"
    assert fast.balance == expected and fast.version == 237
    assert full_reads == 237, f"a full replay reads all 237 events, read {full_reads}"
    assert tail_reads == 37, f"with the snapshot at 200 only the 37 later events should be read, read {tail_reads}"

    # A snapshot is a cache: throw it away and nothing changes.
    snaps.clear()
    assert snaps.latest("a") is None
    s.events_read = 0
    again = mod.load_account(s, "a", snaps)
    assert again.to_state() == plain.to_state() and s.events_read == 237, "without snapshots we fall back to a full replay"

    # A short stream never gets one; a command that crosses a boundary writes one.
    mod.execute(s, "b", lambda x: x.open("bob"), snapshots=snaps, snapshot_every=50)
    assert snaps.latest("b") is None, "1 event is far below the threshold: no snapshot"
    mod.execute(s, "a", lambda x: x.deposit(1), snapshots=snaps, snapshot_every=50)       # event 238, not a boundary
    assert snaps.latest("a") is None, "snapshots are written when a multiple of N is crossed, not on every append"
    mod.execute(s, "a", lambda x: x.deposit(1) * 13, snapshots=snaps, snapshot_every=50)   # events 239..251 in one command
    snap = snaps.latest("a")
    assert snap is not None and snap[0] == 251, "one command that crosses a multiple of 50 should leave a snapshot of the new state"
    acct = mod.load_account(s, "a", snaps)
    assert acct.to_state() == mod.load_account(s, "a").to_state()
    assert acct.version == 251, "a snapshot-based load must see events appended in bulk"
    note(f"      237-event stream: full replay read {full_reads} events, snapshot + tail read {tail_reads}; same state")


# --- Milestone 5 ---------------------------------------------------------------------
def m5():
    s = new_store(clock=Clock(100, 10))
    mod.execute(s, "t", lambda x: x.open("tia"))          # v1 at t=100
    mod.execute(s, "t", lambda x: x.deposit(5_000))       # v2 at t=110
    mod.execute(s, "t", lambda x: x.deposit(2_500))       # v3 at t=120
    mod.execute(s, "t", lambda x: x.withdraw(1_000))      # v4 at t=130
    mod.execute(s, "t", lambda x: x.deposit(300))         # v5 at t=140
    f = mod.account_as_of
    assert f(s, "t").balance == 6_800, "with no arguments, account_as_of is the current state"
    assert f(s, "t", at=125).balance == 7_500, f"at t=125 the balance was 7500, got {f(s, 't', at=125).balance}"
    assert f(s, "t", at=130).balance == 6_500, "the bound is inclusive: the withdrawal recorded at t=130 counts"
    assert f(s, "t", at=129.9).balance == 7_500
    assert f(s, "t", at=99).opened is False and f(s, "t", at=99).balance == 0, "before the account was opened it did not exist"
    assert f(s, "t", at=99).version == 0
    assert f(s, "t", version=2).balance == 5_000 and f(s, "t", version=2).version == 2
    assert f(s, "t", version=0).opened is False
    assert f(s, "t", version=99).balance == 6_800, "a version beyond the end just means 'now'"
    assert f(s, "t", version=4, at=125).balance == 7_500, "when both are given, both limits apply"
    assert f(s, "t", at=10**9).balance == 6_800
    hist = mod.balance_history(s, "t")
    assert hist == [(1, 100, 0), (2, 110, 5_000), (3, 120, 7_500), (4, 130, 6_500), (5, 140, 6_800)], f"balance_history gave {hist}"
    for v, t, b in hist:
        assert f(s, "t", version=v).balance == b == f(s, "t", at=t).balance
    note("      balance at t=125: 7500; at version 2: 5000; before it existed: 0 (not opened)")


# --- Milestone 6 (optional) ----------------------------------------------------------
def m6():
    s = new_store()
    old = {"amount": "12.50"}
    ev = mod.Event(1, "x", 1, "Deposited", old, 0.0)
    up = mod.upcast(ev)
    assert up.data.get("amount_cents") == 1250 and up.data.get("v") == 2, f"v1 {{'amount': '12.50'}} should become v2 with 1250 cents, got {up.data}"
    assert "amount" not in up.data, "the old field should be gone after upcasting"
    assert ev.data == {"amount": "12.50"}, "upcast must return a new event, not modify its argument"
    v2 = mod.Event(2, "x", 2, "Deposited", {"v": 2, "amount_cents": 99}, 0.0)
    assert mod.upcast(v2) == v2, "current events pass through unchanged"
    other = mod.Event(3, "x", 3, "Withdrawn", {"amount_cents": 5}, 0.0)
    assert mod.upcast(other) == other, "only Deposited v1 is upcast"
    for text, cents in [("19.99", 1999), ("0.10", 10), ("7", 700), ("1234.5", 123450), ("0.29", 29)]:
        got = mod.upcast(mod.Event(1, "x", 1, "Deposited", {"amount": text}, 0.0)).data["amount_cents"]
        assert got == cents, f"{text!r} dollars is {cents} cents, got {got} (float arithmetic loses a cent here: use Decimal or round)"

    # Old events are already in the log, in the old shape. Everything downstream must still work.
    s.append("old", 0, [opened("olga"), ("Deposited", {"amount": "19.99"}), ("Deposited", {"amount": "0.01"}),
                        dep(500), wd(300)])
    acct = mod.Account.load(s, "old")
    assert acct.balance == 2_200, f"1999 + 1 + 500 - 300 = 2200 cents, got {acct.balance}"
    raw = s.conn.execute("SELECT data FROM events WHERE stream_id='old' AND version=2").fetchone()[0]
    assert '"amount"' in raw and "amount_cents" not in raw, "upcasting happens on read: the stored row must keep its original v1 shape"
    P = mod.Projector(s)
    P.catch_up()
    assert P.balance_of("old") == 2_200, "the projector reads through the same upcaster"
    assert mod.account_as_of(s, "old", version=2).balance == 1_999
    note("      v1 {'amount': '19.99'} read as 1999 cents; the stored row is untouched")


print(f"Lab 5 checks against {target}.py\n")
try:
    check("Milestone 1: the event store and optimistic concurrency", m1)
    check("Milestone 2: aggregates rebuilt from events", m2)
    check("Milestone 3: projections and the read model", m3)
    check("Milestone 4: snapshots", m4)
    check("Milestone 5: temporal queries", m5)
    check("Milestone 6 (optional): upcasting old events", m6)
finally:
    shutil.rmtree(TMP, ignore_errors=True)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
