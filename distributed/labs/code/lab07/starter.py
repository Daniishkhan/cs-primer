"""Lab 7: Deterministic Simulation Testing. Your file.

You build the machinery that lets a whole cluster run inside one process, driven by one seed:
a simulator (time, network, crashes, disk), a workload and fault generator, a history recorder
with invariants, a seed search, replay, and a shrinker. The store under test is given in
kvstore.py (it has a bug; finding it is the point), and so are the clients and the glue in
harness.py and a linearizability checker in linearize.py. Read those two docstrings first.

Sections:   Simulator (1) | generate_plan (2) | Recorder, durability, run_seed (3)
            find_failing_seed, replay_matches (4) | shrink (5) | FixedKVNode, soak (6)
Run `python3 check.py` to see where you are.
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

    Public attributes (the nodes and harness.py use them):
        rng          random.Random(seed): the ONLY source of randomness in the whole run
        now          the current simulated time (an int)
        ghost        a dict nobody but test code looks at (invariants read it)
        nodes        node id -> the live node object, or None while that node is crashed
        durable      node id -> the dict of what is on that node's disk
        trace        a list of strings, one per thing that happened, each starting with the time

    Rules to implement:
      * ONE priority queue of (time, seq, kind, data). seq is a counter that breaks ties, so two
        events at the same time run in the order they were scheduled (and nothing ever has to
        compare two functions). run() pops events in order, sets self.now to each event's time.
      * Messages: send() may DROP a message (probability net.drop) or DUPLICATE it (net.dup), and
        gives each copy a delay from rng.randint(net.min_delay, net.max_delay), so messages
        reorder. But a message from a node to itself, or to or from a node added with client=True,
        is never dropped or duplicated (it is still delayed).
      * A message is delivered only if, AT DELIVERY TIME, the destination is up, it is the SAME
        life of the destination as when the message was sent (see incarnation), and the sender and
        receiver are not in different partition groups. Otherwise it is dropped (and logged).
      * crash(n) throws away the node object (its memory) and bumps the node's incarnation, so
        every message, timer and disk write that belonged to the old life is silently ignored when
        its time comes. restart(n) builds a new node from the factory using a deep copy of the
        durable dict: the new life sees only what had reached the disk.
      * write_disk(n, key, value, cb) puts value on the disk a random time later
        (rng.randint(*disk_delay)), in the order the writes were issued, and then calls cb. If the
        node crashes before that, the write is lost and cb is never called.
      * Everything that happens is appended to self.trace, so the run can be hashed.
    Never use the global `random`, `time`, `id()` or `hash()`, and never iterate a set.
    """

    def __init__(self, seed, net=None, disk_delay=(2, 12)):
        """net is a NetConfig (use DEFAULT_NET if None). Set up an empty cluster at time 0."""
        raise NotImplementedError("TODO milestone 1: Simulator.__init__")

    def add_node(self, node_id, factory, client=False):
        """Register a node and start it: node = factory(node_id, sim, durable_copy), then node.on_start().
        `durable_copy` is a deep copy of self.durable[node_id], which starts as {}."""
        raise NotImplementedError("TODO milestone 1: Simulator.add_node")

    def crash(self, node_id):
        """Lose the node's memory. Does nothing if it is already down. Log it."""
        raise NotImplementedError("TODO milestone 1: Simulator.crash")

    def restart(self, node_id):
        """Boot a new node object from the durable state. Does nothing if the node is up. Log it."""
        raise NotImplementedError("TODO milestone 1: Simulator.restart")

    def schedule(self, delay, fn):
        """Call fn() `delay` ticks from now. Not tied to any node, so it survives crashes."""
        raise NotImplementedError("TODO milestone 1: Simulator.schedule")

    def set_timer(self, node_id, delay, tag):
        """In `delay` ticks call node.on_timer(tag), unless that node has crashed since."""
        raise NotImplementedError("TODO milestone 1: Simulator.set_timer")

    def run(self, until, after_event=None):
        """Run events in order while the next one is due at or before time `until`. If
        after_event is given, call it with no arguments after every event."""
        raise NotImplementedError("TODO milestone 1: Simulator.run")

    def send(self, src, dst, msg):
        """Send msg from src to dst through the faulty network. Deliver with dst's
        node.on_message(src, msg)."""
        raise NotImplementedError("TODO milestone 1: Simulator.send")

    def partition(self, *groups):
        """partition((0,), (1, 2)) cuts node 0 off from nodes 1 and 2. Nodes in no group (clients)
        can talk to everyone. Replaces any earlier partition."""
        raise NotImplementedError("TODO milestone 1: Simulator.partition")

    def heal(self):
        """Remove the partition."""
        raise NotImplementedError("TODO milestone 1: Simulator.heal")

    def write_disk(self, node_id, key, value, cb=None):
        """Save value under key for this node: see the rules above. Store the object as given
        (callers pass a fresh copy)."""
        raise NotImplementedError("TODO milestone 1: Simulator.write_disk")

    def log(self, text):
        """Append f"{self.now} {text}" to the trace."""
        raise NotImplementedError("TODO milestone 1: Simulator.log")

    def trace_hash(self):
        """A hex digest (sha256) of the whole trace. Two runs are the same run iff these are equal."""
        raise NotImplementedError("TODO milestone 1: Simulator.trace_hash")


# =====================================================================================
# Milestone 2: the workload and fault generator
# =====================================================================================

def generate_plan(seed, n_clients=3, ops_per_client=6, horizon=220):
    """A random Plan (see the docstring in harness.py), a pure function of `seed`: the same seed
    must give an equal Plan, in any process.

      ops     n_clients clients x ops_per_client ops: about half writes, half reads, on keys "x" and
              "y", each at a random server 0 to 2. Every write uses a fresh value (1, 2, 3, ...), so
              a read can be traced back to the one write that produced it.
      faults  crash a node, restart it 10 to 60 ticks later (some nodes, some seeds); sometimes
              cut one node off from the others for 20 to 80 ticks and then heal.
              Times fall in [0, horizon + 140]. List them in time order.

    Use a private random.Random for this (for example random.Random(f"plan:{seed}")), not the
    simulator's. Make crashes uncommon (an unlucky seed should be needed): a test that breaks
    every run finds nothing, and a test that breaks nothing finds nothing either."""
    raise NotImplementedError("TODO milestone 2: generate_plan")


# =====================================================================================
# Milestone 3: history recorder, invariants, and run_seed
# =====================================================================================

class Recorder:
    """Called by the clients. Builds linearize.Op objects (see linearize.py)."""

    def invoke(self, process, f, key, value, time):
        """A client starts an op. `process` is a string, unique among pending ops."""
        raise NotImplementedError("TODO milestone 3: Recorder.invoke")

    def ok(self, process, value, time):
        """The op finished: a read returned `value`; for a write `value` is what was written."""
        raise NotImplementedError("TODO milestone 3: Recorder.ok")

    def info(self, process, time):
        """The client gave up. A write becomes indeterminate (ret=INF, indeterminate=True). A read
        is dropped: it says nothing and changes nothing."""
        raise NotImplementedError("TODO milestone 3: Recorder.info")

    def operations(self):
        """All the Ops so far. Ops still pending count as timed out (writes only)."""
        raise NotImplementedError("TODO milestone 3: Recorder.operations")


def durability(sim):
    """An invariant: a node never forgets a write it has acknowledged. Return None if it holds, else
    a short message. KVNode records every acknowledgement in sim.ghost["acked"], a dict
    (node id, key) -> highest timestamp acknowledged. A live node's sim.nodes[id].store[key][0] must
    be at least that. (A crashed node, None in sim.nodes, is skipped.)"""
    raise NotImplementedError("TODO milestone 3: durability")


def run_seed(seed, node_factory=KVNode, plan=None, invariants=(durability,)):
    """One complete simulated run. Use generate_plan(seed) unless a plan is given.

    Call harness.run_plan(plan, seed, simulator_cls=Simulator, node_factory=node_factory,
    recorder=<a new Recorder>, invariants=invariants). It raises InvariantViolation (with .sim)
    if an invariant fires. Otherwise check the history with linearize.check_history(ops): it
    returns None, or the name of a key whose history is not linearizable.

    Return RunResult(seed, ok, reason, trace_hash, plan, trace, operations): ok is True only if
    nothing failed; reason is None or a short sentence saying what failed: start it with
    "invariant violated" for an invariant, or say "not linearizable" for a bad history."""
    raise NotImplementedError("TODO milestone 3: run_seed")


# =====================================================================================
# Milestone 4: seed search and replay
# =====================================================================================

def find_failing_seed(seeds, node_factory=KVNode, invariants=(durability,)):
    """Run run_seed for each seed in order. Return the RunResult of the first failure, or None."""
    raise NotImplementedError("TODO milestone 4: find_failing_seed")


def replay_matches(seed, node_factory=KVNode, invariants=(durability,)):
    """Run the seed twice. True if both runs have the same trace hash and the same verdict."""
    raise NotImplementedError("TODO milestone 4: replay_matches")


# =====================================================================================
# Milestone 5: shrinking
# =====================================================================================

def shrink(failure, node_factory=KVNode, invariants=(durability,)):
    """Given a failing RunResult, return the RunResult of a smaller plan that still fails with the
    SAME seed. Removing any single remaining op or fault must make the run pass.

    Use harness.plan_items(plan) (a flat list) and harness.plan_from_items(items). Try dropping
    one item at a time and keep any removal that still fails; repeat until nothing can go. Then
    make it fast: try dropping big chunks first (delta debugging)."""
    raise NotImplementedError("TODO milestone 5: shrink")


# =====================================================================================
# Milestone 6: the fix, and a soak test
# =====================================================================================

class FixedKVNode(KVNode):
    """KVNode with the bug fixed. Override ONE method of KVNode (read kvstore.py to find which)."""


def soak(seeds, node_factory=FixedKVNode, invariants=(durability,)):
    """Run every seed. Return the list of seeds that failed (empty means all passed)."""
    raise NotImplementedError("TODO milestone 6: soak")
