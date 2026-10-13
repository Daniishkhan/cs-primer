"""Self-check for Lab 6.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Everything runs in-process against a SQLite file in a temporary directory.
Crashes are simulated: the check passes a `crash(point)` hook that raises Crash
at a chosen point, throws away the connection (like a dead process: an open
transaction is rolled back), and reopens the file. Nothing depends on timing, and
all randomness is seeded. Prints a tick, a cross, or "not implemented yet" per milestone.
"""
import contextlib
import copy
import importlib
import json
import os
import random
import sqlite3
import sys
import tempfile

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


class Crash(BaseException):
    """A simulated crash. BaseException so that `except Exception` cannot hide it."""


def crash_at(point, nth=1):
    """A hook that raises Crash the nth time the code announces `point`."""
    seen = []

    def hook(p):
        if p == point:
            seen.append(p)
            if len(seen) == nth:
                raise Crash(point)
    hook.seen = seen
    return hook


# --- independent reference helpers: they do NOT use your code ----------------------------
REF_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, customer TEXT NOT NULL, item TEXT NOT NULL,
    total_cents INTEGER NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, aggregate_id INTEGER NOT NULL,
    type TEXT NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL, published INTEGER NOT NULL DEFAULT 0);
"""


def ref_open(path):
    c = sqlite3.connect(path, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.executescript(REF_SCHEMA)
    return c


def ref_state(c, oid):
    r = c.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
    return {k: r[k] for k in ("id", "customer", "item", "total_cents", "status", "version")}


def ref_place(c, oid, customer, item, total):
    c.execute("BEGIN")
    c.execute("INSERT INTO orders VALUES (?,?,?,?, 'placed', 1)", (oid, customer, item, total))
    c.execute("INSERT INTO outbox (aggregate_id, type, payload, created_at) VALUES (?,?,?,0)",
              (oid, "OrderPlaced", json.dumps(ref_state(c, oid))))
    c.execute("COMMIT")


def ref_update(c, oid, status):
    c.execute("BEGIN")
    c.execute("UPDATE orders SET status = ?, version = version + 1 WHERE id = ?", (status, oid))
    c.execute("INSERT INTO outbox (aggregate_id, type, payload, created_at) VALUES (?,?,?,0)",
              (oid, "OrderStatusChanged", json.dumps(ref_state(c, oid))))
    c.execute("COMMIT")


def ref_events(c, since=0):
    return [{"id": r["id"], "aggregate_id": r["aggregate_id"], "type": r["type"], "payload": json.loads(r["payload"])}
            for r in c.execute("SELECT * FROM outbox WHERE id > ? ORDER BY id", (since,))]


def truth(c):
    return {r["id"]: {k: r[k] for k in ("id", "customer", "item", "total_cents", "status", "version")}
            for r in c.execute("SELECT * FROM orders")}


def ref_tokens(o):
    return {w.lower() for w in f"{o['item']} {o['customer']} {o['status']}".split()}


def ref_inverted(t):
    inv = {}
    for o in t.values():
        for w in ref_tokens(o):
            inv.setdefault(w, []).append(o["id"])
    return {w: sorted(v) for w, v in inv.items()}


def counts(path):
    c = sqlite3.connect(path)
    try:
        return (c.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
                c.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])
    finally:
        c.close()


@contextlib.contextmanager
def workdir():
    with tempfile.TemporaryDirectory(prefix="lab06-") as tmp:
        yield os.path.join(tmp, "shop.db")


def restart(conn, path):
    """A crashed process: its connection dies (an open transaction is rolled back), a new one starts."""
    try:
        conn.close()
    except Exception:
        pass
    return mod.open_db(path)


STATUSES = ["paid", "packed", "shipped", "cancelled"]
CUSTOMERS = ["ana", "ben", "chloe", "dev"]
ITEMS = ["red kettle", "blue lamp", "green rug", "wooden chair", "steel pan"]


def build_history(path, n_orders=12, seed=1):
    """Fill the DB (reference code) with orders and status changes. Returns (conn, events)."""
    rng = random.Random(seed)
    c = ref_open(path)
    ids = []
    for i in range(1, n_orders + 1):
        ref_place(c, i, rng.choice(CUSTOMERS), rng.choice(ITEMS), rng.randint(500, 9000))
        ids.append(i)
        for _ in range(rng.randint(0, 2)):
            ref_update(c, rng.choice(ids), rng.choice(STATUSES))
    for _ in range(10):
        ref_update(c, rng.choice(ids), rng.choice(STATUSES))
    return c, ref_events(c)


# --- Milestone 1 -----------------------------------------------------------------------------
EMPTY = {"cache_missing": [], "cache_extra": [], "cache_stale": [],
         "index_missing": [], "index_extra": [], "index_stale": []}


def want(**kw):
    d = {k: list(v) for k, v in EMPTY.items()}
    d.update(kw)
    return d


def m1():
    scenarios = [
        # (description, how to run, expected report)
        ("DB first, crash after the DB commit",       ("place", False, "after_db"),    want(cache_missing=[2], index_missing=[2])),
        ("DB first, crash after the cache write",     ("place", False, "after_cache"), want(index_missing=[2])),
        ("DB first, no crash",                        ("place", False, None),          want()),
        ("cache first, crash after the cache write",  ("place", True, "after_cache"),  want(cache_extra=[2])),
        ("cache first, crash after the index write",  ("place", True, "after_index"),  want(cache_extra=[2], index_extra=[2])),
        ("status update, crash after the DB commit",  ("update", False, "after_db"),   want(cache_stale=[1], index_stale=[1])),
        ("status update, crash after the cache write", ("update", False, "after_cache"), want(index_stale=[1])),
    ]
    lines = []
    for desc, (kind, cache_first, point), expected in scenarios:
        with workdir() as path:
            conn = mod.open_db(path)
            cache, index = mod.Cache(), mod.SearchIndex()
            mod.place_order_dual_write(conn, cache, index, 1, "ana", "red kettle", 2500)    # order 1 reaches all three
            crash = crash_at(point) if point else (lambda p: None)
            try:
                if kind == "place":
                    mod.place_order_dual_write(conn, cache, index, 2, "ben", "blue lamp", 1800,
                                               crash=crash, cache_first=cache_first)
                else:
                    mod.update_status_dual_write(conn, cache, index, 1, "paid", crash=crash)
            except Crash:
                pass
            else:
                assert point is None, f"{desc}: the crash hook was never reached"
            conn = restart(conn, path)
            got = mod.diagnose(conn, cache, index)
            assert isinstance(got, dict), "diagnose() must return a dict with the six keys cache_missing ... index_stale"
            for k, v in expected.items():
                assert k in got, f"{desc}: the report has no key {k!r} (keys: {sorted(got)})"
                assert sorted(got[k]) == v, (f"{desc}: expected {k} = {v}, but diagnose() reported {sorted(got[k])}. "
                                             f"Hint: compare each system with the DB, which is the truth")
            lines.append(f"        {desc:<46} -> " + (", ".join(f"{k}={v}" for k, v in expected.items() if v) or "all consistent"))
            conn.close()
    note("      what each crash leaves behind (the DB is the truth):")
    for ln in lines:
        note(ln)


# --- Milestone 2 -----------------------------------------------------------------------------
def m2():
    expected = {"id": 1, "customer": "ana", "item": "red kettle", "total_cents": 2500, "status": "placed", "version": 1}
    with workdir() as path:
        conn = mod.open_db(path)
        mod.place_order(conn, 1, "ana", "red kettle", 2500)
        assert counts(path) == (1, 1), f"one order should produce one orders row and one outbox row, got (orders, outbox) = {counts(path)}"
        r = sqlite3.connect(path).execute("SELECT aggregate_id, type, payload, published, created_at FROM outbox").fetchone()
        assert r[0] == 1, f"outbox.aggregate_id should be the order id (1), got {r[0]}"
        assert r[1] == "OrderPlaced", f"event type should be 'OrderPlaced', got {r[1]!r}"
        assert json.loads(r[2]) == expected, f"payload should carry the whole order state {expected}, got {r[2]}"
        assert r[3] == 0, "a fresh outbox row is unpublished (published = 0)"
        assert r[4] is not None, "created_at must be filled in"
        mod.update_status(conn, 1, "paid")
        st = sqlite3.connect(path).execute("SELECT status, version FROM orders WHERE id = 1").fetchone()
        assert st == ("paid", 2), f"update_status should set status 'paid' and bump version to 2, got {st}"
        rows = sqlite3.connect(path).execute("SELECT type, payload FROM outbox ORDER BY id").fetchall()
        assert [x[0] for x in rows] == ["OrderPlaced", "OrderStatusChanged"], f"expected two events in order, got {[x[0] for x in rows]}"
        assert json.loads(rows[1][1]) == dict(expected, status="paid", version=2), "the second event must carry the NEW state (status paid, version 2)"
        conn.close()

    # Crash injection: place_order
    for point, survives in (("after_order_insert", False), ("before_commit", False), ("after_commit", True)):
        with workdir() as path:
            conn = mod.open_db(path)
            hook = crash_at(point)
            try:
                mod.place_order(conn, 7, "ben", "blue lamp", 1800, crash=hook)
            except Crash:
                pass
            assert hook.seen, f"your place_order never called crash({point!r}); keep the crash() calls where the docstring puts them"
            conn = restart(conn, path)
            got = counts(path)
            want_counts = (1, 1) if survives else (0, 0)
            assert got == want_counts, (f"crash at {point!r}: (orders, outbox) = {got}, expected {want_counts}. "
                                        + ("Both rows must exist or neither." if not survives else "The commit had happened: both rows must be there."))
            conn.close()

    # Crash injection: update_status
    for point, survives in (("after_order_update", False), ("before_commit", False), ("after_commit", True)):
        with workdir() as path:
            conn = mod.open_db(path)
            mod.place_order(conn, 1, "ana", "red kettle", 2500)
            hook = crash_at(point)
            try:
                mod.update_status(conn, 1, "paid", crash=hook)
            except Crash:
                pass
            assert hook.seen, f"your update_status never called crash({point!r})"
            conn = restart(conn, path)
            version = sqlite3.connect(path).execute("SELECT version FROM orders WHERE id = 1").fetchone()[0]
            events = counts(path)[1]
            assert (version, events) == ((2, 2) if survives else (1, 1)), (
                f"crash at {point!r}: (order version, outbox rows) = {(version, events)}; "
                f"the order change and its event must succeed or fail together")
            conn.close()

    # A failing statement must not leave a half transaction or a stray event behind.
    with workdir() as path:
        conn = mod.open_db(path)
        mod.place_order(conn, 1, "ana", "red kettle", 2500)
        try:
            mod.place_order(conn, 1, "ana", "red kettle", 2500)         # duplicate primary key
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("placing order 1 twice should raise sqlite3.IntegrityError")
        assert counts(path) == (1, 1), f"the failed duplicate must not add an outbox row, got {counts(path)}"
        assert not conn.in_transaction, "after the error your transaction must be rolled back (conn.in_transaction is still True)"
        mod.place_order(conn, 2, "ben", "blue lamp", 100)
        assert counts(path) == (2, 2)
        conn.close()
    note("      crash points tried: after the order insert, before commit, after commit - orders and outbox always agree")


# --- Milestone 3 -----------------------------------------------------------------------------
def m3():
    with workdir() as path:
        ref = ref_open(path)
        for i in range(1, 6):
            ref_place(ref, i, "ana", "red kettle", 100 * i)
        ref_update(ref, 2, "paid")                                      # outbox ids 1..6
        conn = mod.open_db(path)
        log = []
        n = mod.relay_once(conn, log)
        assert n == 6, f"relay_once should return the number of events it published (6), returned {n}"
        assert [e["id"] for e in log] == [1, 2, 3, 4, 5, 6], f"events must be published in outbox id order, got {[e['id'] for e in log]}"
        e = log[5]
        assert set(e) >= {"id", "aggregate_id", "type", "payload"}, f"each event needs id, aggregate_id, type, payload; got keys {sorted(e)}"
        assert e["type"] == "OrderStatusChanged" and e["aggregate_id"] == 2 and e["payload"]["status"] == "paid" and e["payload"]["version"] == 2, \
            f"event 6 should be the status change of order 2 with the payload as a dict, got {e}"
        unpublished = ref.execute("SELECT COUNT(*) FROM outbox WHERE published = 0").fetchone()[0]
        assert unpublished == 0, f"published rows must be marked published = 1 ({unpublished} still unmarked)"
        assert mod.relay_once(conn, log) == 0 and len(log) == 6, "running the relay again with nothing new must publish nothing"
        ref_place(ref, 6, "ben", "blue lamp", 50)
        assert mod.relay_once(conn, log) == 1 and [x["id"] for x in log][-1] == 7 and len(log) == 7, "only the new row should be published"
        conn.close()

    # Crash between publish and mark: at-least-once.
    with workdir() as path:
        ref = ref_open(path)
        for i in range(1, 6):
            ref_place(ref, i, "ana", "red kettle", 100 * i)
        ref_update(ref, 2, "paid")
        conn = mod.open_db(path)
        log = []
        hook = crash_at("after_publish", nth=3)
        try:
            mod.relay_once(conn, log, crash=hook)
        except Crash:
            pass
        assert hook.seen, "your relay_once never called crash('after_publish') between publishing and marking"
        before = [e["id"] for e in log]
        assert before[:3] == [1, 2, 3] and len(before) == 3, f"the crash came right after publishing event 3; log ids so far: {before}"
        conn = restart(conn, path)
        mod.relay_once(conn, log)                                       # the restarted relay
        ids = [e["id"] for e in log]
        assert set(ids) == {1, 2, 3, 4, 5, 6}, f"an event was LOST: log ids are {ids}. Mark a row only AFTER it is published"
        assert ids.count(3) == 2, f"event 3 was published but not marked before the crash, so it must appear twice; log ids: {ids}"
        assert all(ids.count(i) == 1 for i in (4, 5, 6)), f"events 4-6 were never touched before the crash, expected once each; got {ids}"
        firsts = [i for n, i in enumerate(ids) if i not in ids[:n]]
        assert firsts == sorted(firsts), f"even after the restart events must first appear in id order, got {ids}"
        note(f"      after the crash and restart the log holds ids {ids}: event 3 is delivered twice (at-least-once)")
        conn.close()

    # Crash after marking: nothing duplicated.
    with workdir() as path:
        ref = ref_open(path)
        for i in range(1, 4):
            ref_place(ref, i, "ana", "red kettle", 100 * i)
        conn = mod.open_db(path)
        log = []
        try:
            mod.relay_once(conn, log, crash=crash_at("after_mark", nth=2))
        except Crash:
            pass
        conn = restart(conn, path)
        mod.relay_once(conn, log)
        assert [e["id"] for e in log] == [1, 2, 3], f"a crash AFTER the mark must not cause a duplicate, got {[e['id'] for e in log]}"
        conn.close()


# --- Milestone 4 -----------------------------------------------------------------------------
def compare(consumer_cache, consumer_index, t, label):
    """Assert the cache and index equal the database `t`."""
    if consumer_cache.entries != t:
        bad = [i for i in sorted(set(t) | set(consumer_cache.entries)) if consumer_cache.entries.get(i) != t.get(i)]
        i = bad[0]
        raise AssertionError(f"{label}: cache differs from the DB for {len(bad)} order(s). Order {i}: "
                             f"cache has version {(consumer_cache.entries.get(i) or {}).get('version')}, DB has version {(t.get(i) or {}).get('version')}")
    if consumer_index.docs != t:
        bad = [i for i in sorted(set(t) | set(consumer_index.docs)) if consumer_index.docs.get(i) != t.get(i)]
        raise AssertionError(f"{label}: the index's documents differ from the DB for orders {bad[:5]}")
    inv = {w: sorted(ids) for w, ids in consumer_index.inverted.items() if ids}
    assert inv == ref_inverted(t), (f"{label}: the inverted index is wrong. Did you remove an order's OLD tokens "
                                    f"(its old status) when it changed? {sorted(set(inv) ^ set(ref_inverted(t)))[:6]}")
    for term in ("paid", "shipped", "cancelled", "kettle", "ana"):
        assert consumer_index.search(term) == ref_inverted(t).get(term, []), f"{label}: search({term!r}) is wrong"


def deliver(events, label, t):
    cache, index = mod.Cache(), mod.SearchIndex()
    pristine = copy.deepcopy(events)
    for e in events:
        cache.handle(e)
    for e in events:
        index.handle(e)
    assert events == pristine, "handle() must not modify the event it is given"
    compare(cache, index, t, label)


def m4():
    with workdir() as path:
        ref, events = build_history(path)
        t = truth(ref)
        assert len(events) > 30
        rng = random.Random(42)
        deliver(events, "clean log", t)
        deliver([e for e in events for _ in (0, 1)], "every event twice in a row", t)
        deliver(events + events, "the whole log delivered twice", t)
        dups = list(events)
        for _ in range(25):
            dups.insert(rng.randrange(len(dups) + 1), rng.choice(events))
        deliver(dups, "random duplicates inserted at random places", t)
        for window in (3, 5):
            shuffled = []
            for k in range(0, len(events), window):
                chunk = events[k:k + window]
                rng.shuffle(chunk)
                shuffled += chunk
            deliver(shuffled, f"events reordered inside windows of {window}", t)
        mixed = []
        for k in range(0, len(events), 4):
            chunk = events[k:k + 4] + [rng.choice(events)]
            rng.shuffle(chunk)
            mixed += chunk
        deliver(mixed + mixed[:10], "duplicates AND reordering together", t)
        deliver(list(reversed(events)), "the entire log in REVERSE order", t)

        # A stale event arriving after a newer one must not roll state back.
        cache, index = mod.Cache(), mod.SearchIndex()
        by_order = {}
        for e in events:
            by_order.setdefault(e["aggregate_id"], []).append(e)
        multi = next(v for v in by_order.values() if len(v) >= 3)
        for c in (cache, index):
            c.handle(multi[-1])
            c.handle(multi[0])
        oid = multi[0]["aggregate_id"]
        assert cache.entries[oid]["version"] == multi[-1]["payload"]["version"], "an OLD event overwrote newer cache state"
        assert index.docs[oid]["version"] == multi[-1]["payload"]["version"], "an OLD event overwrote newer index state"
        note(f"      {len(events)} events, 8 deliveries (clean + 7 hostile: duplicates, replays, reordering, reverse); cache and index always equal the DB")


# --- Milestone 5 -----------------------------------------------------------------------------
def m5():
    with workdir() as path:
        ref, events = build_history(path, seed=7)
        log = list(events)
        t = truth(ref)
        for cls in (mod.Cache, mod.SearchIndex):
            c = mod.rebuild(log, cls)
            assert isinstance(c, cls), "rebuild(log, consumer_cls) must return the new consumer"
            assert c.offset == len(log), f"after replaying {len(log)} events the offset should be {len(log)}, got {c.offset}"
        cache, index = mod.rebuild(log, mod.Cache), mod.rebuild(log, mod.SearchIndex)
        # compare() wants both halves; build full objects
        full_cache, full_index = mod.Cache(), mod.SearchIndex()
        full_cache.poll(log)
        full_index.poll(log)
        compare(full_cache, full_index, t, "brand-new consumers replayed from offset 0")
        assert cache.entries == t and index.docs == t

        # New business happens; consumers that are already caught up read only the new events.
        ref_place(ref, 100, "dev", "wooden chair", 4200)
        ref_update(ref, 100, "paid")
        ref_update(ref, 3, "shipped")
        new = ref_events(ref, since=events[-1]["id"])
        assert len(new) == 3
        log.extend(new)
        n = full_cache.poll(log)
        assert n == 3, f"poll() should handle only the 3 new events (it resumes from its offset), it handled {n}"
        full_index.poll(log)
        assert full_cache.poll(log) == 0, "polling an up-to-date log must handle nothing"
        compare(full_cache, full_index, truth(ref), "incremental catch-up")

        # A consumer crashes after handling an event but before saving its offset: that event is redelivered.
        t = truth(ref)
        for cls, attr in ((mod.Cache, "entries"), (mod.SearchIndex, "docs")):
            c = cls()
            hook = crash_at("handled", nth=5)
            try:
                c.poll(log, crash=hook)
            except Crash:
                pass
            assert hook.seen, "your poll() never called crash('handled') after handle() and before advancing the offset"
            assert c.offset == 4, f"4 events were fully processed before the crash; offset should be 4, got {c.offset}"
            c.poll(log)                                                 # the restart: event 5 is handled a second time
            assert c.offset == len(log)
            assert getattr(c, attr) == t, f"{cls.__name__} state is wrong after a crash and a restart (redelivery of one event)"

        # A log with duplicates (as left behind by a crashed relay) replays correctly.
        noisy = [e for e in log for _ in (0, 1)]
        assert mod.rebuild(noisy, mod.Cache).entries == t
        # Empty log, and independent offsets
        empty = mod.rebuild([], mod.Cache)
        assert empty.entries == {} and empty.offset == 0
        a, b = mod.Cache(), mod.Cache()
        a.poll(log[:5])
        assert a.offset == 5 and b.offset == 0, "each consumer keeps its own offset"
        note(f"      replayed {len(log)} events from offset 0 into brand-new consumers: both equal the database")


print(f"Lab 6 checks against {target}.py\n")
check("Milestone 1: the dual-write bug (diagnose the divergence)", m1)
check("Milestone 2: transactional outbox (order and event, atomically)", m2)
check("Milestone 3: relay (at-least-once publishing)", m3)
check("Milestone 4: idempotent consumers", m4)
check("Milestone 5: catch-up and rebuild from offset 0", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
