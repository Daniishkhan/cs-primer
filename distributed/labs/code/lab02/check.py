"""Self-check for Lab 2: Leases & Fencing Tokens.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 17    # milestone 3, replaying ONLY seed 17, with its timeline

The world is simulated: time, clocks, pauses and delayed messages all come from one
seeded random generator, so every run is identical. When a seed fails, the message
names it and prints the timeline of what happened, so you can replay exactly that run.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import os
import random
import sys

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

CHAOS = dict(clients=3, jobs=3, rho=0.03, slow_p=0.05, slow_max=3000, pause_p=0.15, pause_max=4000)
DRIFT = dict(clients=3, jobs=40, rho=0.05, lease_ms=1000, renew=False)       # clocks drift, nothing else goes wrong
MIXED = dict(clients=3, jobs=40, rho=0.05, lease_ms=1000, renew=False, pause_p=0.003, pause_max=2500)
SCRIPT = dict(clients=2, jobs={"c0": 1, "c1": 8}, script={"c0": {"after_check": [1300]}},
              starts={"c0": 0, "c1": 100}, delay=(10, 10), work=40, lease_ms=1000)


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


def fuzz(count, **kw):
    """Run `count` seeds; return a dict of tallies and the first corrupted/unfinished world."""
    tally = {"corrupt": 0, "stale": 0, "rejected": 0, "unfinished": 0, "first_bad": None, "seeds": []}
    for s in seeds(range(count)):
        w = mod.build_world(s, **kw).run()
        problem = None if w.finished() else "clients never finished (liveness)"
        problem = problem or w.corrupted()
        if not w.finished():
            tally["unfinished"] += 1
        if w.corrupted():
            tally["corrupt"] += 1
        tally["stale"] += bool(w.store.stale_accepted)
        tally["rejected"] += bool(w.store.rejected)
        if problem:
            tally["seeds"].append(s)
            if tally["first_bad"] is None:
                tally["first_bad"] = (s, problem, w)
    return tally


def explain(tally):
    s, problem, w = tally["first_bad"]
    return f"seed {s}: {problem}\n{w.timeline(24)}"


# =============================================================================
# Milestone 1: the lock service
# =============================================================================
def m1():
    svc = mod.LockService(1000)
    assert svc.acquire("a", 0) == 1, "the first grant should carry token 1"
    assert svc.acquire("b", 500) is None, "b asked while a's lease (0..1000) was valid: refuse"
    assert svc.acquire("a", 500) is None, "the holder asking again should renew, not acquire: refuse"
    assert svc.renew("a", 1, 500) is True, "a holds token 1 and its lease is valid: renew must succeed"
    assert svc.acquire("b", 1499) is None, "renewal at t=500 extends the lease to 1500, so t=1499 is still a's"
    assert svc.acquire("b", 1500) == 2, "at exactly t=1500 the lease has expired (valid for t < 1500): b gets token 2"
    assert svc.renew("a", 1, 1500) is False, "a lost the lock to b: its renew must fail"
    assert svc.renew("b", 1, 1600) is False, "b holds token 2, not token 1: renew with the wrong token must fail"
    assert svc.renew("b", 2, 2500) is False, "b's lease ran out at 2500: an expired lease cannot be renewed, even if nobody else took the lock"
    assert svc.acquire("b", 2500) == 3, "b acquiring again after expiry still gets a NEW token (3)"
    assert svc.release("b", 2, 2600) is False, "releasing with a stale token must fail"
    assert svc.release("b", 3, 2600) is True, "the holder may release early"
    assert svc.acquire("a", 2600) == 4, "after a release the lock is free at once, with token 4: tokens never go back"
    assert svc.last_token == 4
    # compare against an independent model on random operation sequences
    for s in seeds(range(200)):
        rng = random.Random(s)
        svc = mod.LockService(100)
        holder, token, expires, last = None, 0, 0, 0
        now = 0
        for step in range(60):
            now += rng.randint(0, 60)
            who = rng.choice("abc")
            op = rng.choice(["acquire", "renew", "release"])
            held = holder is not None and now < expires
            if op == "acquire":
                got = svc.acquire(who, now)
                if held:
                    assert got is None, f"seed {s} t={now}: {who} acquired while {holder}'s lease was valid until {expires}"
                else:
                    assert got == last + 1, f"seed {s} t={now}: expected token {last + 1}, got {got}"
                    last, holder, token, expires = got, who, got, now + 100
            else:
                tk = rng.choice([token, token, max(0, token - 1)])
                valid = held and holder == who and token == tk
                got = svc.renew(who, tk, now) if op == "renew" else svc.release(who, tk, now)
                assert bool(got) == valid, f"seed {s} t={now}: {op}({who}, {tk}) returned {got}, expected {valid}"
                if valid and op == "renew":
                    expires = now + 100
                if valid and op == "release":
                    holder = None
    return "200 random operation sequences agree with the model; tokens only ever increase"


# =============================================================================
# Milestone 2: clients with pauses, drift and delays; the unsafe naive lock
# =============================================================================
def m2():
    # unit: the client counts from the SEND time, on its own clock
    w = mod.build_world(0, clients=1, jobs=1)
    c = w.clients[0]
    assert c.token is None and not c.lease_ok(), "a client with no token does not hold a lease"
    w.sim.now = 500
    c.sent_local = 300
    c.on_grant(7, 1000)
    assert c.token == 7, "on_grant must remember the token"
    assert c.deadline == 1300, f"the lease is 1000 ms counted from the send time (local 300), so deadline 1300; got {c.deadline}"
    w.sim.now = 1299
    assert c.lease_ok(), "local clock 1299 < deadline 1300: still ok"
    w.sim.now = 1300
    assert not c.lease_ok(), "local clock 1300 >= deadline 1300: the lease is over"
    c.margin = 100
    c.sent_local = 300
    c.on_grant(8, 1000)
    assert c.deadline == 1200, f"with a 100 ms margin the client stops 100 ms early (deadline 1200); got {c.deadline}"
    c.margin = 0
    w.sim.drift["c0"] = -0.10                      # a slow clock: it reads 10% less than true time
    w.sim.now = 1400
    c.sent_local = 300
    c.on_grant(9, 1000)
    assert c.lease_ok(), "at true t=1400 a 10%-slow clock reads 1260 < 1300: THIS is how a slow clock outlives its lease. lease_ok must use self.local()"
    c.sent_local = 1250
    c.on_renewed(1000)
    assert c.deadline == 2250, f"on_renewed counts from the renew request's send time: expected 2250, got {c.deadline}"
    # unit: the unfenced storage says yes to everything
    st = mod.Storage()
    assert st.write(5, 10) is True and st.read(5) == (True, 10), "an unfenced Storage stores what it is given"
    assert st.write(1, 11) is True and st.value == 11, "an UNFENCED storage accepts an old token: that is the bug we are about to see"
    # the scripted accident: c0 freezes for 1.3 s right after checking its lease
    w = mod.build_world(1, fenced=False, **SCRIPT).run()
    again = mod.build_world(1, fenced=False, **SCRIPT).run()
    assert w.sim.trace == again.sim.trace, "the same seed must replay the same timeline"
    assert w.finished(), "all clients should finish\n" + w.timeline()
    assert w.store.stale_accepted >= 1, ("the freeze was supposed to make c0 write with token 1 after the storage saw token 2, "
                                         "but no stale write was accepted. Timeline:\n" + w.timeline())
    bad = w.corrupted()
    assert bad, "the unsafe lock should have lost an update here. Timeline:\n" + w.timeline()
    lines = [l for l in w.timeline(200).split("\n") if any(k in l for k in ("grants", "FREEZES", "STALE"))]
    return "naive lock, scripted freeze of c0 (seed 1), reproduced exactly:\n" + "\n".join(lines) + "\nresult: " + bad


# =============================================================================
# Milestone 3: fencing at the storage
# =============================================================================
def m3():
    g = mod.FenceGuard()
    assert g.admit(5) is True and g.admit(4) is False, "after seeing token 5, token 4 must be refused"
    assert g.admit(5) is True, "the same token again is fine (the holder keeps writing): compare with <, not <="
    assert g.admit(6) is True and g.admit(5) is False, "6 raises the bar; 5 is now stale"
    st = mod.Storage(fenced=True)
    assert st.read(3) == (True, 0)
    assert st.write(3, 10) is True
    assert st.write(2, 99) is False and st.value == 10, "a stale write must be refused AND change nothing"
    assert st.read(2) == (False, None), "a stale READ is refused too: the new holder's first read is what raises the bar"
    assert st.read(4) == (True, 10) and st.write(3, 77) is False, "a read with token 4 announces token 4: a late write with 3 must now fail"
    # the same scripted accident, now fenced
    w = mod.build_world(1, fenced=True, **SCRIPT).run()
    assert w.finished(), "all clients should finish\n" + w.timeline()
    assert w.store.rejected >= 1, "c0's write with token 1 should have been rejected. Timeline:\n" + w.timeline()
    assert w.corrupted() is None, "fenced storage must not lose updates. Timeline:\n" + w.timeline()
    assert w.store.storage.value == 9 and w.store.acked == 9, f"expected 9 increments in all, got value {w.store.storage.value}, acked {w.store.acked}"
    # hundreds of seeds of everything going wrong at once
    t = fuzz(300, fenced=True, **CHAOS)
    assert not t["seeds"], f"{len(t['seeds'])} of 300 seeds went wrong with fencing on. Failing seeds: {t['seeds'][:10]}\n{explain(t)}"
    assert t["stale"] == 0, "the storage accepted a write with a lower token than one it had already seen"
    base = fuzz(300, fenced=False, **CHAOS) if ONLY_SEED is None else {"corrupt": -1}
    if ONLY_SEED is None:
        assert base["corrupt"] >= 30, f"sanity: without fencing at least 30 of 300 chaotic runs should be corrupted, saw {base['corrupt']}"
    return (f"300 chaotic seeds (pauses to 4 s, delays to 3 s, clock drift 3%, 3 clients):\n"
            f"  without fencing: {base['corrupt']} runs lost updates\n"
            f"  with fencing:    0 runs corrupted; the storage refused a stale writer in {t['rejected']} runs")


# =============================================================================
# Milestone 4: a client-side safety margin
# =============================================================================
def m4():
    assert mod.safety_margin(1000, 0.0, 0) == 0, "no drift and no delay needs no margin"
    assert mod.safety_margin(10000, 1e-4, 0) == 2, "a 10 s lease with 100 ppm drift loses about 2 ms (chapter 4)"
    m = mod.safety_margin(1000, 0.05, 20)
    assert 110 <= m <= 125, f"expected about 2*0.05*1000/1.05 + 0.95*20 = 115 ms, got {m}"
    assert mod.safety_margin(1000, 0.05, 20) > mod.safety_margin(1000, 0.01, 20) > mod.safety_margin(1000, 0.01, 0), \
        "the margin must grow with the drift bound and with the message delay"
    out = []
    margin = mod.safety_margin(1000, 0.05, 20)
    # drift is the only problem: the margin removes it completely
    without = fuzz(300, fenced=False, **DRIFT)
    with_m = fuzz(300, fenced=False, margin=margin, **DRIFT)
    assert with_m["stale"] == 0 and with_m["corrupt"] == 0, \
        f"with a {margin} ms margin and only clock drift (5%) no stale write should ever be accepted. Failing seeds {with_m['seeds'][:8]}\n{explain(with_m)}"
    if ONLY_SEED is None:
        assert without["stale"] >= 20, f"sanity: without a margin 5% drift should cause stale writes in many seeds, saw {without['stale']}"
    out.append(f"clock drift only (5%), no fencing, 300 seeds: {without['stale']} runs with a stale write accepted without a margin, "
               f"{with_m['stale']} with a {margin} ms margin")
    # now add occasional freezes: the margin helps but cannot finish the job
    mixed0 = fuzz(300, fenced=False, **MIXED)
    mixed1 = fuzz(300, fenced=False, margin=margin, **MIXED)
    mixed2 = fuzz(300, fenced=True, margin=margin, **MIXED)
    if ONLY_SEED is None:
        assert mixed1["corrupt"] > 0, "a freeze after the lease check cannot be prevented by a margin: some corruption must remain"
        assert mixed1["corrupt"] < mixed0["corrupt"], f"the margin should remove the drift-caused corruption ({mixed1['corrupt']} vs {mixed0['corrupt']})"
    assert mixed2["corrupt"] == 0 and mixed2["stale"] == 0, f"the margin PLUS fencing must be safe. Seeds {mixed2['seeds'][:8]}\n{explain(mixed2)}"
    out.append(f"drift plus rare freezes (0.3% of steps): corrupted runs: no margin {mixed0['corrupt']}, margin only {mixed1['corrupt']}, margin + fencing {mixed2['corrupt']}")
    return "\n".join(out)


# =============================================================================
# Milestone 5: a leader's log
# =============================================================================
def m5():
    log = mod.FencedLog(fenced=True)
    assert log.read(2) == (True, 0)
    assert log.write(2, 1) is True and log.entries == [(2, 1)], "append stores (term, entry)"
    assert log.write(1, 2) is False and log.entries == [(2, 1)], "a deposed leader (term 1) must be refused and the log left alone"
    assert log.read(1) == (False, None)
    assert log.read(3) == (True, 1) and log.write(2, 5) is False, "a new leader's first read must raise the bar to term 3"
    plain = mod.FencedLog(fenced=False)
    plain.write(2, 1)
    assert plain.write(1, 2) is True, "with fenced=False the log accepts any term"
    # the deposed leader, scripted
    w = mod.build_world(1, fenced=False, store="log", **SCRIPT).run()
    bad = w.corrupted()
    assert bad, "without fencing, the deposed leader's late append should have damaged the log. Timeline:\n" + w.timeline()
    w = mod.build_world(1, fenced=True, store="log", **SCRIPT).run()
    assert w.finished() and w.corrupted() is None, "with term fencing the log must stay 1, 2, 3, ... \n" + w.timeline()
    assert w.store.rejected >= 1, "the deposed leader's append should have been refused. Timeline:\n" + w.timeline()
    assert [t for t, _ in w.store.storage.entries] == sorted(t for t, _ in w.store.storage.entries), "terms must never go backwards"
    terms = sorted({t for t, _ in w.store.storage.entries})
    t = fuzz(300, fenced=True, store="log", **CHAOS)
    assert not t["seeds"], f"{len(t['seeds'])} of 300 seeds damaged the log with fencing on. Failing seeds: {t['seeds'][:10]}\n{explain(t)}"
    base = fuzz(300, fenced=False, store="log", **CHAOS) if ONLY_SEED is None else {"corrupt": -1}
    if ONLY_SEED is None:
        assert base["corrupt"] >= 30, f"sanity: an unfenced log should break in many chaotic runs, saw {base['corrupt']}"
    return (f"scripted: deposed leader (term 1) refused after term 2 took over; log terms {terms}, entries 1..{len(w.store.storage.entries)}\n"
            f"300 chaotic seeds: unfenced log damaged in {base['corrupt']}, fenced log damaged in 0 "
            f"(a deposed leader was refused in {t['rejected']} runs)")


print(f"Lab 2 checks against {target}.py\n")
check(1, "Milestone 1: a lock service with leases and tokens", m1)
check(2, "Milestone 2: pauses, drift, and the unsafe naive lock", m2)
check(3, "Milestone 3: fencing at the storage", m3)
check(4, "Milestone 4: a client-side safety margin", m4)
check(5, "Milestone 5 (optional): a leader's log fenced by its term", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
