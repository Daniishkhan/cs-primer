"""Self-check for Lab 6: A Durable Job Scheduler.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 17    # milestone 4, replaying ONLY seed 17

Everything is simulated: time is a number the tests pass in or the event loop advances, the disk is a Python
object that can lose power in the middle of a write, every random draw comes from a seeded random.Random,
nothing sleeps and nothing touches a file or a socket. The check computes its own expected answers (a model of
what was acknowledged, shadow copies of the leases) and reads the durable log directly, so a bug in your code
cannot hide a bug in the reference data. A failing property prints its seed and the command that replays it.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import collections
import importlib
import json
import math
import os
import random
import sys
import time

T0 = time.time()
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


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def replay(n, seed):
    return f"(replay: python3 check.py {target} {n} {seed})"


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
        print(f"  ✘ {name}: " + str(e).replace("\n", "\n      "))
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: crashed with {type(e).__name__}: {e}  [in {where}]")
        results.append(False)


def log_records(disk):
    """The records in the durable log, decoded by THIS FILE (not by your decode_record)."""
    import zlib
    out = []
    for line in disk.durable:
        crc, _, body = line.partition(" ")
        if len(crc) == 8 and f"{zlib.crc32(body.encode()):08x}" == crc:
            out.append(json.loads(body))
    return out


# ---------------------------------------------------------------------------------------------
def m1():
    # records: round trip, and every proper prefix of a line is rejected
    rec = {"set": {"a": 1, "b": [1, 2, {"c": None}]}, "del": ["z"]}
    line = mod.encode_record(rec)
    assert mod.decode_record(line) == rec, "decode_record(encode_record(r)) must give r back"
    assert len(line.partition(" ")[0]) == 8, "a line is '<8 hex digits of crc32> <json>'"
    for cut in range(0, len(line)):
        assert mod.decode_record(line[:cut]) is None, f"a line cut short at {cut} of {len(line)} characters must be rejected (a torn write is not a record): {line[:cut]!r}"
    flipped = mod.encode_record({"set": {"a": 1}, "del": []}).replace('"a":1', '"a":2')
    assert json.loads(flipped.split(" ", 1)[1]) == {"set": {"a": 2}, "del": []} and mod.decode_record(flipped) is None, "a line whose body was changed but is still valid JSON must fail its checksum"
    assert mod.decode_record("") is None and mod.decode_record("zzzzzzzz not json") is None, "garbage lines must be rejected, not crash"
    # basic LogDict
    d = mod.Disk()
    db = mod.LogDict(d)
    db.put("a", 1)
    db.put_many({"b": 2, "c": {"x": [1]}}, ["a"])
    assert db.get("a") is None and db.get("b") == 2 and "c" in db and db.items() == [("b", 2), ("c", {"x": [1]})], f"put / put_many / delete semantics wrong: {db.items()}"
    assert len(d.durable) == 2 and not d.cache, f"every change is one record, fsynced: expected 2 durable lines, found {len(d.durable)} (+{len(d.cache)} in the cache)"
    db2 = mod.LogDict(d)
    assert db2.items() == db.items(), "a LogDict opened on the same Disk must recover the same contents"
    # a torn tail is cut off on recovery, so that later writes are not lost behind it
    d = mod.Disk()
    db = mod.LogDict(d)
    for i in range(5):
        db.put(f"k{i}", i)
    d.durable.append(mod.encode_record({"set": {"z": 1}, "del": []})[:-4])
    db = mod.LogDict(d)
    assert sorted(db.data) == [f"k{i}" for i in range(5)], f"recovery must stop at the torn line: got {sorted(db.data)}"
    assert len(d.durable) == 5, f"recovery must truncate the torn line off the disk (disk.truncate): {len(d.durable)} lines remain"
    db.put("after", 1)
    assert "after" in mod.LogDict(d), "a record written after recovery was lost: the torn line was not truncated, so replay stopped before it"
    d = mod.Disk()
    db = mod.LogDict(d)
    db.put("k0", 0)
    d.durable.append("00000000 {\"set\":{\"bad\":1}}")
    d.durable.append(mod.encode_record({"set": {"late": 1}, "del": []}))
    db = mod.LogDict(d)
    assert db.data == {"k0": 0} and len(d.durable) == 1, f"replay stops at the first damaged line and trusts nothing after it; got {db.data}, {len(d.durable)} lines left"
    # crash anywhere: what was acknowledged survives; the interrupted write is all-or-nothing
    S = seeds(range(1, 61))
    crashes = 0
    for s in S:
        rng = random.Random(s)
        disk = mod.Disk()
        db = mod.LogDict(disk)
        model = {}
        for step in range(80):
            k = f"k{rng.randrange(8)}"
            r = rng.random()
            if r < 0.5:
                sets, dels = {k: step}, []
            elif r < 0.75:
                sets, dels = {k: step, f"k{rng.randrange(8)}": -step}, []
            else:
                sets, dels = {}, [k]
            after = dict(model)
            after.update(sets)
            for x in dels:
                after.pop(x, None)
            if rng.random() < 0.3:
                disk.fail_at = rng.randrange(1, 4)
            try:
                db.put_many(sets, dels)
                disk.fail_at = None
                model = after
                assert db.data == model, f"seed {s} step {step}: after put_many the in-memory dict is {db.data}, expected {model} {replay(1, s)}"
            except mod.Crash:
                crashes += 1
                disk.fail_at = None
                assert db.data == model, f"seed {s} step {step}: put_many raised Crash but the in-memory dict already changed ({db.data} vs {model}): apply to memory only AFTER the record is durable {replay(1, s)}"
                disk.crash(rng)
                db = mod.LogDict(disk)
                assert db.data == model or db.data == after, f"seed {s} step {step}: after a crash during put_many({sets}, {dels}) the recovered dict must be the old state or the new one, never a mixture.\n  old {model}\n  new {after}\n  got {db.data} {replay(1, s)}"
                model = dict(db.data)
            if rng.random() < 0.1:
                disk.crash(rng)
                db = mod.LogDict(disk)
                assert db.data == model, f"seed {s} step {step}: a power loss between operations lost or invented data: {db.data} vs {model} {replay(1, s)}"
        assert mod.LogDict(disk).data == model, f"seed {s}: final reopen differs from the acknowledged state {replay(1, s)}"
        assert all(mod.decode_record(x) is not None for x in disk.durable), f"seed {s}: the durable log still contains a damaged line after recovery {replay(1, s)}"
    # the due-time index against a model
    for s in seeds(range(1, 31)):
        rng = random.Random(1000 + s)
        ix = mod.DueIndex()
        model = {}
        for step in range(300):
            r = rng.random()
            j = f"j{rng.randrange(25)}"
            if r < 0.5:
                t = round(rng.uniform(0, 50), 1)
                ix.add(j, t)
                model[j] = t
            elif r < 0.65:
                ix.discard(j)
                model.pop(j, None)
            else:
                now = round(rng.uniform(0, 55), 1)
                want = sorted((t, x) for x, t in model.items() if t <= now)
                assert ix.ready(now) == [x for _, x in want], f"seed {s} step {step}: ready({now}) = {ix.ready(now)}, expected {[x for _, x in want]} {replay(1, s)}"
                got = ix.pop_ready(now)
                if want:
                    assert got == want[0][1], f"seed {s} step {step}: pop_ready({now}) = {got}, expected {want[0][1]} (earliest ready time, then id) {replay(1, s)}"
                    del model[got]
                else:
                    assert got is None, f"seed {s} step {step}: pop_ready({now}) = {got} but nothing is ready (a job must never come out early) {replay(1, s)}"
            assert len(ix) == len(model), f"seed {s} step {step}: len(index) = {len(ix)}, expected {len(model)} (re-adding a job must replace its time, not duplicate it) {replay(1, s)}"
    # the job store: idempotent submit, durable, index rebuilt after a restart
    for s in seeds(range(1, 41)):
        rng = random.Random(2000 + s)
        disk = mod.Disk()
        st = mod.JobStore(disk, s)
        acked, maybe = {}, {}
        for i in range(50):
            jid = f"j{rng.randrange(35)}"
            due = round(rng.uniform(0, 100), 1)
            if rng.random() < 0.3:
                disk.fail_at = rng.randrange(1, 4)
            try:
                created = st.submit(jid, due, {"n": i}, max_attempts=3)
                disk.fail_at = None
                assert created == (jid not in acked and jid not in maybe), f"seed {s}: submit({jid!r}) returned {created}; it must be True the first time and False for an existing id {replay(1, s)}"
                if created:
                    acked[jid] = due
            except mod.Crash:
                disk.fail_at = None
                disk.crash(rng)
                st = mod.JobStore(disk, s)
                maybe.pop(jid, None)
                got = st.get(jid)
                if got is not None and jid not in acked:
                    assert got["due"] == due, f"seed {s}: the recovered record of {jid!r} has due {got['due']}, expected {due} {replay(1, s)}"
                    acked[jid] = due                          # it was durable before the crash: allowed
        st = mod.JobStore(disk, s)                            # a clean restart
        for jid, due in acked.items():
            rec = st.get(jid)
            assert rec is not None and rec["due"] == due and rec["state"] == "queued" and rec["attempts"] == 0 and rec["fence"] == 0, f"seed {s}: job {jid!r} is missing or wrong after a restart: {rec} {replay(1, s)}"
        for now in (0.0, 10.0, 33.3, 70.0, 100.0):
            want = [j for _, j in sorted((d, j) for j, d in acked.items() if d <= now)]
            assert st.ready(now) == want, f"seed {s}: ready({now}) after a restart is {st.ready(now)}, expected {want} (due-time order, none early, none missing) {replay(1, s)}"
    return (f"records: every proper prefix of a log line is rejected, a flipped character fails the checksum; torn tails are truncated away on recovery\n"
            f"{len(S)} seeds x 80 operations with {crashes} injected crashes: acknowledged writes always survive, the interrupted write is all-or-nothing\n"
            f"DueIndex == a model on 30 seeds; JobStore.submit idempotent and durable, ready(now) in (due, id) order after crashes and restarts (40 seeds)")


# ---------------------------------------------------------------------------------------------
def m2():
    L = 3.0
    d = mod.Disk()
    st = mod.JobStore(d, 1)
    st.submit("a", 8.0, {"x": 1})
    st.submit("b", 8.0, {"x": 2})
    st.submit("c", 4.0, {"x": 3})
    assert st.claim(3.99, "w1", L) is None, "nothing is due at 3.99: a job must never be claimed early"
    c1 = st.claim(4.0, "w1", L)
    assert c1 and c1["id"] == "c" and c1["fence"] == 1 and c1["attempts"] == 1 and c1["state"] == "running" and c1["owner"] == "w1" and c1["lease_until"] == 7.0, f"first claim of c at t=4: expected fence 1, attempts 1, lease_until 7.0, got {c1}"
    assert st.claim(5.0, "w2", L) is None, "c is leased until 7.0 and a and b are not due: nothing to claim at 5.0"
    assert st.heartbeat("c", 1, 6.0, L) is True, "heartbeat with the current fence must succeed"
    assert [st.claim(8.0, "w2", L)["id"], st.claim(8.0, "w3", L)["id"]] == ["a", "b"], "jobs due at the same time are claimed in id order, one claim each (c's lease now runs to 9.0)"
    assert st.claim(8.99, "w4", L) is None, "after the heartbeat at t=6 the lease of c runs to 9.0: not claimable at 8.99"
    c2 = st.claim(9.0, "w4", L)
    assert c2 and c2["id"] == "c" and c2["fence"] == 2 and c2["attempts"] == 2, f"an expired lease (lease_until <= now) makes the job claimable again with fence + 1; got {c2}"
    # the stale worker is fenced out
    assert st.heartbeat("c", 1, 9.5, L) is False, "w1's heartbeat with the OLD fence must be refused"
    assert st.complete("c", 1) is False, "w1's complete with the OLD fence must be refused: that is the whole point of the token"
    assert st.get("c")["state"] == "running" and st.get("c")["owner"] == "w4", "a refused call must change nothing"
    assert st.complete("c", 2) is True and st.get("c")["state"] == "done", "the current holder can complete"
    assert st.complete("c", 2) is False and st.heartbeat("c", 2, 9.6, L) is False, "a finished job accepts nothing further"
    c3 = st.claim(1000.0, "w5", L)
    assert c3["id"] == "a" and c3["fence"] == 2, f"a and b were never completed: their leases (to 11.0) expired and a is claimed again with fence 2; got {c3}"
    # fences and leases survive a crash
    st2 = mod.JobStore(d, 1)
    assert st2.get("a")["fence"] == 2 and st2.get("a")["lease_until"] == 1003.0 and st2.get("c")["state"] == "done", "fence, lease and state are durable"
    assert st2.claim(1001.0, "w9", L)["id"] == "b" and st2.claim(1002.0, "w9", L) is None, "after a restart the running lease of a (until 1003.0) must still protect it"
    # heartbeats and claims interrupted by a crash leave a consistent record
    # random interleavings against a shadow model
    S = seeds(range(1, 61))
    steps = 0
    for s in S:
        rng = random.Random(s)
        disk = mod.Disk()
        st = mod.JobStore(disk, s)
        ready = {}
        for i in range(15):
            due = round(rng.uniform(0, 10), 1)
            st.submit(f"j{i}", due, {}, max_attempts=10 ** 6)
            ready[f"j{i}"] = due
        last_fence, finished, completions = {}, set(), collections.Counter()
        held = {}
        now = 0.0
        for step in range(400):
            steps += 1
            now = round(now + rng.choice((0, 0.1, 0.5, 1.0, 2.0, 4.0)), 3)
            w = rng.randrange(4)
            r = rng.random()
            if rng.random() < 0.04:
                disk.crash(rng)
                st = mod.JobStore(disk, s)
            if r < 0.4:
                want = sorted((t, j) for j, t in ready.items() if t <= now)
                rec = st.claim(now, f"w{w}", L)
                if not want:
                    assert rec is None, f"seed {s} step {step}: claim at {now} returned {rec['id']}, but nothing is claimable (early, or a live lease was stolen) {replay(2, s)}"
                else:
                    assert rec is not None and rec["id"] == want[0][1], f"seed {s} step {step}: claim at {now} returned {rec and rec['id']}, expected {want[0][1]} (earliest ready time, then id; ready: {want[:3]}) {replay(2, s)}"
                    jid = rec["id"]
                    assert rec["fence"] == last_fence.get(jid, 0) + 1, f"seed {s} step {step}: fence for {jid} is {rec['fence']}, expected {last_fence.get(jid, 0) + 1}: the token must rise by exactly one per claim and survive restarts {replay(2, s)}"
                    last_fence[jid] = rec["fence"]
                    ready[jid] = now + L
                    held[w] = (jid, rec["fence"])
            elif r < 0.6 and held:
                w2 = rng.choice(sorted(held))
                jid, f = held[w2]
                ok = st.heartbeat(jid, f, now, L)
                valid = last_fence.get(jid) == f and jid not in finished
                assert ok == valid, f"seed {s} step {step}: heartbeat({jid}, fence {f}) returned {ok}; the current fence is {last_fence.get(jid)} and finished={jid in finished} {replay(2, s)}"
                if ok:
                    ready[jid] = now + L
            elif r < 0.85 and held:
                w2 = rng.choice(sorted(held))
                jid, f = held[w2]
                ok = st.complete(jid, f)
                valid = last_fence.get(jid) == f and jid not in finished
                assert ok == valid, f"seed {s} step {step}: complete({jid}, fence {f}) returned {ok}; the current fence is {last_fence.get(jid)} and finished={jid in finished}: a stale worker must be refused, the current one accepted, exactly once {replay(2, s)}"
                if ok:
                    finished.add(jid)
                    completions[jid] += 1
                    ready.pop(jid, None)
        now += 100.0
        while True:
            rec = st.claim(now, "drain", L)
            if rec is None:
                break
            assert st.complete(rec["id"], rec["fence"]), f"seed {s}: draining: complete of a fresh claim failed {replay(2, s)}"
            finished.add(rec["id"])
            completions[rec["id"]] += 1
        assert len(finished) == 15 and all(v == 1 for v in completions.values()), f"seed {s}: after draining every job must be done exactly once; done {len(finished)}/15, completions {dict(completions)} {replay(2, s)}"
    return ("a hand-written story (claim, heartbeat, expiry, takeover, stale worker refused, restart) behaves exactly as specified\n"
            f"{len(S)} random interleavings ({steps:,} steps, 4 workers, restarts included) against a shadow model: claims come in (ready time, id) order, never early,\n"
            "never while a lease is live; fences rise by one per claim; stale heartbeats and completes are refused; each job completes exactly once")


# ---------------------------------------------------------------------------------------------
def m3():
    assert mod.backoff_delay(1, 2.0, 100.0, 0.5) == 1.0 and mod.backoff_delay(3, 2.0, 100.0, 1.0) == 8.0 and mod.backoff_delay(10, 2.0, 100.0, 0.5) == 50.0 and mod.backoff_delay(4, 1.0, 5.0, 0.0) == 0.0, \
        "backoff_delay(attempt, base, cap, u) = u * min(cap, base * 2**(attempt-1)): (1, 2, 100, .5) -> 1.0, (3, 2, 100, 1.0) -> 8.0, (10, 2, 100, .5) -> 50.0"
    # a retry: state, due, owner, error
    d = mod.Disk()
    st = mod.JobStore(d, 5)
    st.submit("j", 0.0, {}, max_attempts=3, base=2.0, cap=20.0)
    c = st.claim(0.0, "w", 5.0)
    assert st.fail("j", c["fence"] + 1, 1.0, "boom") == "fenced" and st.get("j")["state"] == "running", "fail with a stale/wrong fence must return 'fenced' and change nothing"
    assert st.fail("j", c["fence"], 1.0, "boom") == "retry"
    r = st.get("j")
    top = 2.0 * 2 ** 0
    assert r["state"] == "queued" and r["owner"] is None and r["error"] == "boom" and 1.0 <= r["due"] <= 1.0 + top, f"after the 1st failure: queued, no owner, error kept, due in [1.0, {1.0 + top}]; got {r}"
    assert st.fail("j", c["fence"], 2.0, "again") == "fenced", "a second failure report for the same claim is stale: the job is no longer running"
    # attempts exhausted -> dead letter
    for n in (2, 3):
        c = st.claim(100.0 * n, "w", 5.0)
        assert c["attempts"] == n, f"claim #{n} should have attempts == {n}, got {c['attempts']}"
        res = st.fail("j", c["fence"], 100.0 * n, "e")
        assert res == ("retry" if n < 3 else "dead"), f"failure #{n} of max_attempts=3 should give {'retry' if n < 3 else 'dead'}, got {res!r}"
    assert st.get("j")["state"] == "dead" and st.dead_letters() == ["j"] and st.claim(1e9, "w", 5.0) is None, "a dead job is listed in dead_letters() and is never claimed"
    assert st.redrive("nope", 0.0) is False and st.redrive("j", 5000.0) is True, "redrive: True for a dead job, False otherwise"
    rr = st.get("j")
    assert rr["state"] == "queued" and rr["attempts"] == 0 and rr["due"] == 5000.0 and rr["error"] is None and st.dead_letters() == [], f"redrive resets attempts and due: {rr}"
    assert st.redrive("j", 5000.0) is False, "a queued job cannot be redriven"
    # a permanent error skips the retries
    st = mod.JobStore(mod.Disk(), 3)
    st.submit("p", 0.0, {}, max_attempts=9)
    cp = st.claim(0.0, "w", 5.0)
    assert st.fail("p", cp["fence"], 0.0, "bad payload", retryable=False) == "dead" and st.dead_letters() == ["p"], "retryable=False goes straight to the dead-letter queue"
    # poison job: every worker dies, nobody ever reports. Each CLAIM counts as an attempt.
    d = mod.Disk()
    st = mod.JobStore(d, 2)
    st.submit("poison", 0.0, {}, max_attempts=3)
    st.submit("z-fine", 15.0, {}, max_attempts=3)
    seen = []
    t = 0.0
    for i in range(3):
        c = st.claim(t, "w", 5.0)
        seen.append(c["id"] if c else None)
        t += 5.0
    assert seen == ["poison", "poison", "poison"], f"the poison job is handed out max_attempts times: {seen}"
    c = st.claim(t, "w", 5.0)
    assert c is not None and c["id"] == "z-fine", f"after its 3rd lease expires the poison job must go to the dead-letter queue and must not block the next job; claim returned {c and c['id']}"
    assert st.dead_letters() == ["poison"] and st.get("poison")["attempts"] == 3, f"poison: dead after 3 claims, got {st.dead_letters()}, attempts {st.get('poison')['attempts']}"
    # backoff statistics: bounded, capped, spread out, deterministic
    N = 300
    base, cap = 1.0, 30.0
    per = collections.defaultdict(list)
    disk = mod.Disk()
    st = mod.JobStore(disk, 99)
    for i in range(N):
        st.submit(f"b{i}", 0.0, {}, max_attempts=12, base=base, cap=cap)
    for a in range(1, 9):
        T = 1000.0 * a
        claimed = [st.claim(T, "w", 1.0) for _ in range(N)]
        assert all(c is not None and c["attempts"] == a for c in claimed), f"attempt {a}: all {N} jobs should be claimable at t={T} with attempts == {a}"
        for c in claimed:
            assert st.fail(c["id"], c["fence"], T, "x") == "retry"
            per[a].append(st.get(c["id"])["due"] - T)
    for a in range(1, 9):
        hi = min(cap, base * 2 ** (a - 1))
        xs = per[a]
        assert all(0 <= x <= hi + 1e-9 for x in xs), f"attempt {a}: every delay must lie in [0, min(cap, base*2^(a-1))] = [0, {hi}]; saw {min(xs):.2f}..{max(xs):.2f}"
        mean = sum(xs) / N
        assert 0.4 * hi <= mean <= 0.6 * hi, f"attempt {a}: full jitter averages half of the ceiling ({hi / 2:.2f}); the mean was {mean:.2f}"
        assert max(xs) > 0.85 * hi and len({round(x, 6) for x in xs}) > 0.97 * N, f"attempt {a}: delays should spread across [0, {hi}] (max {max(xs):.2f}, {len({round(x, 6) for x in xs})} distinct of {N})"
    herd = collections.Counter(int(x / 0.5) for x in per[3])
    assert max(herd.values()) <= 3 * N / (4.0 / 0.5), f"attempt 3: {N} jobs failing in the same instant must not retry in lock-step; the busiest half-second holds {max(herd.values())} of {N}"
    other = mod.JobStore(mod.Disk(), 99)
    other.submit("b0", 0.0, {}, max_attempts=12, base=base, cap=cap)
    c = other.claim(0.0, "w", 1.0)
    other.fail("b0", c["fence"], 0.0, "x")
    assert abs(other.get("b0")["due"] - (per[1][0])) < 1e-9, "the jitter for (job, attempt) must be reproducible (JobStore.jitter), not drawn from global random state"
    # the chaos harness with a poison job and a permanent failure
    S = seeds(range(1, 13))
    retries = 0
    for s in S:
        out = mod.run_chaos(s, mod.handle_deposit_unsafe, special=("poison", "permanent"))
        stt = out["store"]
        assert stt.dead_letters() == ["x-permanent", "x-poison"], f"seed {s}: the dead-letter queue should hold exactly the poison and the permanent job, got {stt.dead_letters()} {replay(3, s)}"
        for j in out["specs"]:
            if j not in out["bad"]:
                assert stt.get(j)["state"] == "done", f"seed {s}: ordinary job {j} is {stt.get(j)['state']}, not done: retries must get every healthy job through {replay(3, s)}"
        perm = [e[4] for e in out["log"] if e[1] == "fail" and e[2] == "x-permanent"]
        assert perm and "retry" not in perm, f"seed {s}: a permanent error must go straight to the dead-letter queue, never to a retry; fail() results for it: {perm} {replay(3, s)}"
        assert stt.get("x-poison")["attempts"] == 4, f"seed {s}: the poison job should be claimed exactly max_attempts=4 times before it is dead-lettered, got {stt.get('x-poison')['attempts']} {replay(3, s)}"
        retries += sum(1 for e in out["log"] if e[1] == "fail" and e[4] == "retry")
    return (f"backoff = full jitter in [0, min(cap, base*2^(a-1))]: {N} jobs x 8 attempts stay in bounds, average half the ceiling, saturate at the cap, do not retry in lock-step; reproducible per (job, attempt)\n"
            f"max_attempts -> dead letter; retryable=False -> dead at once; redrive resets; poison jobs (nobody reports) die after max_attempts CLAIMS without blocking others\n"
            f"{len(S)} chaos runs with a poison job, a permanent failure and flaky handlers ({retries} retries): dead-letter queue exactly right, every healthy job done")


# ---------------------------------------------------------------------------------------------
def totals(specs):
    t = collections.Counter()
    for sp in specs.values():
        t[sp["acct"]] += sp["amount"]
    return t


def m4():
    # the ledger alone: idempotent, atomic with the effect, crash-safe
    bank = mod.Bank(mod.Disk())
    assert bank.deposit("k1", "a", 10) is True and bank.deposit("k1", "a", 10) is False and bank.balance("a") == 10, "the same key must pay once: deposit('k1') twice gives True then False, balance 10"
    assert bank.deposit("k2", "a", 5) is True and bank.balance("a") == 15 and bank.ledger.done("k1") and not bank.ledger.done("k9"), "a different key pays again"
    for s in seeds(range(1, 61)):
        rng = random.Random(s)
        disk = mod.Disk()
        bank = mod.Bank(disk)
        keys = [f"k{i}" for i in range(25)]
        for _ in range(120):
            k = rng.choice(keys)
            if rng.random() < 0.35:
                disk.fail_at = rng.randrange(1, 4)
            try:
                bank.deposit(k, "acct", 1)
                disk.fail_at = None
            except mod.Crash:
                disk.fail_at = None
                disk.crash(rng)
                bank = mod.Bank(disk)
            n_ledger = sum(1 for key in bank.db.data if key.startswith("ledger:"))
            assert bank.balance("acct") == n_ledger, f"seed {s}: balance {bank.balance('acct')} but {n_ledger} ledger entries: the effect and its ledger entry must be ONE atomic write (a crash tore them apart) {replay(4, s)}"
        for k in keys:
            bank.deposit(k, "acct", 1)
        assert bank.balance("acct") == 25 and sum(1 for key in bank.db.data if key.startswith("ledger:")) == 25, f"seed {s}: after retrying every key until it succeeded the balance must be exactly 25, got {bank.balance('acct')} {replay(4, s)}"
    # chaos: duplicate executions, stale workers, crashes everywhere; the effect happens once per job
    S = seeds(range(1, 301))
    dup_runs = execs = total_exec = stale = lost_ack = 0
    for s in S:
        out = mod.run_chaos(s, mod.handle_deposit)
        st, bank, specs, log = out["store"], out["bank"], out["specs"], out["log"]
        bad = [j for j in specs if st.get(j)["state"] != "done"]
        assert not bad, f"seed {s}: jobs not done after the chaos stopped: {bad[:4]} (states {[st.get(j)['state'] for j in bad[:4]]}) {replay(4, s)}"
        want = totals(specs)
        for acct, amt in want.items():
            assert bank.balance(acct) == amt, f"seed {s}: {acct} holds {bank.balance(acct)}, expected exactly {amt}: some job's effect happened {'twice or more' if bank.balance(acct) > amt else 'zero times'}. Is the ledger key the same on every attempt? {replay(4, s)}"
        ledger = sorted(k[7:] for k in bank.db.data if k.startswith("ledger:"))
        assert ledger == sorted(specs), f"seed {s}: the ledger holds {ledger[:5]}..., expected one entry per job id, {sorted(specs)[:5]}... {replay(4, s)}"
        won = collections.Counter(e[2] for e in log if e[1] == "complete" and e[4] is True)
        assert set(won) <= set(specs) and all(v == 1 for v in won.values()), f"seed {s}: no job may be completed successfully twice (a stale fence must be refused); completions {dict(won)} {replay(4, s)}"
        runs = collections.Counter(e[2] for e in log if e[1] == "exec")
        total_exec += sum(runs.values())
        dup_runs += any(v > 1 for v in runs.values())
        execs += sum(v - 1 for v in runs.values() if v > 1)
        stale += sum(1 for e in log if e[1] == "complete" and e[4] is False)
        lost_ack += sum(1 for e in log if e[1] == "store-crash")
    assert dup_runs >= len(S) * 0.2 or ONLY_SEED is not None, f"internal: the chaos only produced a duplicate execution in {dup_runs}/{len(S)} runs; the test would prove little"
    # the check has teeth: the same chaos breaks handlers without a ledger, and with a ledger keyed by attempt
    broke = {}
    for name, h in (("no ledger", mod.handle_deposit_unsafe), ("ledger keyed by job+attempt", mod.handle_deposit_attempt_key)):
        n = 0
        for s in seeds(range(1, 101)):
            out = mod.run_chaos(s, h)
            want = totals(out["specs"])
            n += any(out["bank"].balance(a) != v for a, v in want.items())
        broke[name] = n
        assert n >= 10 or ONLY_SEED is not None, f"internal: a handler with {name} survived {100 - n}/100 chaos runs; the chaos is too gentle"
    return (f"ledger: same key pays once; effect + ledger entry are one atomic record (60 seeds x 120 deposits with injected crashes: balance == ledger entries, always)\n"
            f"{len(S)} chaos runs (workers die before and after the effect, freeze past their lease and run again, store and bank lose power): {total_exec} handler executions for {len(S) * 12} jobs\n"
            f"({execs} duplicate executions in {dup_runs} runs, {stale} stale completes refused, {lost_ack} store crashes): every job done, no job completed twice, its effect applied EXACTLY once\n"
            f"the same chaos breaks the naive versions: no ledger corrupts {broke['no ledger']}/100 runs, a ledger keyed by job+attempt {broke['ledger keyed by job+attempt']}/100")


# ---------------------------------------------------------------------------------------------
def m5():
    # fire times
    assert mod.fire_times(20.0, 3.0, -1e-6, 70.0) == [3.0, 23.0, 43.0, 63.0], f"fire_times(20, 3, -1e-6, 70) -> {mod.fire_times(20.0, 3.0, -1e-6, 70.0)}"
    assert mod.fire_times(20.0, 3.0, 23.0, 63.0) == [43.0, 63.0], "after < t <= upto: 23 is excluded, 63 included"
    assert mod.fire_times(60.0, 10.0, 14.999999, 140.0) == [70.0, 130.0] and mod.fire_times(60.0, 10.0, 100.0, 100.0) == [], "start offsets and empty ranges"
    # jitter: stable, in range, spreads a herd
    assert mod.cron_jitter("x", 0) == 0.0
    spread = 300.0
    offs = [mod.cron_jitter(f"cron-{i}", spread) for i in range(3000)]
    assert all(0 <= o < spread for o in offs) and offs == [mod.cron_jitter(f"cron-{i}", spread) for i in range(3000)], "jitter must lie in [0, spread) and be the same every time for a given cron id (stable, not re-drawn each period)"
    per_s = collections.Counter(int(o) for o in offs)
    deciles = collections.Counter(int(o / (spread / 10)) for o in offs)
    assert max(per_s.values()) <= 3 * 3000 / spread, f"3000 crons all scheduled at :00 with {spread:.0f} s of jitter: the busiest second starts {max(per_s.values())} (mean {3000 / spread:.0f}); expected at most {3 * 3000 / spread:.0f}"
    assert all(0.07 * 3000 <= v <= 0.13 * 3000 for v in deciles.values()) and len(deciles) == 10, f"jitter should be uniform over the spread; decile counts {sorted(deciles.items())}"
    assert len({mod.cron_jitter(f"cron-{i}", spread) for i in range(3000)}) > 2900, "different crons must get different offsets"
    # fire_cron: exactly once, fenced, atomic with the cursor
    disk = mod.Disk()
    st = mod.JobStore(disk, 1)
    assert st.cursor("c", -1.0) == -1.0
    assert st.fire_cron("c", 20.0, 22.5, {"p": 1}, 1) == "created", "first firing creates the job"
    j = st.get("c@20.0")
    assert j and j["due"] == 22.5 and j["state"] == "queued" and st.cursor("c", -1.0) == 20.0 and j["key"] == "c@20.0", f"the job id is '<cron>@<fire time>', due = the given due, cursor moved: {j}"
    assert st.fire_cron("c", 20.0, 22.5, {"p": 1}, 1) == "duplicate" and st.fire_cron("c", 20.0, 22.5, {"p": 1}, 5) == "duplicate", "the same (cron, fire time) never creates a second job, whatever the token"
    assert st.fire_cron("c", 40.0, 40.0, {}, 5) == "created", "a higher token is accepted"
    assert st.fire_cron("c", 60.0, 60.0, {}, 4) == "fenced" and st.get("c@60.0") is None and st.cursor("c", -1.0) == 40.0, "a token below the highest seen is a replaced leader: 'fenced', nothing written"
    st2 = mod.JobStore(disk, 1)
    assert st2.get("c@40.0") and st2.cursor("c", -1.0) == 40.0 and st2.fire_cron("c", 60.0, 60.0, {}, 4) == "fenced", "the highest token survives a restart"
    for s in seeds(range(1, 41)):
        rng = random.Random(s)
        disk = mod.Disk()
        st = mod.JobStore(disk, s)
        for k in range(1, 30):
            if rng.random() < 0.4:
                disk.fail_at = rng.randrange(1, 4)
            try:
                st.fire_cron("c", float(k), float(k), {}, 1)
                disk.fail_at = None
            except mod.Crash:
                disk.fail_at = None
                disk.crash(rng)
                st = mod.JobStore(disk, s)
                cur = st.cursor("c", 0.0)
                assert (st.get(f"c@{float(k)}") is not None) == (cur == float(k)), f"seed {s}: after a crash during fire_cron the job and the cursor must agree: job exists = {st.get(f'c@{float(k)}') is not None}, cursor = {cur} {replay(5, s)}"
    # three replicas with a leader lease, crashing, freezing and firing late with stale tokens
    S = seeds(range(1, 41))
    zombies = fenced_or_dup = crashes = jobs_total = 0
    for s in S:
        out = mod.run_cron(s, spread=0.0)
        st, crons, H = out["store"], out["crons"], out["horizon"]
        recs = log_records(st.db.disk)
        created = collections.Counter()
        last_tok = 0
        for r in recs:
            for k, v in r.get("set", {}).items():
                if k.startswith("job:"):
                    created[k[4:]] += 1
            tok = r.get("set", {}).get("meta:cron_token")
            if tok is not None:
                assert tok >= last_tok, f"seed {s}: the store accepted token {tok} after {last_tok}: a replaced leader got through {replay(5, s)}"
                last_tok = tok
        assert created and all(v == 1 for v in created.values()), f"seed {s}: these scheduled firings were turned into jobs more than once: {[k for k, v in created.items() if v > 1][:3]} {replay(5, s)}"
        for c in crons:
            want = mod.fire_times(c["period"], c["offset"], c["start"] - 1e-6, H - 60)
            missing = [t for t in want if f"{c['id']}@{t}" not in created]
            assert not missing, f"seed {s}: cron {c['id']} missed {len(missing)} firing(s), e.g. t={missing[0]}: after a leader crash or freeze the next leader must catch up on every missed period {replay(5, s)}"
            for jid in created:
                if jid.startswith(c["id"] + "@"):
                    t = float(jid.split("@")[1])
                    assert t >= c["start"] and abs((t - c["offset"]) / c["period"] - round((t - c["offset"]) / c["period"])) < 1e-9 and t <= H, f"seed {s}: job {jid} is not on the schedule of {c['id']} {replay(5, s)}"
        owners = collections.Counter(e[2] for e in out["log"] if e[1] == "tick" and e[4])
        assert len(owners) >= 1
        zombies += sum(1 for e in out["log"] if e[1] == "zombie")
        fenced_or_dup += sum(1 for e in out["log"] if e[1] == "zombie" and e[4] == 0)
        crashes += sum(1 for e in out["log"] if e[1] in ("crash", "store-crash", "freeze"))
        jobs_total += len(created)
    # the lease is for efficiency: with no faults, exactly one replica does all the work, under one token
    calm = mod.run_cron(3, spread=0.0, chaos=False)
    workers = [r.name for r in calm["replicas"] if r.created > 0]
    assert len(workers) == 1 and calm["lease"].token == 1, f"with no faults one replica should hold the lease the whole time and fire everything; replicas that created jobs: {workers}, lease tokens issued: {calm['lease'].token}. Does tick() check the lease before firing?"
    # catching up after a long absence: every missed period gets its job
    for jump in (130.0, 400.0):
        disk = mod.Disk()
        st = mod.JobStore(disk, 1)
        cr = [{"id": "fast", "period": 20.0, "offset": 3.0, "start": 0.0}, {"id": "slow", "period": 60.0, "offset": 10.0, "start": 15.0}]
        rep = mod.CronReplica("r0", mod.LeaseService(), st, cr)
        rep.tick(1.0)
        rep.tick(jump)
        for c in cr:
            want = mod.fire_times(c["period"], c["offset"], c["start"] - 1e-6, jump)
            have = sorted(float(k[4:].split("@")[1]) for k, _ in st.db.items() if k.startswith("job:" + c["id"] + "@"))
            assert have == want, f"after being away from t=1 to t={jump:.0f}, cron {c['id']} should have one job per missed period {want}, found {have}"
    # jitter in the pipeline
    out = mod.run_cron(7, spread=240.0, chaos=False)
    seen_off = set()
    for key, rec in out["store"].db.items():
        if key.startswith("job:"):
            cid, t = rec["id"].split("@")
            off = rec["due"] - float(t)
            assert abs(off - mod.cron_jitter(cid, 240.0)) < 1e-9, f"job {rec['id']}: due - fire time should be cron_jitter({cid!r}, 240) = {mod.cron_jitter(cid, 240.0):.3f}, got {off:.3f}"
            seen_off.add((cid, round(off, 6)))
    assert len({c for c, _ in seen_off}) == len(seen_off) >= 4, "each cron must keep ONE offset for all of its periods"
    return ("fire_times / cron_jitter: schedule arithmetic exact; 3000 crons at :00 with 300 s of jitter -> at most "
            f"{max(per_s.values())} starts in any second (mean 10; without jitter: 3000), stable per cron\n"
            "fire_cron: one job per (cron, fire time), a replaced leader is fenced, job and cursor are one atomic write (40 seeds of injected crashes)\n"
            f"{len(S)} runs of 3 replicas for 600 s with {crashes} replica crashes / freezes / store crashes and {zombies} late zombie firings: {jobs_total} jobs, "
            "no firing created twice, none missed, tokens never went backwards")


check(1, "Milestone 1: a durable log-backed store and a due-time index", m1)
check(2, "Milestone 2: leases, expiry and fencing tokens", m2)
check(3, "Milestone 3: retries with backoff and jitter, dead letters", m3)
check(4, "Milestone 4: idempotent handlers via an effect ledger, under chaos", m4)
check(5, "Milestone 5: cron with a leader lease, jitter against the herd", m5)

print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - T0:.1f} s)")
sys.exit(0 if results and all(results) else 1)
