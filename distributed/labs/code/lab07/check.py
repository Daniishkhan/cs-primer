"""Self-check for Lab 7: Deterministic Simulation Testing.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Everything is simulated in one process and seeded: no network, no threads. A full run takes
roughly 20 seconds with the reference solution. When something fails, the output names the seed
(and the plan) so you can replay it: run_seed(SEED) gives the same run every time.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import os
import random
import signal
import subprocess
import sys
import time
import types

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
if target not in ("starter", "solution"):
    sys.exit("usage: python3 check.py [starter|solution]")
mod = importlib.import_module(target)
ref = importlib.import_module("solution")      # the oracle: "does this seed really fail?"
import harness                                # noqa: E402
import kvstore                                 # noqa: E402
import linearize                               # noqa: E402

INF = float("inf")
results = []
notes = []


def note(text):
    notes.append(text)


def _alarm(signum, frame):
    raise AssertionError("this took more than 45 seconds: is something looping, or is run_seed far too slow?")


def check(name, fn):
    del notes[:]
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(45)
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
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
    for line in notes:
        print(line)


# ======================================================================================
# Milestone 1: the simulator
# ======================================================================================

def make_probe(events):
    """A node class that records everything that happens to it in `events`."""
    class Probe:
        boots = 0

        def __init__(self, node_id, sim, durable):
            self.id, self.sim, self.durable = node_id, sim, durable
            events.append((sim.now, "boot", node_id, dict(durable)))

        def on_start(self):
            events.append((self.sim.now, "start", self.id, None))

        def on_message(self, src, msg):
            events.append((self.sim.now, "msg", self.id, (src, msg)))

        def on_timer(self, tag):
            events.append((self.sim.now, "timer", self.id, tag))
    return Probe


def cluster(seed=1, net=None, disk=(3, 3), nodes=(0, 1, 2), clients=(100,)):
    events = []
    sim = mod.Simulator(seed, net, disk)
    probe = make_probe(events)
    for n in nodes:
        sim.add_node(n, probe)
    for c in clients:
        sim.add_node(c, probe, client=True)
    return sim, events


def msgs(events, dst=None):
    return [(t, e[2], e[3]) for e in events for t in [e[0]] if e[1] == "msg" and (dst is None or e[2] == dst)]


def m1():
    NC = harness.NetConfig
    # --- time and ordering
    sim = mod.Simulator(1)
    order = []
    sim.schedule(5, lambda: order.append(("a", sim.now)))
    sim.schedule(3, lambda: order.append(("b", sim.now)))
    sim.schedule(5, lambda: order.append(("c", sim.now)))
    sim.schedule(3, lambda: sim.schedule(1, lambda: order.append(("d", sim.now))))
    sim.run(100)
    assert order == [("b", 3), ("d", 4), ("a", 5), ("c", 5)], \
        f"events must run in (time, scheduling order); an event may schedule more. Got {order}"
    assert sim.now == 5, f"after run() the clock should sit at the last event's time (5), not {sim.now}: time only moves when an event runs"
    sim = mod.Simulator(1)
    seen = []
    sim.schedule(10, lambda: seen.append(10))
    sim.schedule(20, lambda: seen.append(20))
    ticks = []
    sim.run(15, after_event=lambda: ticks.append(sim.now))
    assert seen == [10] and ticks == [10], "run(until) must stop before events due after `until`, and call after_event once per event"
    sim.run(25)
    assert seen == [10, 20], "a later run() continues where the first stopped"

    # --- seeded randomness
    def scenario(seed):
        sim, ev = cluster(seed, NC(1, 9, 0.2, 0.2))
        for i in range(120):
            sim.send(i % 3, (i + 1) % 3, ("m", i))
        sim.run(1000)
        return sim, ev
    a, ea = scenario(5)
    b, eb = scenario(5)
    c, ec = scenario(6)
    assert ea == eb and a.trace_hash() == b.trace_hash(), "the same seed must give exactly the same run"
    assert ea != ec and a.trace_hash() != c.trace_hash(), "a different seed should give a different run"
    random.seed(1)
    x = scenario(5)[1]
    random.seed(2)
    y = scenario(5)[1]
    assert x == y, "the run changed when the global `random` module was reseeded: use only self.rng"

    # --- delay, reorder, loss, duplication
    sim, ev = cluster(2, NC(2, 9, 0.0, 0.0))
    for i in range(300):
        sim.send(0, 1, i)
    sim.run(1000)
    got = msgs(ev, 1)
    assert len(got) == 300, f"with drop=0 and dup=0 all 300 messages arrive, got {len(got)}"
    assert all(2 <= t <= 9 for t, _, _ in got), "every delay must lie in [min_delay, max_delay]"
    seq = [m[2][1] for m in got]
    assert seq != sorted(seq), "messages must be able to arrive out of order: draw a fresh random delay for each"
    sim, ev = cluster(3, NC(1, 3, 0.3, 0.0))
    for i in range(3000):
        sim.send(0, 1, i)
    sim.run(1000)
    n = len(msgs(ev, 1))
    assert 1950 <= n <= 2250, f"with drop=0.3 about 2100 of 3000 messages should arrive, got {n}"
    sim, ev = cluster(4, NC(1, 3, 0.0, 0.2))
    for i in range(3000):
        sim.send(0, 1, i)
    sim.run(1000)
    n = len(msgs(ev, 1))
    assert 3450 <= n <= 3750, f"with dup=0.2 about 3600 deliveries of 3000 messages are expected, got {n}"
    sim, ev = cluster(5, NC(1, 3, 1.0, 1.0))
    sim.send(0, 0, "self")
    sim.send(100, 0, "from client")
    sim.send(1, 100, "to client")
    sim.send(0, 1, "lossy")
    sim.run(100)
    got = sorted(str(m[2][1]) for m in msgs(ev))
    assert got == ["from client", "self", "to client"], \
        f"with drop=1.0 only messages to self or to/from a client survive (and none are duplicated); got {got}"

    # --- partitions
    sim, ev = cluster(6, NC(5, 5, 0, 0))
    sim.partition((0,), (1, 2))
    sim.send(0, 1, "cut")
    sim.send(1, 2, "same side")
    sim.send(100, 0, "client")
    sim.run(100)
    got = sorted(str(m[2][1]) for m in msgs(ev))
    assert got == ["client", "same side"], f"a partition drops messages between groups only; got {got}"
    sim.heal()
    sim.send(0, 1, "after heal")
    sim.run(200)
    assert any(m[2][1] == "after heal" for m in msgs(ev, 1)), "heal() must restore the link"
    sim, ev = cluster(6, NC(5, 5, 0, 0))
    sim.send(0, 1, "in flight")
    sim.send(1, 2, "healed in time")
    sim.schedule(1, lambda: sim.partition((0,), (1, 2)))
    sim.schedule(2, lambda: sim.partition((1,), (0, 2)))
    sim.schedule(3, sim.heal)
    sim.run(100)
    got = sorted(str(m[2][1]) for m in msgs(ev))
    assert got == ["healed in time", "in flight"], \
        f"a message is judged by the partition in force when it ARRIVES (healed by t=3, arrival t=5); got {got}"
    sim, ev = cluster(6, NC(5, 5, 0, 0))
    sim.send(0, 1, "cut in flight")
    sim.schedule(2, lambda: sim.partition((0,), (1, 2)))
    sim.run(100)
    assert not msgs(ev, 1), "a partition that starts while a message is in flight must drop that message"

    # --- crash, restart, durable and volatile state
    sim, ev = cluster(7, NC(5, 5, 0, 0), disk=(3, 3))
    assert sim.nodes[1] is not None
    sim.write_disk(1, "k", {"v": 1}, cb=lambda: ev.append((sim.now, "cb", 1, None)))
    sim.run(2)
    assert sim.durable[1] == {}, "a disk write must not be durable before its delay has passed"
    sim.run(10)
    assert sim.durable[1] == {"k": {"v": 1}} and (3, "cb", 1, None) in ev, "the write lands at t=3 and then calls cb"
    sim.crash(1)
    assert sim.nodes[1] is None, "sim.nodes[id] must be None while a node is down"
    sim.crash(1)
    sim.restart(1)
    boots = [e for e in ev if e[1] == "boot" and e[2] == 1]
    assert len(boots) == 2 and boots[1][3] == {"k": {"v": 1}}, "restart builds a NEW node from the durable state only"
    sim.restart(1)
    assert len([e for e in ev if e[1] == "boot" and e[2] == 1]) == 2, "restart() of a running node does nothing"
    sim.nodes[1].durable["k"] = "scribble"
    assert sim.durable[1]["k"] == {"v": 1}, "the node must get a COPY of the durable dict, or its memory leaks onto the disk"

    sim, ev = cluster(8, NC(5, 5, 0, 0), disk=(3, 3))
    sim.write_disk(2, "lost", 1, cb=lambda: ev.append((sim.now, "cb-lost", 2, None)))
    sim.schedule(1, lambda: sim.crash(2))
    sim.schedule(2, lambda: sim.restart(2))
    sim.run(50)
    assert "lost" not in sim.durable[2] and not any(e[1] == "cb-lost" for e in ev), \
        "a disk write still in flight when the node crashes is lost, and its callback never runs"

    sim, ev = cluster(9, NC(5, 5, 0, 0))
    sim.send(0, 1, "old life")
    sim.set_timer(1, 6, "old timer")
    sim.schedule(2, lambda: sim.crash(1))
    sim.schedule(3, lambda: sim.restart(1))
    sim.schedule(4, lambda: sim.send(0, 1, "new life"))
    sim.schedule(4, lambda: sim.set_timer(1, 6, "new timer"))
    sim.run(100)
    got = [m[2][1] for m in msgs(ev, 1)]
    timers = [e[3] for e in ev if e[1] == "timer"]
    assert got == ["new life"], f"a message sent to a previous life of a node must not reach the new life; got {got}"
    assert timers == ["new timer"], f"a timer set in a previous life must not fire in the new one; got {timers}"
    sim, ev = cluster(10, NC(5, 5, 0, 0))
    sim.send(0, 1, "to a dead node")
    sim.schedule(1, lambda: sim.crash(1))
    sim.run(100)
    assert not msgs(ev, 1), "a message to a crashed node is dropped"

    sim = mod.Simulator(11, NC(1, 1, 0, 0), (1, 20))
    sim.add_node(0, make_probe([]))
    order = []
    for k in range(1, 4):
        sim.write_disk(0, "k", k, cb=lambda k=k: order.append((k, sim.durable[0]["k"])))
    sim.run(100)
    assert order == [(1, 1), (2, 2), (3, 3)], f"disk writes land in the order they were issued; callbacks saw {order}"

    # --- trace
    sim, ev = cluster(12, NC(1, 4, 0.1, 0.1))
    for i in range(50):
        sim.send(0, 1, i)
    sim.crash(2)
    sim.run(100)
    assert len(sim.trace) >= len(msgs(ev)) + 1 and all(isinstance(l, str) for l in sim.trace), \
        "trace must hold at least one string per delivered message and per crash"
    assert len(sim.trace_hash()) == 64
    note("      time, ordering, seeded loss/duplication/reordering, partitions, crash and restart, disk: all as specified")


# ======================================================================================
# Milestone 2: the workload and fault generator
# ======================================================================================

def m2():
    G = mod.generate_plan
    plans = {s: G(s) for s in range(400)}
    assert G(3) == G(3), "the same seed must give an equal plan"
    assert G(3) != G(4), "different seeds should give different plans"
    random.seed(1)
    p1 = G(9)
    random.seed(2)
    p2 = G(9)
    assert p1 == p2, "the plan changed when the global `random` module was reseeded: use your own random.Random"
    small = G(1, n_clients=2, ops_per_client=4)
    assert len(small.ops) == 8, f"n_clients=2, ops_per_client=4 should give 8 ops, got {len(small.ops)}"

    reads = writes = 0
    crash_seeds = part_seeds = 0
    crashed_nodes = set()
    for seed, plan in plans.items():
        assert len(plan.ops) == 18, f"seed {seed}: default is 3 clients x 6 ops = 18 ops, got {len(plan.ops)}"
        values = []
        per_client = {}
        for op in plan.ops:
            assert len(op) == 6, f"seed {seed}: an op is (client, start, f, key, value, node), got {op}"
            client, start, f, key, value, node = op
            assert client in (0, 1, 2) and isinstance(start, int) and start >= 0, f"seed {seed}: bad op {op}"
            assert key in ("x", "y") and node in (0, 1, 2), f"seed {seed}: bad key or node in {op}"
            assert f in ("read", "write"), f"seed {seed}: f must be 'read' or 'write': {op}"
            if f == "write":
                writes += 1
                assert isinstance(value, int) and value > 0, f"seed {seed}: a write needs a positive int value: {op}"
                values.append(value)
            else:
                reads += 1
                assert value is None, f"seed {seed}: a read has value None: {op}"
            per_client.setdefault(client, []).append(start)
        assert len(values) == len(set(values)), f"seed {seed}: write values must be unique (so a read identifies its write)"
        for client, starts in per_client.items():
            assert len(starts) == 6 and starts == sorted(starts), f"seed {seed}: client {client}'s ops must be in start-time order"
        down = {}
        in_partition = False
        last = -1
        for fault in plan.faults:
            assert len(fault) == 3, f"seed {seed}: a fault is (time, kind, arg), got {fault}"
            t, kind, arg = fault
            assert isinstance(t, int) and 0 <= t <= 220 + 140, f"seed {seed}: fault time out of range: {fault}"
            assert t >= last, f"seed {seed}: faults must be in time order"
            last = t
            if kind == "crash":
                assert arg in (0, 1, 2) and not down.get(arg), f"seed {seed}: crash of a node that is already down: {fault}"
                down[arg] = True
                crashed_nodes.add(arg)
            elif kind == "restart":
                assert down.get(arg), f"seed {seed}: restart of a node that is not down: {fault}"
                down[arg] = False
            elif kind == "partition":
                flat = sorted(n for g in arg for n in g)
                assert flat == [0, 1, 2], f"seed {seed}: partition groups must split nodes 0,1,2 between them: {fault}"
                assert not in_partition, f"seed {seed}: partition while already partitioned"
                in_partition = True
            elif kind == "heal":
                assert in_partition, f"seed {seed}: heal without a partition"
                in_partition = False
            else:
                raise AssertionError(f"seed {seed}: unknown fault kind {kind!r}")
        assert not any(down.values()), f"seed {seed}: every crash must be followed by a restart: {plan.faults}"
        assert not in_partition, f"seed {seed}: every partition must be followed by a heal"
        crash_seeds += any(f[1] == "crash" for f in plan.faults)
        part_seeds += any(f[1] == "partition" for f in plan.faults)
    total = reads + writes
    assert 0.3 <= reads / total <= 0.7, f"reads should be roughly half of the ops, got {reads}/{total}"
    assert 0.04 <= crash_seeds / 400 <= 0.6, \
        f"{crash_seeds} of 400 plans contain a crash: faults should be present but not in every plan"
    assert part_seeds / 400 >= 0.05, f"only {part_seeds} of 400 plans contain a partition"
    assert crashed_nodes == {0, 1, 2}, f"every node should get crashed in some plan; only {sorted(crashed_nodes)} were"
    note(f"      400 plans: {crash_seeds} with a crash, {part_seeds} with a partition, {reads} reads / {writes} writes")


# ======================================================================================
# Milestone 3: recorder, invariants, run_seed
# ======================================================================================

def m3():
    r = mod.Recorder()
    r.invoke("a", "write", "x", 1, 0)
    r.invoke("b", "read", "x", None, 2)
    r.ok("a", 1, 3)
    r.ok("b", 1, 5)
    r.invoke("c", "write", "y", 9, 6)
    r.info("c", 66)
    r.invoke("d", "read", "x", None, 70)
    r.info("d", 130)
    r.invoke("e", "write", "x", 4, 140)
    got = sorted(r.operations(), key=lambda o: (o.call, o.process))
    want = [linearize.Op("a", "write", "x", 1, 0, 3, False),
            linearize.Op("b", "read", "x", 1, 2, 5, False),
            linearize.Op("c", "write", "y", 9, 6, INF, True),
            linearize.Op("e", "write", "x", 4, 140, INF, True)]
    assert got == want, ("expected (a timed-out read is dropped; a timed-out or still-pending write has ret=INF and"
                         f" indeterminate=True; a read's value is what it returned):\n    {want}\n  got\n    {got}")

    S = types.SimpleNamespace
    node = lambda store: S(store=store)
    ts = lambda n: (n, 1, 5)
    sim = S(ghost={"acked": {(1, "x"): ts(2)}}, nodes={0: None, 1: node({"x": (ts(2), 7)})})
    assert not mod.durability(sim), "node 1 holds exactly what it acknowledged: the invariant holds"
    sim = S(ghost={"acked": {(1, "x"): ts(2)}}, nodes={1: node({"x": (ts(3), 7)})})
    assert not mod.durability(sim), "holding something NEWER than what it acknowledged is fine"
    sim = S(ghost={"acked": {(1, "x"): ts(2)}}, nodes={1: node({"x": (ts(1), 7)})})
    assert mod.durability(sim), "node 1 acknowledged timestamp 2 but holds timestamp 1: must return a message"
    sim = S(ghost={"acked": {(1, "x"): ts(2)}}, nodes={1: node({})})
    assert mod.durability(sim), "node 1 acknowledged x but holds nothing: must return a message"
    sim = S(ghost={"acked": {(1, "x"): ts(2)}}, nodes={1: None})
    assert not mod.durability(sim), "a crashed node (None) is not checked"
    assert not mod.durability(S(ghost={}, nodes={1: node({})})), "nothing acknowledged yet: the invariant holds"

    ok_count = 0
    for seed in range(150):
        res = mod.run_seed(seed, ref.FixedKVNode)
        assert res.ok, (f"false alarm: seed {seed} fails on the CORRECT store: {res.reason}\n"
                        f"      plan: {res.plan}\n      replay with run_seed({seed}, FixedKVNode-from-solution)")
        assert res.seed == seed and res.reason is None and isinstance(res.trace, list) and len(res.trace_hash) == 64
        ok_count += 1
    note(f"      {ok_count} seeds on the correct store: no false alarms")

    bug = [mod.run_seed(s, kvstore.KVNode) for s in range(300)]
    bad = [b for b in bug if not b.ok]
    assert bad, "the buggy store passed 300 seeds: the invariant or the generator is not catching anything"
    assert all(isinstance(b.reason, str) and b.reason for b in bad), "a failing run needs a `reason` string"
    assert all(b.reason.startswith("invariant") for b in bad), "an invariant failure's reason should start with 'invariant violated'"

    class Liar(kvstore.KVNode):                      # a store that forgets every write when asked
        def on_query(self, src, rid, key):
            self.sim.send(self.id, src, ("query_reply", rid, kvstore.ZERO, None))
    lin = [mod.run_seed(s, Liar, invariants=()) for s in range(60)]
    bad = [b for b in lin if not b.ok]
    assert bad, "a store that answers every read with None must be caught by the history check (no invariants): is run_seed checking the history?"
    assert all("linearizable" in b.reason for b in bad), "a history failure's reason should say 'not linearizable'"
    note(f"      the history check alone catches a store that forgets writes in {len(bad)} of 60 runs")


# ======================================================================================
# Milestone 4: seed search and replay
# ======================================================================================

def subprocess_hash(seed, hashseed):
    code = (f"import sys; sys.dont_write_bytecode = True; sys.path.insert(0, {HERE!r}); "
            f"import {target} as m; print(m.run_seed({seed}).trace_hash)")
    env = dict(os.environ, PYTHONHASHSEED=str(hashseed))
    p = subprocess.run([sys.executable, "-B", "-c", code], env=env, cwd=HERE, capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, f"replaying seed {seed} in a fresh process crashed:\n{p.stderr[-600:]}"
    return p.stdout.strip()


def tail(res, n=8):
    return "\n".join("        " + line for line in res.trace[-n:])


def m4():
    assert mod.find_failing_seed(range(300), ref.FixedKVNode) is None, "the correct store must not have a failing seed"
    t0 = time.time()
    res = mod.find_failing_seed(range(1500), kvstore.KVNode)
    assert res is not None, ("no failing seed in the first 1500 on the buggy store. Are crashes in your plans, and does "
                             "your invariant look at what each node acknowledged?")
    assert not res.ok and res.reason and 0 <= res.seed < 1500
    truth = ref.run_seed(res.seed)
    assert not truth.ok, f"you report seed {res.seed} as failing, but the reference run of that seed passes"
    note(f"      first failing seed: {res.seed}  ({res.reason})")
    note("      the last events of that run:")
    note(tail(res))
    assert mod.replay_matches(res.seed), f"seed {res.seed}: two runs in one process gave different trace hashes"
    again = mod.run_seed(res.seed)
    assert again.trace_hash == res.trace_hash and again.reason == res.reason, "replaying a seed must give the identical trace hash"
    assert again.trace == res.trace, "replaying a seed must give the identical trace, line by line"
    other = mod.run_seed(res.seed + 1)
    assert other.trace_hash != res.trace_hash, "different seeds should give different traces"
    for hashseed in (1, 2, 12345):
        h = subprocess_hash(res.seed, hashseed)
        assert h == res.trace_hash, (f"seed {res.seed} gives a different trace in a fresh process with PYTHONHASHSEED={hashseed}.\n"
                                     "      Something depends on set order, hash(), id() or the global random module: find it and remove it.")
    note(f"      replay is byte-identical: same trace hash in this process and in 3 fresh processes ({res.trace_hash[:16]}...)")


# ======================================================================================
# Milestone 5: shrinking
# ======================================================================================

def m5():
    found = []
    for seed in range(1500):
        r = ref.run_seed(seed)
        if not r.ok:
            found.append(seed)
        if len(found) == 4:
            break
    assert len(found) == 4
    sizes = []
    for seed in found:
        failure = mod.run_seed(seed)
        assert not failure.ok
        small = mod.shrink(failure)
        assert not small.ok, f"seed {seed}: the shrunk plan does not fail any more"
        assert small.seed == seed, "shrinking keeps the seed and changes the plan"
        before = harness.plan_items(failure.plan)
        after = harness.plan_items(small.plan)
        assert all(item in before for item in after), "the shrunk plan may only contain items from the original plan"
        assert len(after) <= len(before) // 2 + 1, \
            f"seed {seed}: shrunk {len(before)} items to only {len(after)}: keep going, most of a plan is irrelevant to a bug"
        for i in range(len(after)):
            rest = after[:i] + after[i + 1:]
            still = not ref.run_seed(seed, kvstore.KVNode, harness.plan_from_items(rest)).ok
            assert not still, (f"seed {seed}: item {after[i]} can be removed and the run still fails: not minimal yet.\n"
                               f"      shrunk plan: {small.plan}")
        assert mod.run_seed(seed, plan=small.plan).trace_hash == small.trace_hash, "the shrunk run must replay identically too"
        sizes.append(len(after))
        if seed == found[0]:
            note(f"      seed {seed}: {len(before)} items shrink to {len(after)}")
            note(f"      ops:    {list(small.plan.ops)}")
            note(f"      faults: {list(small.plan.faults)}")
            note(f"      why:    {small.reason}")
        else:
            note(f"      seed {seed}: {len(before)} items shrink to {len(after)}")
    assert min(sizes) <= 5, f"the smallest case you reached has {min(sizes)} items; this bug needs only a write, a read and a crash with its restart"


# ======================================================================================
# Milestone 6: the fix
# ======================================================================================

def m6():
    assert mod.FixedKVNode is not kvstore.KVNode and issubclass(mod.FixedKVNode, kvstore.KVNode), \
        "FixedKVNode must be a subclass of KVNode"
    buggy = mod.soak(range(300), kvstore.KVNode)
    truth = [s for s in range(300) if not ref.run_seed(s).ok]
    assert buggy == truth, "soak on the buggy store must list exactly the failing seeds"
    for seed in truth[:3]:
        r = mod.run_seed(seed, mod.FixedKVNode)
        assert r.ok, f"seed {seed} still fails with your FixedKVNode: {r.reason}\n      plan: {r.plan}"
    t0 = time.time()
    bad = mod.soak(range(5000), mod.FixedKVNode)
    assert not bad, f"your fix still fails on {len(bad)} of 5000 seeds, for example {bad[:5]}: replay one with run_seed(seed, FixedKVNode)"
    bad = mod.soak(range(100000, 100500), mod.FixedKVNode, invariants=())
    assert not bad, f"the history check alone fails on seeds {bad[:5]} with your fix"
    note(f"      5,500 seeds on FixedKVNode, all pass ({time.time() - t0:.1f}s); the original {len(truth)} failures of the first 300 seeds are gone")


print(f"Lab 7 checks against {target}.py\n")
check("Milestone 1: a deterministic simulator", m1)
check("Milestone 2: a workload and fault generator", m2)
check("Milestone 3: history recorder, invariants and run_seed", m3)
check("Milestone 4: seed search, and replay that is byte-identical", m4)
check("Milestone 5: shrinking a failing run to a minimal case", m5)
check("Milestone 6: fix the bug, then soak thousands of seeds", m6)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing")
sys.exit(0 if passed == len(results) else 1)
