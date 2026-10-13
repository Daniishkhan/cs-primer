"""Self-check for Lab 5.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Every milestone runs against real nodes on 127.0.0.1, but the failures are
injected by switches on the Node objects (pause, kill, drop replies) and the
clients use a fake sleep, so nothing depends on a timing race.
Prints ✔ / ✘ / … (not implemented yet).
"""
import importlib
import itertools
import random
import socket
import sys
import threading
import time

HOST = "127.0.0.1"
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
server_errors = []      # exceptions raised inside server threads


class NotStarted(Exception):
    pass


def check(name, fn):
    server_errors.clear()
    del mod.NODE_ERRORS[:]
    try:
        note = fn()
        print(f"  ✔ {name}")
        if note:
            for line in str(note).splitlines():
                print(f"      {line}")
        results.append(True)
    except (NotImplementedError, NotStarted) as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:  # anything else is a bug worth seeing
        inner = next((x for x in server_errors + mod.NODE_ERRORS if isinstance(x, NotImplementedError)), None)
        other = next(iter(server_errors + mod.NODE_ERRORS), None)
        if inner is not None:
            print(f"  … {name}: not implemented yet ({inner})")
        elif other is not None:
            print(f"  ✘ {name}: a node crashed with {type(other).__name__}: {other}")
        else:
            print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)


def start(server_fn, **kwargs):
    """Run server_fn(port=0, ready=...) in a thread; return the port it bound."""
    got = {}
    ready = threading.Event()

    def on_ready(port):
        got["port"] = port
        ready.set()

    def run():
        try:
            server_fn(port=0, ready=on_ready, **kwargs)
        except BaseException as e:  # surface errors from the thread
            got["error"] = e
            server_errors.append(e)
            ready.set()

    threading.Thread(target=run, daemon=True).start()
    if not ready.wait(3):
        raise AssertionError("server did not call ready(port) within 3 s")
    if "error" in got:
        raise got["error"]
    return got["port"]


class Fresh:
    """A cluster that is always shut down afterwards."""

    def __init__(self, n=3):
        self.cluster = mod.Cluster(n)

    def __enter__(self):
        return self.cluster

    def __exit__(self, *exc):
        self.cluster.stop()


def holders(cluster, key, value):
    """Indexes of the nodes whose store holds `value` for `key`."""
    return [i for i, n in enumerate(cluster.nodes) if n.store.get(key)[0] == value]


def free_port():
    s = socket.socket()
    s.bind((HOST, 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --- Milestone 1 ----------------------------------------------------------------

def m1():
    stop = threading.Event()
    port = start(mod.serve, stop=stop)
    try:
        r = mod.call(port, {"op": "get", "key": "x"})
        assert r["ok"] and r["value"] is None and tuple(r["version"]) == (0, ""), \
            f"a missing key should give value None and version (0, ''), got {r}"
        r = mod.call(port, {"op": "put", "key": "x", "value": "hello", "version": [1, "a"]})
        assert r["ok"] and r["applied"] is True, f"first put should be applied, got {r}"
        r = mod.call(port, {"op": "get", "key": "x"})
        assert r["value"] == "hello" and tuple(r["version"]) == (1, "a"), f"get after put returned {r}"
        r = mod.call(port, {"op": "put", "key": "x", "value": "newer", "version": [2, "a"]})
        assert r["applied"] is True
        r = mod.call(port, {"op": "put", "key": "x", "value": "old", "version": [1, "z"]})
        assert r["applied"] is False, "a put with an older version must be ignored"
        r = mod.call(port, {"op": "put", "key": "x", "value": "tie", "version": [2, "b"]})
        assert r["applied"] is True, "equal counters: the bigger tag ('b' > 'a') should win"
        r = mod.call(port, {"op": "get", "key": "x"})
        assert r["value"] == "tie" and tuple(r["version"]) == (2, "b"), f"expected ('tie', (2, 'b')), got {r}"
    finally:
        stop.set()
    # Nobody listens here any more: a definite refusal, not a hang.
    try:
        mod.call(free_port(), {"op": "ping"}, timeout=1)
        raise AssertionError("call() to a closed port should raise ReplicaDown")
    except mod.ReplicaDown:
        pass
    # Something listens but never answers (the kernel accepts the connection, nobody reads it).
    mute = socket.socket()
    mute.bind((HOST, 0))
    mute.listen(1)
    t = time.time()
    try:
        mod.call(mute.getsockname()[1], {"op": "ping"}, timeout=0.3)
        raise AssertionError("call() to a silent server should raise ReplicaTimeout")
    except mod.ReplicaTimeout:
        pass
    finally:
        mute.close()
    assert time.time() - t < 2, "call() should give up after its timeout"


# --- Milestone 2 ----------------------------------------------------------------

def m2():
    with Fresh() as c:
        cl = c.client(w=2)
        v1 = cl.put("x", "v1", prefer=[0, 1, 2])
        assert holders(c, "x", "v1") == [0, 1], \
            f"with W=2 the write should reach exactly the first two replicas, but {holders(c, 'x', 'v1')} hold it"
        assert c.nodes[0].store.get("x")[1] == tuple(v1), "the node should store the version put() returned"
        v2 = cl.put("x", "v2", prefer=[2, 0, 1])
        assert tuple(v2) > tuple(v1), f"a later put must get a bigger version ({v2} vs {v1})"
        assert holders(c, "x", "v2") == [0, 2], "second write should go to replicas 2 and 0"
        assert c.nodes[1].store.get("x")[0] == "v1", "replica 1 was not written, so it still holds v1"
        cl3 = c.client(w=3, client_id="c2")
        cl3.put("y", "everywhere")
        assert holders(c, "y", "everywhere") == [0, 1, 2], "W=3 means all three replicas"
        cl1 = c.client(w=1, client_id="c3")
        cl1.put("z", "lonely", prefer=[1, 0, 2])
        assert holders(c, "z", "lonely") == [1], "W=1 means a single replica holds the write"


# --- Milestone 3 ----------------------------------------------------------------

def stale_count(cluster, w, r):
    """Over every (write order, read order) pair: how often does a read miss the newest write?"""
    cl = cluster.client(w=3, r=r, client_id=f"s{w}{r}")   # op ids must be unique per client
    perms = list(itertools.permutations(range(3)))
    stale = 0
    for n, (wo, ro) in enumerate(itertools.product(perms, perms)):
        key = f"k{w}{r}-{n}"
        cl.w = 3
        cl.put(key, "old")                 # everyone has the old value
        cl.w = w
        cl.put(key, "new", prefer=wo)      # only W replicas get the new one
        value, _ = cl.get(key, prefer=ro)
        stale += value != "new"
    return stale, len(perms) ** 2


def m3():
    lines = []
    with Fresh() as c:
        cl = c.client(w=3, r=3)
        cl.put("k", "v")
        assert cl.get("k") == ("v", cl.get("k")[1]) and cl.get("k")[0] == "v", "R=3 should read back what W=3 wrote"
        assert cl.get("nope")[0] is None, "a key nobody wrote reads as None"
        # R=1: really asks one replica only, so it can see an old copy
        cl.w, cl.r = 3, 1
        cl.put("a", "old")
        cl.w = 1
        cl.put("a", "new", prefer=[0, 1, 2])
        assert cl.get("a", prefer=[0, 1, 2])[0] == "new"
        assert cl.get("a", prefer=[2, 1, 0])[0] == "old", "R=1 from a replica that missed the write must return the old value"
        for w, r in [(1, 1), (2, 1), (1, 2), (2, 2), (3, 1), (1, 3), (3, 3)]:
            stale, total = stale_count(c, w, r)
            if w + r <= 3:
                assert stale > 0, f"N=3, W={w}, R={r}: R+W <= N, so some order should read stale data, but none did"
                lines.append(f"W={w} R={r}  R+W={w + r} <= N: stale in {stale:2d} of {total} read/write orders")
            else:
                assert stale == 0, f"N=3, W={w}, R={r}: R+W > N, but {stale} of {total} order combinations read stale data"
                lines.append(f"W={w} R={r}  R+W={w + r} >  N: stale in  0 of {total} read/write orders")
    return "\n".join(lines)


# --- Milestone 4 ----------------------------------------------------------------

def m4():
    notes = []
    with Fresh() as c:
        cl = c.client(w=2, r=2, timeout=0.2)
        # a killed node: refused at once, the write goes to the next replicas instead
        c.nodes[2].kill()
        t = time.time()
        cl.put("x", "v1", prefer=[2, 0, 1])
        assert holders(c, "x", "v1") == [0, 1], "node 2 is dead, so the write should land on 0 and 1"
        assert time.time() - t < 1.5, "a refused connection should not cost a timeout"
        # a paused node: silence, so we pay one timeout and move on
        c.nodes[2].restart()
        c.nodes[1].pause()
        t = time.time()
        value, _ = cl.get("x", prefer=[1, 0, 2])
        took = time.time() - t
        assert value == "v1", f"read should skip the paused node and still find v1, got {value!r}"
        assert 0.15 <= took < 1.5, f"expected about one 0.2 s timeout for the paused replica, took {took:.2f}s"
        notes.append(f"skipping a paused replica cost one timeout ({took:.2f}s)")
        # not enough replicas: fail cleanly, with numbers
        c.nodes[2].kill()
        t = time.time()
        try:
            cl.put("x", "v2", prefer=[0, 1, 2])
            raise AssertionError("only node 0 is reachable and W=2: put must raise QuorumNotReached")
        except mod.QuorumNotReached as e:
            assert (e.needed, e.got) == (2, 1), f"expected needed=2 got=1, got needed={e.needed} got={e.got}"
        assert time.time() - t < 3, "a failed quorum must fail in bounded time, not hang"
        try:
            cl.get("x", prefer=[0, 1, 2])
            raise AssertionError("R=2 with one reachable replica: get must raise QuorumNotReached")
        except mod.QuorumNotReached:
            pass
        notes.append("W=2 with one live replica: QuorumNotReached(needed=2, got=1)")
        # restart: with the data kept (on disk) or lost (memory only)
        c.nodes[1].resume()
        c.nodes[2].restart(wipe=False)
        c.nodes[1].kill()
        c.nodes[1].restart(wipe=False)
        assert c.nodes[1].store.get("x")[0] == "v1", "restart(wipe=False) must keep the data"
        c.nodes[1].restart(wipe=True)
        assert c.nodes[1].store.get("x")[0] is None, "restart(wipe=True) must lose the data"
        cl.put("x", "v3", prefer=[1, 0, 2])
        assert holders(c, "x", "v3") == [0, 1], "after the restart the cluster is writable again"
        notes.append("restart keeps data if it was on disk, loses it if it was only in memory")
    return "\n".join(notes)


# --- Milestone 5 ----------------------------------------------------------------

def m5():
    notes = []
    rng = random.Random(7)
    # backoff_delay: full jitter inside a growing ceiling
    for attempt in range(8):
        ceiling = min(2.0, 0.1 * 2 ** attempt)
        draws = [mod.backoff_delay(attempt, base=0.1, cap=2.0, rng=rng) for _ in range(300)]
        assert all(0 <= d <= ceiling + 1e-9 for d in draws), \
            f"attempt {attempt}: every delay must be between 0 and {ceiling}, got max {max(draws)}"
        assert len(set(round(d, 6) for d in draws)) > 100, f"attempt {attempt}: delays should be random (jitter), not all the same"
        assert max(draws) > ceiling * 0.8, f"attempt {attempt}: delays should spread up towards {ceiling}"
    # retry(): fake sleep, so no real waiting
    sleeps = []
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise mod.QuorumNotReached(2, 1)
        return "ok"
    assert mod.retry(flaky, attempts=5, base=0.1, cap=2.0, rng=random.Random(1), sleep=sleeps.append) == "ok"
    assert len(calls) == 3 and len(sleeps) == 2, f"two failures should mean two sleeps, got {len(sleeps)}"
    assert sleeps[0] <= 0.1 and sleeps[1] <= 0.2, f"waits should come from the growing ceiling (<=0.1, <=0.2), got {sleeps}"
    sleeps.clear()
    n = []

    def always():
        n.append(1)
        raise mod.QuorumNotReached(2, 0)
    try:
        mod.retry(always, attempts=4, rng=random.Random(2), sleep=sleeps.append)
        raise AssertionError("retry() should re-raise after the last attempt")
    except mod.QuorumNotReached:
        pass
    assert len(n) == 4 and len(sleeps) == 3, f"4 attempts means 4 calls and 3 sleeps, got {len(n)} calls and {len(sleeps)} sleeps"

    def buggy():
        raise ValueError("bug")
    sleeps.clear()
    try:
        mod.retry(buggy, attempts=4, sleep=sleeps.append)
        raise AssertionError("a ValueError is not retryable")
    except ValueError:
        assert not sleeps, "don't back off for errors that aren't in retry_on"
    # idempotency: every node does the put but its reply is lost, so the client sees a failure
    with Fresh() as c:
        cl = c.client(w=2, r=2, timeout=0.15)
        for node in c.nodes:
            node.drop_next_replies(1, "put")
        slept = []
        out = mod.retry(lambda: cl.increment("hits", op_id="inc-1"), attempts=4,
                        rng=random.Random(3), sleep=slept.append)
        assert slept, "the first attempt should have failed (all replies were dropped) and been retried"
        assert out == 1, f"retry of increment 'inc-1' returned {out}; it should return 1"
        assert cl.get("hits")[0] == 1, "counter is not 1: the retry applied the increment a second time"
        assert cl.increment("hits", op_id="inc-2") == 2, "a genuinely new operation must still count"
        assert cl.increment("hits", op_id="inc-2") == 2, "repeating inc-2 must not count again"
        assert cl.get("hits")[0] == 2
        notes.append("retried increment with an idempotency key: counter = 1, not 2")
        # the same story without a key: a fresh id per attempt double counts
        for node in c.nodes:
            node.drop_next_replies(1, "put")
        out = mod.retry(lambda: cl.increment("naive"), attempts=4,
                        rng=random.Random(3), sleep=lambda s: None)
        assert out == 2, f"without a reused key the retry should double count (2), got {out}"
        notes.append("same retry with a NEW id each attempt: counter = 2 (applied twice!)")
        # append works the same way
        assert cl.append("log", "a", op_id="ap-1") == ["a"]
        assert cl.append("log", "a", op_id="ap-1") == ["a"], "repeating ap-1 must not append twice"
        assert cl.append("log", "b", op_id="ap-2") == ["a", "b"]
        notes.append("append with the same key twice: stored once")
    return "\n".join(notes)


# --- Milestone 6 ----------------------------------------------------------------

def m6():
    notes = []
    with Fresh() as c:
        cl = c.client(w=1, r=3, read_repair=False)
        cl.put("x", "v1", prefer=[0, 1, 2])
        assert cl.get("x")[0] == "v1"
        assert holders(c, "x", "v1") == [0], "without read repair, reading must not change the replicas"
        cl.read_repair = True
        value, _ = cl.get("x")
        assert value == "v1", "read repair must not change what the read returns"
        assert holders(c, "x", "v1") == [0, 1, 2], f"after a read repair all replicas should hold v1, but only {holders(c, 'x', 'v1')} do"
        assert cl.repairs == 2, f"two replicas were behind, so repairs should be 2, got {cl.repairs}"
        notes.append("W=1 write on one replica; one R=3 read copied it to the other two")
        # a replica that restarted empty is healed by the next read
        c.nodes[1].restart(wipe=True)
        assert c.nodes[1].store.get("x")[0] is None
        cl.get("x")
        assert c.nodes[1].store.get("x")[0] == "v1", "a wiped replica should be repaired by a read that touches it"
        notes.append("a wiped replica was repaired by the next read")
        # only the replicas we asked are repaired, and repair never goes backwards
        cl2 = c.client(w=1, r=2, read_repair=True, client_id="c9")
        cl2.put("y", "new", prefer=[0, 1, 2])
        cl2.get("y", prefer=[0, 1, 2])
        assert holders(c, "y", "new") == [0, 1], "R=2 only touches two replicas, so only those are repaired"
        c.nodes[0].store.put("y", "newer", (99, "zz"))
        cl2.get("y", prefer=[2, 1, 0])
        assert c.nodes[1].store.get("y")[0] == "new", "stale data must never overwrite newer data"
        # a dead replica must not break a read
        c.nodes[2].kill()
        cl2.timeout = 0.2
        assert cl2.get("y", prefer=[2, 1, 0])[0] == "newer"
    return "\n".join(notes)


print(f"Lab 5 checks against {target}.py\n")
check("Milestone 1: a single node (get/put with versions)", m1)
check("Milestone 2: replicated writes to W nodes", m2)
check("Milestone 3: quorum reads, and when they go stale", m3)
check("Milestone 4: timeouts, failures and QuorumNotReached", m4)
check("Milestone 5: retries with backoff, and idempotency keys", m5)
check("Milestone 6: read repair", m6)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
