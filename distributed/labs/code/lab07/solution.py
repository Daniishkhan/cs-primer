"""Lab 7: Deterministic Simulation Testing. Reference solution.

Same layout as starter.py. Try not to read this before you have had a real go.
Run `python3 check.py solution` to check it.
"""
import copy
import hashlib
import heapq
import itertools
import random

import linearize
from harness import (DEFAULT_NET, InvariantViolation, NetConfig, Plan, RunResult,
                     plan_from_items, plan_items, run_plan)
from kvstore import KVNode, ZERO

INF = float("inf")


# =====================================================================================
# Milestone 1: the simulator
# =====================================================================================

class Simulator:
    """A whole cluster in one thread. Time is an integer that only moves when an event runs.

    Everything that can happen later is an entry in one priority queue ordered by (time, seq), where
    seq is a counter that makes ties deterministic. Everything random comes from self.rng."""

    def __init__(self, seed, net=None, disk_delay=(2, 12)):
        self.rng = random.Random(seed)
        self.net = net or DEFAULT_NET
        self.disk_delay = disk_delay
        self.now = 0
        self.ghost = {}                 # scratch space for test instrumentation (see KVNode._ack)
        self.nodes = {}                 # id -> live node object, or None while the node is crashed
        self.durable = {}               # id -> dict that survives crashes (what is on the disk)
        self.incarnation = {}           # id -> how many times it has crashed
        self.trace = []
        self._factories = {}
        self._clients = set()
        self._group = {}                # id -> partition group number
        self._disk_free = {}            # id -> time the disk finishes its last queued write
        self._queue = []
        self._seq = 0

    # ---- nodes ----
    def add_node(self, node_id, factory, client=False):
        """Create a node: factory(node_id, sim, durable_copy) -> node. Then call node.on_start()."""
        self._factories[node_id] = factory
        self.durable[node_id] = {}
        self.incarnation[node_id] = 0
        if client:
            self._clients.add(node_id)
        self._boot(node_id)

    def _boot(self, node_id):
        node = self._factories[node_id](node_id, self, copy.deepcopy(self.durable[node_id]))
        self.nodes[node_id] = node
        self.log(f"start {node_id}")
        node.on_start()

    def crash(self, node_id):
        """Lose everything in memory. Messages, timers and disk writes belonging to this life die with it."""
        if self.nodes[node_id] is None:
            return
        self.nodes[node_id] = None
        self.incarnation[node_id] += 1
        self._disk_free[node_id] = 0
        self.log(f"crash {node_id}")

    def restart(self, node_id):
        """Boot a fresh node object from the durable state only."""
        if self.nodes[node_id] is not None:
            return
        self._boot(node_id)

    # ---- time and events ----
    def _push(self, delay, kind, data):
        heapq.heappush(self._queue, (self.now + delay, self._seq, kind, data))
        self._seq += 1

    def schedule(self, delay, fn):
        self._push(delay, "call", (fn,))

    def set_timer(self, node_id, delay, tag):
        self._push(delay, "timer", (node_id, tag, self.incarnation[node_id]))

    def run(self, until, after_event=None):
        """Process events in (time, seq) order while the next one is due at or before `until`."""
        while self._queue and self._queue[0][0] <= until:
            self.now, _, kind, data = heapq.heappop(self._queue)
            getattr(self, "_do_" + kind)(*data)
            if after_event is not None:
                after_event()

    def _do_call(self, fn):
        fn()

    def _do_timer(self, node_id, tag, incarnation):
        node = self.nodes[node_id]
        if node is None or incarnation != self.incarnation[node_id]:
            return
        self.log(f"timer {node_id} {tag}")
        node.on_timer(tag)

    # ---- network ----
    def send(self, src, dst, msg):
        lossy = src != dst and src not in self._clients and dst not in self._clients
        if lossy and self.rng.random() < self.net.drop:
            self.log(f"lost {src}->{dst} {msg}")
            return
        copies = 2 if lossy and self.rng.random() < self.net.dup else 1
        for _ in range(copies):
            delay = self.rng.randint(self.net.min_delay, self.net.max_delay)
            self._push(delay, "deliver", (src, dst, msg, self.incarnation[dst]))

    def _do_deliver(self, src, dst, msg, incarnation):
        node = self.nodes[dst]
        if node is None or incarnation != self.incarnation[dst]:
            self.log(f"drop {src}->{dst} {msg} (destination down)")
        elif self._blocked(src, dst):
            self.log(f"drop {src}->{dst} {msg} (partition)")
        else:
            self.log(f"deliver {src}->{dst} {msg}")
            node.on_message(src, msg)

    def partition(self, *groups):
        self._group = {n: g for g, members in enumerate(groups) for n in members}
        self.log(f"partition {groups}")

    def heal(self):
        self._group = {}
        self.log("heal")

    def _blocked(self, a, b):
        ga, gb = self._group.get(a), self._group.get(b)
        return ga is not None and gb is not None and ga != gb

    # ---- disk ----
    def write_disk(self, node_id, key, value, cb=None):
        """Save value under key for node_id. It reaches the disk after a random delay, in the order
        the writes were issued. If the node crashes first, the write is lost and cb is never called."""
        lo, hi = self.disk_delay
        done = max(self.now + self.rng.randint(lo, hi), self._disk_free.get(node_id, 0))
        self._disk_free[node_id] = done
        self._push(done - self.now, "disk", (node_id, key, value, cb, self.incarnation[node_id]))

    def _do_disk(self, node_id, key, value, cb, incarnation):
        if incarnation != self.incarnation[node_id]:
            self.log(f"disk write lost {node_id} {key}")
            return
        self.durable[node_id][key] = value
        self.log(f"disk {node_id} {key}")
        if cb is not None:
            cb()

    # ---- trace ----
    def log(self, text):
        self.trace.append(f"{self.now} {text}")

    def trace_hash(self):
        return hashlib.sha256("\n".join(self.trace).encode()).hexdigest()


# =====================================================================================
# Milestone 2: the workload and fault generator
# =====================================================================================

def generate_plan(seed, n_clients=3, ops_per_client=6, horizon=220):
    """A random Plan, a pure function of `seed`: the same seed must give an equal Plan."""
    rng = random.Random(f"plan:{seed}")             # a string seed is stable across processes
    fresh = itertools.count(1)
    ops = []
    for c in range(n_clients):
        t = rng.randint(0, 25)
        for _ in range(ops_per_client):
            key = rng.choice(["x", "y"])
            if rng.random() < 0.5:
                f, value = "write", next(fresh)
            else:
                f, value = "read", None
            ops.append((c, t, f, key, value, rng.randrange(3)))
            t += rng.randint(5, 35)
    faults = []
    for node in range(3):
        if rng.random() < 0.12:
            t = rng.randint(10, horizon)
            faults.append((t, "crash", node))
            faults.append((t + rng.randint(10, 60), "restart", node))
    if rng.random() < 0.3:
        t = rng.randint(10, horizon)
        lone = rng.randrange(3)
        others = tuple(n for n in range(3) if n != lone)
        faults.append((t, "partition", ((lone,), others)))
        faults.append((t + rng.randint(20, 80), "heal", None))
    faults.sort(key=lambda f: (f[0], f[1], str(f[2])))
    return Plan(tuple(ops), tuple(faults))


# =====================================================================================
# Milestone 3: history recorder, invariants, and run_seed
# =====================================================================================

class Recorder:
    """Called by the clients. Builds linearize.Op objects with intervals."""

    def __init__(self):
        self._pending = {}              # process -> (f, key, value, call time)
        self._done = []

    def invoke(self, process, f, key, value, time):
        self._pending[process] = (f, key, value, time)

    def ok(self, process, value, time):
        f, key, _, call = self._pending.pop(process)
        self._done.append(linearize.Op(process, f, key, value, call, time, False))

    def info(self, process, time):
        f, key, value, call = self._pending.pop(process)
        if f == "write":                # a read that timed out tells us nothing and changes nothing
            self._done.append(linearize.Op(process, f, key, value, call, INF, True))

    def operations(self):
        ops = list(self._done)
        for process, (f, key, value, call) in self._pending.items():      # never answered: same as a timeout
            if f == "write":
                ops.append(linearize.Op(process, f, key, value, call, INF, True))
        return ops


def durability(sim):
    """A node never forgets a write it has acknowledged. Returns a message if some node has."""
    for (node_id, key), ts in sim.ghost.get("acked", {}).items():
        node = sim.nodes[node_id]
        if node is None:
            continue
        have = node.store.get(key, (ZERO, None))[0]
        if have < ts:
            return f"node {node_id} acknowledged {key} at timestamp {ts} but now holds only {have}"
    return None


def run_seed(seed, node_factory=KVNode, plan=None, invariants=(durability,)):
    """One complete simulated run. Returns a RunResult. ok is True when no invariant fired and every
    key's history is linearizable; otherwise `reason` says which."""
    plan = plan if plan is not None else generate_plan(seed)
    recorder = Recorder()
    reason = None
    try:
        sim = run_plan(plan, seed, simulator_cls=Simulator, node_factory=node_factory,
                       recorder=recorder, invariants=invariants)
    except InvariantViolation as e:
        sim, reason = e.sim, f"invariant violated: {e}"
    ops = recorder.operations()
    if reason is None:
        bad = linearize.check_history(ops)
        if bad is not None:
            reason = f"history of key {bad!r} is not linearizable"
    return RunResult(seed, reason is None, reason, sim.trace_hash(), plan, sim.trace, ops)


# =====================================================================================
# Milestone 4: seed search and replay
# =====================================================================================

def find_failing_seed(seeds, node_factory=KVNode, invariants=(durability,)):
    """Return the RunResult of the first seed that fails, or None."""
    for seed in seeds:
        result = run_seed(seed, node_factory, invariants=invariants)
        if not result.ok:
            return result
    return None


def replay_matches(seed, node_factory=KVNode, invariants=(durability,)):
    """Run the seed twice. True if both runs have the same trace hash and the same verdict."""
    a = run_seed(seed, node_factory, invariants=invariants)
    b = run_seed(seed, node_factory, invariants=invariants)
    return a.trace_hash == b.trace_hash and a.reason == b.reason


# =====================================================================================
# Milestone 5: shrinking
# =====================================================================================

def shrink(failure, node_factory=KVNode, invariants=(durability,)):
    """Given a failing RunResult, return the RunResult of a smaller plan that still fails with the
    same seed. Removing any single remaining op or fault must make the run pass.
    Delta debugging over plan_items(failure.plan): try dropping chunks, refine when stuck."""
    def fails(items):
        return not run_seed(failure.seed, node_factory, plan_from_items(items), invariants).ok

    items = plan_items(failure.plan)
    parts = 2
    while len(items) >= 2:
        chunk = max(1, len(items) // parts)
        for start in range(0, len(items), chunk):
            candidate = items[:start] + items[start + chunk:]
            if fails(candidate):
                items = candidate
                parts = max(parts - 1, 2)
                break
        else:
            if chunk == 1:
                break
            parts = min(len(items), parts * 2)
    return run_seed(failure.seed, node_factory, plan_from_items(items), invariants)


# =====================================================================================
# Milestone 6: the fix, and a soak test
# =====================================================================================

class FixedKVNode(KVNode):
    """Acknowledge a store only after it has reached the disk."""

    def on_store(self, src, rid, key, ts, value):
        if ts > self.store.get(key, (ZERO, None))[0]:
            self.store[key] = (ts, value)
        self.sim.write_disk(self.id, "store", dict(self.store),
                            cb=lambda: self._ack(src, rid, key, ts))


def soak(seeds, node_factory=FixedKVNode, invariants=(durability,)):
    """Run every seed. Return the list of seeds that failed (empty means all passed)."""
    return [s for s in seeds if not run_seed(s, node_factory, invariants=invariants).ok]
