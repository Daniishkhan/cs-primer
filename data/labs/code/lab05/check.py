"""Self-check for Lab 5.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Everything is in-process and deterministic: transactions are interleaved by hand
(or by a seeded random scheduler), so there are no threads, no timing and no
flakiness. Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
Store, SerializationError = mod.Store, mod.SerializationError
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


def put(store, **kv):
    """Commit a transaction that writes the given keys (uses YOUR begin/write/commit)."""
    tx = store.begin()
    for k, v in kv.items():
        tx.write(k, v)
    tx.commit()


def raises(exc, fn, msg):
    try:
        fn()
    except exc:
        return
    except Exception as e:
        raise AssertionError(f"{msg} (got {type(e).__name__}: {e} instead)")
    raise AssertionError(msg)


# --- Milestone 1 ---------------------------------------------------------------------
def m1():
    s = Store()
    t1 = s.begin()
    assert t1.txid == 1, f"the first transaction should get txid 1, got {t1.txid}"
    assert s.next_txid == 2, "begin() must advance the global txid counter"
    assert set(t1.snapshot.active) == set(), f"nobody else was running: snapshot.active should be empty, got {set(t1.snapshot.active)}"
    t2 = s.begin()
    assert t2.txid == 2, f"txids must increase by one per begin(), got {t2.txid}"
    assert set(t2.snapshot.active) == {1}, \
        f"t2 began while t1 was running: snapshot.active should be {{1}}, got {set(t2.snapshot.active)}"
    assert t2.snapshot.txid == 2
    assert s.status[1] == "active" and s.status[2] == "active", "status[txid] should be 'active' after begin()"
    t1.write("x", 10)
    vs = s.versions.get("x")
    assert vs and len(vs) == 1, "write() on a new key should create exactly one Version in store.versions['x']"
    assert (vs[0].value, vs[0].created_by, list(vs[0].deleted_by)) == (10, 1, []), \
        f"first version should be (10, created_by=1, deleted_by=[]), got {vs[0]!r}"
    t1.write("x", 11)
    assert len(s.versions["x"]) == 1 and s.versions["x"][0].value == 11, \
        "writing the same key twice in ONE transaction should update your own version, not stack a second one"
    t1.commit()
    assert s.status[1] == "committed", "commit() should set status[txid] to 'committed'"
    t3 = s.begin()
    assert set(t3.snapshot.active) == {2}, f"t1 committed, t2 still runs: snapshot.active should be {{2}}, got {set(t3.snapshot.active)}"
    t3.write("x", 20)
    vs = s.versions["x"]
    assert len(vs) == 2, f"an update adds a new version next to the old one (2 versions), got {len(vs)}"
    assert (vs[1].value, vs[1].created_by) == (20, 3), f"new version should be (20, created_by=3), got {vs[1]!r}"
    assert list(vs[0].deleted_by) == [3], f"the replaced version should record deleted_by=[3], got {list(vs[0].deleted_by)}"
    assert list(vs[1].deleted_by) == [], "the new version is not deleted"
    t3.delete("x")
    assert len(s.versions["x"]) == 2 and list(s.versions["x"][1].deleted_by) == [3], \
        "deleting a key you wrote yourself marks YOUR version deleted_by your txid"
    t3.commit()
    t4 = s.begin()
    t4.delete("x")
    assert len(s.versions["x"]) == 2, "delete() adds no version"
    t2.commit()
    note("      store.show('x') after the steps above: " + str(s.show("x")))


# --- Milestone 2 ---------------------------------------------------------------------
def m2():
    s = Store()
    t = s.begin()
    assert t.read("a") is None, "reading a key that does not exist returns None"
    t.write("a", 1)
    assert t.read("a") == 1, "a transaction must see its own uncommitted write"
    t.write("a", 2)
    assert t.read("a") == 2, "...and its latest one"
    other = s.begin()
    assert other.read("a") is None, "an uncommitted write must be invisible to everyone else"
    t.commit()
    assert other.read("a") is None, "other began before t committed: its snapshot must not see t's write"
    later = s.begin()
    assert later.read("a") == 2, "a transaction that begins after the commit sees the value"
    other.commit()
    later.commit()

    # Repeatable read: T1 reads, T2 writes and commits, T1 reads again.
    s = Store()
    put(s, x=100)
    t1 = s.begin()
    assert t1.read("x") == 100
    t2 = s.begin()
    t2.write("x", 200)
    t2.commit()
    assert t1.read("x") == 100, "REPEATABLE READ broken: T1 saw T2's commit that happened after T1's snapshot"
    t3 = s.begin()
    assert t3.read("x") == 200, "a new transaction should see 200"
    for t in (t1, t3):
        t.commit()

    # The tricky one: a LOWER txid that commits after my snapshot (it is in snapshot.active).
    s = Store()
    a = s.begin()
    b = s.begin()
    a.write("k", "from-a")
    a.commit()
    assert b.read("k") is None, ("a has the smaller txid, but it was still running when b took its snapshot: "
                                 "b must not see it (check snapshot.active)")
    # A HIGHER txid that committed before I read must also stay invisible.
    c = s.begin()
    d = s.begin()
    d.write("k", "from-d")
    d.commit()
    assert c.read("k") == "from-a", "d began after c's snapshot: invisible to c"

    # Deletes
    s = Store()
    put(s, z=5)
    old = s.begin()
    d = s.begin()
    d.delete("z")
    assert d.read("z") is None, "after deleting z, d itself must not see it"
    assert s.begin().read("z") == 5, "an uncommitted delete must not hide z from others"
    d.commit()
    assert old.read("z") == 5, "old's snapshot predates the delete: it still sees z"
    assert s.begin().read("z") is None, "after the delete commits, new snapshots no longer see z"
    # Delete, then write again, in one transaction
    e = s.begin()
    e.write("z", 6)
    e.delete("z")
    assert e.read("z") is None
    e.write("z", 7)
    assert e.read("z") == 7
    e.commit()
    assert s.begin().read("z") == 7

    # Read skew: an auditor must always see a consistent total of 100.
    s = Store()
    put(s, a=50, b=50)
    audit = s.begin()
    first = audit.read("a")
    mover = s.begin()
    mover.write("a", 0)
    mover.write("b", 100)
    mover.commit()
    second = audit.read("b")
    assert first + second == 100, f"READ SKEW: the auditor saw a={first} and b={second}; they must add up to 100"


# --- Milestone 3 ---------------------------------------------------------------------
def m3():
    s = Store()
    put(s, x=1)
    t = s.begin()
    t.write("x", 2)
    t.write("y", 9)
    t.delete("x")
    t.abort()
    assert s.status[t.txid] == "aborted", "abort() should set status to 'aborted'"
    r = s.begin()
    assert r.read("x") == 1, "an aborted write/delete must not hide the old version of x"
    assert r.read("y") is None, "an aborted insert must be invisible"
    r.commit()
    # Aborted while others were running, then read by a transaction whose txid is higher AND not in its active set.
    s = Store()
    a = s.begin()
    b = s.begin()
    a.write("k", "ghost")
    a.abort()
    c = s.begin()
    assert c.read("k") is None, "a's txid is lower than c's and a is not running any more, but a ABORTED: invisible"
    assert b.read("k") is None
    # Abort leaves nothing behind that can block later writers
    c.write("k", "real")
    c.commit()
    assert s.begin().read("k") == "real"
    # Using a finished transaction is an error
    raises(RuntimeError, lambda: a.read("k"), "reading in an aborted transaction should raise RuntimeError")
    raises(RuntimeError, lambda: a.commit(), "committing an aborted transaction should raise RuntimeError")
    raises(RuntimeError, lambda: c.write("k", 1), "writing in a committed transaction should raise RuntimeError")
    raises(RuntimeError, lambda: c.abort(), "aborting a committed transaction should raise RuntimeError")
    assert b.txid in s.live and a.txid not in s.live and c.txid not in s.live, \
        f"store.live should list only running transactions, got {sorted(s.live)}"


# --- Milestone 4 ---------------------------------------------------------------------
def m4():
    # Lost update: two withdrawals of 30 from a balance of 100.
    s = Store()
    put(s, balance=100)
    t1, t2 = s.begin(), s.begin()
    b1, b2 = t1.read("balance"), t2.read("balance")
    t1.write("balance", b1 - 30)
    t2.write("balance", b2 - 30)
    t1.commit()
    raises(SerializationError, t2.commit, "t2 committed a write to a key that t1 changed after t2's snapshot: expected SerializationError")
    assert s.status[t2.txid] == "aborted", "the loser must be left in the 'aborted' state"
    check_tx = s.begin()
    assert check_tx.read("balance") == 70, f"balance should be 70 (one withdrawal applied), got {check_tx.read('balance')}"
    check_tx.commit()
    # Retry succeeds.
    retry = s.begin()
    retry.write("balance", retry.read("balance") - 30)
    retry.commit()
    assert s.begin().read("balance") == 40, "after the retry both withdrawals are applied: balance 40"

    # First committer wins, whichever it is.
    s = Store()
    put(s, k=0)
    a, b = s.begin(), s.begin()
    a.write("k", 1)
    b.write("k", 2)
    b.commit()
    raises(SerializationError, a.commit, "a started first but b committed first: a must lose")
    assert s.begin().read("k") == 2

    # No conflict when the writes are to different keys, or are not concurrent, or the rival aborted.
    s = Store()
    put(s, p=0, q=0)
    a, b = s.begin(), s.begin()
    a.write("p", 1)
    b.write("q", 1)
    a.commit()
    b.commit()
    a = s.begin()
    a.write("p", 2)
    a.commit()
    b = s.begin()
    b.write("p", 3)
    b.commit()
    a, b = s.begin(), s.begin()
    a.write("p", 4)
    a.abort()
    b.write("p", 5)
    b.commit()
    assert s.begin().read("p") == 5
    # A concurrent delete conflicts with a concurrent write.
    a, b = s.begin(), s.begin()
    a.delete("p")
    b.write("p", 6)
    a.commit()
    raises(SerializationError, b.commit, "delete vs write of the same key, both concurrent: expected a conflict")
    # A failed commit leaves the winner's data intact and the loser's invisible.
    assert s.begin().read("p") is None

    # run_transaction retries. A rival commits during the first attempt only.
    s = Store()
    put(s, balance=100)
    attempts = []

    def withdraw(tx):
        attempts.append(1)
        v = tx.read("balance")
        if len(attempts) == 1:
            rival = s.begin()
            rival.write("balance", rival.read("balance") - 30)
            rival.commit()
        tx.write("balance", v - 30)

    mod.run_transaction(s, withdraw)
    assert len(attempts) == 2, f"run_transaction should retry once after the conflict, ran fn {len(attempts)} time(s)"
    assert s.begin().read("balance") == 40
    boom = []

    def failing(tx):
        boom.append(tx)
        raise ValueError("app bug")
    raises(ValueError, lambda: mod.run_transaction(s, failing), "an application error should propagate out of run_transaction")
    assert s.status[boom[0].txid] == "aborted", "run_transaction must abort the transaction when fn raises"

    # Fuzz: random transfers between accounts + auditors, 4 transactions in flight.
    for seed in range(5):
        rng = random.Random(seed)
        s = Store()
        accounts = ["a0", "a1", "a2", "a3", "a4"]
        total = 1000
        put(s, **{k: total // len(accounts) for k in accounts})
        live = []
        commits = aborts = audits = 0
        for step in range(400):
            if len(live) < 4 and rng.random() < 0.4:
                if rng.random() < 0.2:
                    live.append({"tx": s.begin(), "kind": "audit", "todo": list(accounts)})
                else:
                    x, y = rng.sample(accounts, 2)
                    live.append({"tx": s.begin(), "kind": "xfer", "x": x, "y": y, "amt": rng.randint(1, 20), "n": 0})
                continue
            if not live:
                continue
            w = rng.choice(live)
            tx = w["tx"]
            if w["kind"] == "audit":
                if w["todo"]:
                    w.setdefault("sum", 0)
                    w["sum"] += tx.read(w["todo"].pop(0)) or 0
                else:
                    assert w["sum"] == total, f"seed {seed}: an auditor saw total {w['sum']} instead of {total} (snapshot not consistent)"
                    tx.commit()
                    audits += 1
                    live.remove(w)
                continue
            n = w["n"]
            if n == 0:
                w["bx"] = tx.read(w["x"])
            elif n == 1:
                w["by"] = tx.read(w["y"])
            elif n == 2:
                tx.write(w["x"], w["bx"] - w["amt"])
            elif n == 3:
                tx.write(w["y"], w["by"] + w["amt"])
            else:
                try:
                    tx.commit()
                    commits += 1
                except SerializationError:
                    aborts += 1
                live.remove(w)
            w["n"] += 1
        for w in live:
            w["tx"].abort()
        final = s.begin()
        got = sum(final.read(k) for k in accounts)
        assert got == total, f"seed {seed}: money was created or destroyed: total is {got}, expected {total} (lost updates!)"
        assert commits > 5 and aborts > 0 and audits > 0, f"seed {seed}: the fuzz did not exercise conflicts ({commits} commits, {aborts} aborts)"
    note("      fuzz: 5 seeds x 400 steps of concurrent transfers and audits: total always 1000")


# --- Milestone 5 ---------------------------------------------------------------------
def doctors(ssi):
    s = Store(ssi=ssi)
    put(s, alice=True, bob=True)
    return s


def on_call(s):
    t = s.begin()
    n = sum(1 for d in mod.DOCTORS if t.read(d))
    t.abort()                                   # read-only: nothing to commit
    return n


def m5():
    # Plain SI: both doctors leave. The anomaly is real.
    s = doctors(ssi=False)
    ta, tb = s.begin(), s.begin()
    ra = mod.go_off_call(ta, "alice")
    rb = mod.go_off_call(tb, "bob")
    assert ra is True and rb is True, "each doctor saw two on call, so go_off_call should return True for both"
    ta.commit()
    tb.commit()                                 # SI has no objection: they wrote different keys
    n = on_call(s)
    assert n == 0, f"under plain snapshot isolation both commits should succeed and leave 0 doctors on call (got {n})"
    note("      plain SI: both transactions committed; doctors on call = 0   <- write skew reproduced")

    # SSI-lite: the second committer is aborted.
    s = doctors(ssi=True)
    ta, tb = s.begin(), s.begin()
    assert mod.go_off_call(ta, "alice") and mod.go_off_call(tb, "bob")
    ta.commit()
    raises(SerializationError, tb.commit,
           "ssi=True: bob's transaction read alice's row, which a concurrent transaction changed and committed: expected SerializationError")
    assert on_call(s) == 1, "exactly one doctor should have gone off call"
    again = s.begin()
    assert mod.go_off_call(again, "bob") is False, "the retry sees only bob on call, so it must refuse"
    again.commit()
    assert on_call(s) == 1
    note("      ssi=True: the second commit raised SerializationError; doctors on call = 1")

    # Read-only and disjoint transactions are fine in SSI-lite when nothing concurrent touched what they read.
    s = Store(ssi=True)
    put(s, p=1, q=1)
    a, b = s.begin(), s.begin()
    a.read("p"); a.write("p", 2)
    b.read("q"); b.write("q", 2)
    a.commit()
    b.commit()
    # ssi must not break ordinary write-write detection or the earlier milestones
    s = Store(ssi=True)
    put(s, balance=100)
    t1, t2 = s.begin(), s.begin()
    t1.write("balance", t1.read("balance") - 30)
    t2.write("balance", t2.read("balance") - 30)
    t1.commit()
    raises(SerializationError, t2.commit, "lost update must still be caught with ssi=True")

    # Randomised interleavings of 3 steps x 2 doctors, 60 seeds.
    def run(ssi, seed):
        rng = random.Random(seed)
        s = doctors(ssi)
        state = {"alice": 0, "bob": 0}
        trs = {}
        todo = ["alice"] * 3 + ["bob"] * 3
        order = []
        while todo:
            d = rng.choice(todo)
            todo.remove(d)
            order.append(d)
        for d in order:
            st = state[d]
            if st == 0:
                trs[d] = s.begin()
            elif st == 1:
                mod.go_off_call(trs[d], d)
            else:
                try:
                    trs[d].commit()
                except SerializationError:
                    retry = s.begin()
                    mod.go_off_call(retry, d)
                    retry.commit()
            state[d] += 1
        return on_call(s)
    si_bad = sum(1 for seed in range(60) if run(False, seed) == 0)
    ssi_bad = sum(1 for seed in range(60) if run(True, seed) == 0)
    assert si_bad > 0, "plain SI should hit the anomaly in some interleavings"
    assert ssi_bad == 0, f"with ssi=True nobody should ever be left with zero doctors, but {ssi_bad} of 60 interleavings did"
    note(f"      60 random interleavings: plain SI left nobody on call {si_bad} times, SSI-lite 0 times")


# --- Milestone 6 ---------------------------------------------------------------------
def m6():
    s = Store()
    put(s, x=1)                                 # tx1: v1
    reader = s.begin()                          # tx2 sees x=1
    put(s, x=2)                                 # tx3: v2, v1 deleted by 3
    put(s, x=3)                                 # tx4: v3, v2 deleted by 4
    assert len(s.versions["x"]) == 3
    n = s.vacuum()
    assert n == 1, f"v2 is invisible to the reader and to everyone new, so exactly 1 version (v2) can go; vacuum returned {n}"
    assert [v.value for v in s.versions["x"]] == [1, 3], f"the reader still needs x=1, got {[v.value for v in s.versions['x']]}"
    assert reader.read("x") == 1, "vacuum removed a version an active snapshot still needed"
    reader.commit()
    n = s.vacuum()
    assert n == 1, f"with the reader finished, v1 is garbage: expected 1 removed, got {n}"
    assert [v.value for v in s.versions["x"]] == [3]
    assert s.vacuum() == 0, "nothing left to reclaim: vacuum must return 0"
    t = s.begin()
    t.write("x", 99)
    t.write("junk", 1)
    t.abort()
    assert s.vacuum() == 2, "an aborted transaction's two new versions are garbage"
    assert s.show("x") == [(3, 4, [])], f"x should be back to a single clean version, got {s.show('x')}"
    assert "junk" not in s.versions, "a key with no versions left should disappear from store.versions"
    # A running writer's versions are not garbage; a committed delete makes the key vanish once nobody can see it.
    w = s.begin()
    w.write("x", 4)
    assert s.vacuum() == 0, "versions of a still-running transaction must be kept"
    w.commit()
    d = s.begin()
    d.delete("x")
    d.commit()
    assert s.vacuum() == 2 and "x" not in s.versions, "after a committed delete with no readers, all versions of x are garbage"
    note("      vacuum reclaimed old versions only after the last reader that could see them had finished")


print(f"Lab 5 checks against {target}.py\n")
check("Milestone 1: versions, txids and snapshots", m1)
check("Milestone 2: visibility rules and repeatable reads", m2)
check("Milestone 3: abort makes versions invisible", m3)
check("Milestone 4: first-committer-wins and lost updates", m4)
check("Milestone 5: write skew, and SSI-lite", m5)
check("Milestone 6 (optional): garbage collection", m6)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
