"""Lab 4: Multi-Paxos Replicated Log.

Everything runs inside one Python process on a simulated network: a seeded random
number generator, a priority queue of in-flight messages (they can be dropped,
duplicated, delayed and reordered), simulated time, and nodes that can crash and
restart. Same seed, same run, every time.

The top half of this file is GIVEN: the simulator, an omniscient Observer that
checks safety, and the plumbing around your code (timers, heartbeats, catch-up,
the client). The parts marked TODO are yours, in five milestones:

  1. Acceptor              the prepare and accept rules, with durable state
  2. Proposer              single-decree Paxos: phase 1, adopt the highest value, phase 2
  3. Proposer.retry_delay  randomized backoff, so duelling proposers stop duelling
  4. Replica               Multi-Paxos: one phase 1 per leader, recovery, no-op gap filling
  5. KVStore + apply       a replicated key-value store with exactly-once client requests

Run `python3 check.py` to see how you are doing.
"""
from __future__ import annotations

import collections
import copy
import heapq
import json
import random
from typing import Any, Callable, Dict, List, Optional, Tuple

Ballot = Tuple[int, int]            # (round, proposer id): totally ordered, unique per proposer
NO_BALLOT: Ballot = (0, 0)          # lower than every real ballot (rounds start at 1)
NOOP: Dict[str, Any] = {"op": "noop"}   # the command that fills a gap in the log


def vkey(value: Any) -> str:
    """A hashable name for a value (values may be dicts)."""
    return json.dumps(value, sort_keys=True)


# =====================================================================================
# GIVEN: the simulator
# =====================================================================================
class Observer:
    """An omniscient referee. No real node can see what this class sees.

    Whenever an acceptor accepts (slot, ballot, value), the Observer counts it. When a
    majority of acceptors have accepted the same value at the same ballot for a slot,
    that value is CHOSEN, whether or not anybody knows it yet. The Observer records a
    violation if two different values are ever chosen for one slot, if a value nobody
    proposed is chosen, or if a node claims a value is chosen when it is not.
    """

    def __init__(self, sim: "Sim") -> None:
        self.sim = sim
        self.n_acceptors = 0
        self.proposed: set = {vkey(NOOP)}          # a no-op is always a legal decision
        self.votes: Dict[tuple, set] = {}
        self.chosen: Dict[int, Tuple[str, Any]] = {}   # slot -> (value key, value)
        self.violations: List[str] = []
        self.acked: List[Tuple[int, str]] = []         # (slot, value key) a leader committed
        self.noops = 0

    def propose(self, value: Any) -> None:
        """The harness (or a client) calls this when a real value enters the system."""
        self.proposed.add(vkey(value))

    def _bad(self, text: str) -> None:
        self.violations.append(f"t={self.sim.now}: {text}")

    def on_accept(self, nid: int, slot: int, ballot: Ballot, value: Any) -> None:
        k = (slot, ballot, vkey(value))
        voters = self.votes.setdefault(k, set())
        voters.add(nid)
        if len(voters) < self.n_acceptors // 2 + 1:
            return
        if slot in self.chosen:
            if self.chosen[slot][0] != k[2]:
                self._bad(f"AGREEMENT BROKEN in slot {slot}: {self.chosen[slot][1]!r} was already "
                          f"chosen, and now {value!r} is chosen too (ballot {ballot})")
            return
        self.chosen[slot] = (k[2], value)
        if k[2] == vkey(NOOP):
            self.noops += 1
        if k[2] not in self.proposed:
            self._bad(f"VALIDITY BROKEN in slot {slot}: {value!r} was chosen but nobody proposed it")

    def committed(self, nid: int, slot: int, value: Any) -> None:
        """A leader says: 'a majority accepted this, it is chosen'."""
        if slot not in self.chosen or self.chosen[slot][0] != vkey(value):
            self._bad(f"node {nid} committed slot {slot} = {value!r}, but a majority has not accepted "
                      f"that (chosen so far: {self.chosen.get(slot, ('', None))[1]!r})")
        self.acked.append((slot, vkey(value)))

    def learned(self, nid: int, slot: int, value: Any) -> None:
        """A node says: 'I now know slot = value is chosen'."""
        if slot not in self.chosen or self.chosen[slot][0] != vkey(value):
            self._bad(f"node {nid} learned slot {slot} = {value!r}, which is not what was chosen "
                      f"({self.chosen.get(slot, ('', None))[1]!r})")


class Sim:
    """A deterministic discrete-event simulator: nodes, a lossy network, timers, crashes."""

    def __init__(self, seed: int, drop: float = 0.0, dup: float = 0.0,
                 min_delay: int = 1, max_delay: int = 8, auto_elect: bool = True) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.drop, self.dup = drop, dup
        self.min_delay, self.max_delay = min_delay, max_delay
        self.auto_elect = auto_elect
        self.now = 0
        self._heap: list = []
        self._seq = 0
        self.nodes: Dict[int, "Node"] = {}
        self.up: Dict[int, bool] = {}
        self.disks: Dict[int, dict] = {}        # durable storage: survives crash and restart
        self.factories: Dict[int, Callable] = {}
        self.epoch: Dict[int, int] = {}         # bumped on every crash: kills the old timers
        self.trace: collections.deque = collections.deque(maxlen=600)
        self.sent: collections.Counter = collections.Counter()
        self.observer = Observer(self)

    # ---- building the cluster ----
    def add(self, nid: int, factory: Callable, disk: Optional[dict] = None) -> "Node":
        """factory(nid, sim, disk) -> Node. Called again on every restart, with the SAME disk."""
        self.factories[nid] = factory
        self.disks[nid] = {} if disk is None else disk
        self.up[nid] = True
        self.epoch[nid] = 0
        node = factory(nid, self, self.disks[nid])
        self.nodes[nid] = node
        node.on_start()
        return node

    # ---- the network ----
    def _push(self, when: int, event: tuple) -> None:
        self._seq += 1
        heapq.heappush(self._heap, (when, self._seq, event))

    def send(self, src: int, dst: int, msg: dict) -> None:
        self.sent[msg["t"]] += 1
        if src == dst:                           # a node talking to itself: reliable, immediate
            self._push(self.now, ("msg", src, dst, copy.deepcopy(msg)))
            return
        if self.rng.random() < self.drop:
            self.trace.append((self.now, "lost", src, dst, msg))
            return
        copies = 2 if self.rng.random() < self.dup else 1
        for _ in range(copies):
            delay = self.rng.randint(self.min_delay, self.max_delay)
            self._push(self.now + delay, ("msg", src, dst, copy.deepcopy(msg)))

    def set_timer(self, nid: int, delay: int, name: str) -> None:
        self._push(self.now + max(0, int(delay)), ("timer", nid, self.epoch[nid], name))

    def schedule(self, when: int, fn: Callable[[], None]) -> None:
        """Run fn() at simulated time `when` (used by checks to inject crashes)."""
        self._push(when, ("call", fn))

    def log(self, nid: int, text: str) -> None:
        self.trace.append((self.now, "note", nid, text, None))

    # ---- failures ----
    def crash(self, nid: int) -> None:
        if self.up[nid]:
            self.up[nid] = False
            self.epoch[nid] += 1
            self.trace.append((self.now, "crash", nid, None, None))

    def restart(self, nid: int) -> None:
        if not self.up[nid]:
            self.up[nid] = True
            self.trace.append((self.now, "restart", nid, None, None))
            node = self.factories[nid](nid, self, self.disks[nid])   # new object, same disk
            self.nodes[nid] = node
            node.on_start()

    # ---- running ----
    def run(self, until: int, stop: Optional[Callable[[], bool]] = None) -> None:
        """Process events up to simulated time `until`, or until stop() is true or a violation occurs."""
        while self._heap and self._heap[0][0] <= until:
            when, _, ev = heapq.heappop(self._heap)
            self.now = when
            kind = ev[0]
            if kind == "msg":
                _, src, dst, msg = ev
                if not self.up[dst]:
                    self.trace.append((self.now, "dead", src, dst, msg))
                    continue
                self.trace.append((self.now, "deliver", src, dst, msg))
                self.nodes[dst].on_message(src, msg)
            elif kind == "timer":
                _, nid, epoch, name = ev
                if self.up[nid] and self.epoch[nid] == epoch:
                    self.nodes[nid].on_timer(name)
            else:
                ev[1]()
            if self.observer.violations or (stop is not None and stop()):
                return
        if not (stop is not None and stop()):
            self.now = max(self.now, until)

    # ---- readable traces ----
    @staticmethod
    def _short(msg: dict) -> str:
        parts = [msg["t"]] + [f"{k}={v}" for k, v in msg.items() if k != "t"]
        s = " ".join(parts)
        return s if len(s) <= 100 else s[:97] + "..."

    def format_trace(self, last: int = 25) -> List[str]:
        out = []
        for (t, kind, a, b, msg) in list(self.trace)[-last:]:
            if kind == "deliver":
                out.append(f"t={t:5d}  {a:>3} -> {b:<3} {self._short(msg)}")
            elif kind == "lost":
                out.append(f"t={t:5d}  {a:>3} -> {b:<3} {self._short(msg)}   [LOST]")
            elif kind == "dead":
                out.append(f"t={t:5d}  {a:>3} -> {b:<3} {self._short(msg)}   [node is down]")
            elif kind == "note":
                out.append(f"t={t:5d}  node {a}: {b}")
            else:
                out.append(f"t={t:5d}  ***** node {a} {kind.upper()} *****")
        return out


class Node:
    """Base class for everything that lives on the network."""

    def __init__(self, nid: int, sim: Sim, disk: dict) -> None:
        self.id, self.sim, self.disk = nid, sim, disk

    def send(self, dst: int, msg: dict) -> None:
        self.sim.send(self.id, dst, msg)

    def broadcast(self, dsts: List[int], msg: dict) -> None:
        for d in dsts:
            self.send(d, msg)

    def set_timer(self, delay: int, name: str) -> None:
        self.sim.set_timer(self.id, delay, name)

    def log(self, text: str) -> None:
        self.sim.log(self.id, text)

    def on_start(self) -> None:                   # called at boot and again after every restart
        pass

    def on_message(self, src: int, msg: dict) -> None:
        pass

    def on_timer(self, name: str) -> None:
        pass


# =====================================================================================
# MILESTONE 1: the acceptor
# =====================================================================================
class Acceptor:
    """The memory of the system. Its whole state lives in `disk`, which survives a crash:

        disk["promised"]  the highest ballot this acceptor has promised (NO_BALLOT at first)
        disk["accepted"]  {slot: (ballot, value)}, the proposal accepted for each slot

    A promise names a BALLOT, not a slot: "promise(b)" covers every slot at once. That is
    the fact Multi-Paxos is built on (milestone 4). Single-decree Paxos (milestones 2 and 3)
    simply uses slot 0 only.
    """

    def __init__(self, disk: dict) -> None:
        self.disk = disk
        disk.setdefault("promised", NO_BALLOT)
        disk.setdefault("accepted", {})

    def on_prepare(self, ballot: Ballot) -> tuple:
        """Phase 1b. Return ("promise", accepted) or ("nack", promised).

        1. If `ballot` is higher than disk["promised"]: record it and return
           ("promise", {slot: (ballot, value), ...}), a COPY of everything accepted so far.
        2. Otherwise refuse: return ("nack", disk["promised"]) so the proposer learns
           which ballot to beat.
        """
        if ballot > self.disk["promised"]:
            self.disk["promised"] = ballot
            return ("promise", dict(self.disk["accepted"]))
        return ("nack", self.disk["promised"])

    def on_accept(self, ballot: Ballot, slot: int, value: Any) -> tuple:
        """Phase 2b. Return ("accepted", ballot) or ("nack", promised).

        1. If `ballot` is at least disk["promised"] (equal is fine: it is the ballot this
           acceptor promised to): set promised = ballot, store accepted[slot] = (ballot, value),
           and return ("accepted", ballot).
        2. Otherwise return ("nack", disk["promised"]).

        Compare with on_prepare: the two rules differ by one character, `>` against `>=`.
        """
        if ballot >= self.disk["promised"]:
            self.disk["promised"] = ballot
            self.disk["accepted"][slot] = (ballot, value)
            return ("accepted", ballot)
        return ("nack", self.disk["promised"])


def handle_acceptor(node: Node, acc: Acceptor, src: int, msg: dict) -> tuple:
    """GIVEN glue: run your Acceptor on a prepare/accept message and send the reply."""
    if msg["t"] == "prepare":
        r = acc.on_prepare(msg["b"])
        if r[0] == "promise":
            node.send(src, {"t": "promise", "b": msg["b"], "accepted": r[1]})
        else:
            node.send(src, {"t": "nack", "b": msg["b"], "promised": r[1]})
    else:
        r = acc.on_accept(msg["b"], msg["slot"], msg["v"])
        if r[0] == "accepted":
            node.sim.observer.on_accept(node.id, msg["slot"], msg["b"], msg["v"])
            node.send(src, {"t": "accepted", "b": msg["b"], "slot": msg["slot"]})
        else:
            node.send(src, {"t": "nack", "b": msg["b"], "promised": r[1]})
    return r


class AcceptorNode(Node):
    """GIVEN: a machine that is only an acceptor (used by milestones 2 and 3)."""

    def __init__(self, nid: int, sim: Sim, disk: dict) -> None:
        super().__init__(nid, sim, disk)
        self.acc = Acceptor(disk)

    def on_message(self, src: int, msg: dict) -> None:
        if msg["t"] in ("prepare", "accept"):
            handle_acceptor(self, self.acc, src, msg)


# =====================================================================================
# MILESTONES 2 and 3: the single-decree proposer
# =====================================================================================
TIMEOUT = 60        # a round that has not finished after this long is assumed lost (a message was dropped)
RETRY_CAP = 400


class Proposer(Node):
    """Wants the system to choose `value`. Ballot = (round, own id). Uses slot 0 only.

    State (all soft: a crashed proposer may simply start again with a higher round):
      round, attempt   counters; every begin_round() bumps both
      ballot           (round, self.id) of the current attempt
      promises         {acceptor id: what that acceptor reported for slot 0 (or None)}
      proposal         the value sent in phase 2 (None until phase 2 starts)
      accepted_by      acceptors that accepted our proposal
      chosen           the value we have learned is chosen (None until then)
    """

    def __init__(self, nid: int, sim: Sim, disk: dict, acceptors: List[int], value: Any,
                 start_at: int = 0) -> None:
        super().__init__(nid, sim, disk)
        self.acceptors, self.value, self.start_at = list(acceptors), value, start_at
        self.quorum = len(self.acceptors) // 2 + 1
        self.round = 0
        self.attempt = 0
        self.ballot: Ballot = NO_BALLOT
        self.promises: Dict[int, Any] = {}
        self.proposal: Any = None
        self.accepted_by: set = set()
        self.chosen: Any = None
        self.timer_gen = 0

    # ---- given plumbing ----
    def on_start(self) -> None:
        self.set_timer(self.start_at, "start")

    def arm_retry(self, delay: int = TIMEOUT) -> None:
        """Start (or replace) the single retry timer: in `delay` ticks, begin a new round."""
        self.timer_gen += 1
        self.set_timer(delay, f"retry:{self.timer_gen}")

    def on_timer(self, name: str) -> None:
        kind, _, gen = name.partition(":")
        if self.chosen is None and (kind == "start" or int(gen) == self.timer_gen):
            self.begin_round()

    # ---- milestone 3 ----
    def retry_delay(self, attempt: int) -> int:
        """How long to wait after a nack before trying again with a higher ballot.

        Milestone 2 ships with 0: retry at once. Two proposers that do that to each other
        can duel for a long time (livelock). Milestone 3: return a RANDOMIZED, exponentially
        growing delay. Use self.sim.rng (never the `random` module: runs must be replayable).
        For example: cap = min(20 * 2**(attempt-1), RETRY_CAP), then a random value in
        [cap//2, cap]. `attempt` is 1 for the first retry.
        """
        cap = min(20 * 2 ** (attempt - 1), RETRY_CAP)
        return self.sim.rng.randint(cap // 2, cap)

    # ---- milestone 2 ----
    def begin_round(self) -> None:
        """Phase 1a: start a new attempt.

        1. round += 1 and attempt += 1; ballot = (round, self.id).
        2. Reset promises, proposal and accepted_by.
        3. Send {"t": "prepare", "b": ballot} to every acceptor.
        4. Call self.arm_retry(), so a lost message cannot stall you forever.
        """
        self.round += 1
        self.attempt += 1
        self.ballot = (self.round, self.id)
        self.promises, self.proposal, self.accepted_by = {}, None, set()
        self.broadcast(self.acceptors, {"t": "prepare", "b": self.ballot})
        self.arm_retry()

    def on_message(self, src: int, msg: dict) -> None:
        """Handle a reply from an acceptor.

        {"t": "promise", "b": ballot, "accepted": {slot: (ballot, value)}}   phase 1b
        {"t": "accepted", "b": ballot, "slot": 0}                            phase 2b
        {"t": "nack", "b": ballot, "promised": higher_ballot}                a refusal

        Rules:
        * Once self.chosen is set, ignore everything.
        * nack: if msg["promised"] is HIGHER than our ballot, set round = max(round,
          msg["promised"][0]) so the next ballot beats it, then call
          self.arm_retry(self.retry_delay(self.attempt)). (A nack with promised equal to
          our own ballot is just a duplicate: ignore it.)
        * Ignore any promise/accepted whose "b" is not our current ballot (it is late).
        * promise: remember what src reported for slot 0 (msg["accepted"].get(0), or None).
          When promises come from a QUORUM and phase 2 has not started: pick the value.
          If any acceptor reported an accepted proposal, you MUST use the value of the one
          with the HIGHEST ballot; only if none did may you use self.value. Set
          self.proposal and send {"t": "accept", "b": ballot, "slot": 0, "v": value}
          to every acceptor.
        * accepted: add src to accepted_by (only once phase 2 has started). When a QUORUM
          of acceptors accepted, the value is chosen: set self.chosen = self.proposal.
        """
        if self.chosen is not None:
            return
        t = msg["t"]
        if t == "nack":
            if msg["promised"] > self.ballot:
                self.round = max(self.round, msg["promised"][0])
                self.arm_retry(self.retry_delay(self.attempt))
            return
        if msg["b"] != self.ballot:
            return
        if t == "promise" and self.proposal is None:
            self.promises[src] = msg["accepted"].get(0)
            if len(self.promises) >= self.quorum:
                reports = [r for r in self.promises.values() if r is not None]
                # the adoption rule: the value of the highest-ballot accepted proposal
                self.proposal = max(reports, key=lambda r: r[0])[1] if reports else self.value
                self.broadcast(self.acceptors,
                               {"t": "accept", "b": self.ballot, "slot": 0, "v": self.proposal})
        elif t == "accepted" and self.proposal is not None:
            self.accepted_by.add(src)
            if len(self.accepted_by) >= self.quorum:
                self.chosen = self.proposal
                self.log(f"learned that {self.chosen!r} is chosen (ballot {self.ballot})")


# =====================================================================================
# MILESTONES 4 and 5: Multi-Paxos replicas and a key-value store
# =====================================================================================
HEARTBEAT = 20                  # the leader sends a heartbeat (and retransmits) this often
ELECTION_MIN, ELECTION_MAX = 90, 180   # a follower that hears nothing for this long runs for leader
CLIENT_TIMEOUT = 120


class KVStore:
    """The state machine: a dictionary. Every replica applies the same commands in the same order.

    A command is a dict: {"client": id, "seq": n, "op": "put"|"get"|"incr"|"append", "key": k, "arg": a}
    (or NOOP). Each client has at most one request outstanding and numbers its requests
    1, 2, 3, ... A retried request carries the SAME seq as the original.
    """

    def __init__(self) -> None:
        self.data: Dict[str, Any] = {}
        self.sessions: Dict[int, Tuple[int, Any]] = {}     # client -> (last seq executed, its result)

    def _execute(self, cmd: dict) -> Any:
        """GIVEN: do the operation (no duplicate protection here)."""
        op, key, arg = cmd["op"], cmd.get("key"), cmd.get("arg")
        if op == "put":
            self.data[key] = arg
            return "ok"
        if op == "get":
            return self.data.get(key)
        if op == "incr":
            self.data[key] = self.data.get(key, 0) + arg
            return self.data[key]
        if op == "append":
            self.data[key] = self.data.get(key, "") + arg
            return self.data[key]
        raise ValueError(f"unknown op {op!r}")

    def apply(self, cmd: dict) -> Any:
        """MILESTONE 5. Apply one chosen command and return its result.

        * A NOOP (cmd["op"] == "noop") does nothing and returns None.
        * Exactly once: self.sessions[client] = (seq, result) remembers the last request
          this client had executed. If cmd["seq"] equals that seq, this is a retry that
          was chosen again in a later slot: return the remembered result and do NOT
          execute it again. If it is LOWER than that seq, the client has long moved on:
          return None. Otherwise execute it with self._execute(cmd) and remember it.
        """
        if cmd["op"] == "noop":
            return None
        client, seq = cmd["client"], cmd["seq"]
        last = self.sessions.get(client)
        if last is not None:
            if seq == last[0]:
                return last[1]
            if seq < last[0]:
                return None
        result = self._execute(cmd)
        self.sessions[client] = (seq, result)
        return result


class Replica(Node):
    """One machine that is acceptor, proposer (when leading) and learner, all in one.

    Durable: only the Acceptor's state (self.disk). Everything else is rebuilt after a
    restart from the log, which the leader re-sends.

    Your parts: start_phase1, on_promise, send_accept (with propose), on_accepted (milestone 4)
    and apply_ready (milestone 5). Everything else is given. In particular the given code
      * runs an election timer (randomized) and calls start_phase1() when it fires,
      * steps down when it sees a higher ballot,
      * sends heartbeats, retransmits accepts for pending slots, and catches followers up,
      * answers clients.
    """

    def __init__(self, nid: int, sim: Sim, disk: dict, peers: List[int]) -> None:
        super().__init__(nid, sim, disk)
        self.peers = list(peers)
        self.quorum = len(self.peers) // 2 + 1
        self.acc = Acceptor(disk)
        self.max_round = disk["promised"][0]        # highest ballot round ever seen
        # leader state (volatile)
        self.ballot: Ballot = NO_BALLOT             # the ballot I am campaigning or leading with
        self.electing = False                       # phase 1 in progress
        self.leading = False                        # phase 1 complete: I may run phase 2
        self.promises: Dict[int, dict] = {}         # acceptor id -> its accepted map
        self.pending: Dict[int, Any] = {}           # slot -> value I proposed, not yet committed
        self.votes: Dict[int, set] = {}             # slot -> acceptors that accepted it at my ballot
        self.next_slot = 1                          # the next free slot
        self.leader_hint: Optional[int] = None
        self.follower_upto: Dict[int, int] = {}
        # learner and state machine (volatile)
        self.chosen: Dict[int, Any] = {}            # slot -> value known to be chosen
        self.applied = 0                            # slots 1..applied are applied
        self.kv = KVStore()
        self.election_gen = 0

    # ---------------- given: timers and leadership plumbing ----------------
    def on_start(self) -> None:
        self.reset_election_timer()
        self.set_timer(HEARTBEAT, "tick")

    def reset_election_timer(self) -> None:
        self.election_gen += 1
        self.set_timer(self.sim.rng.randint(ELECTION_MIN, ELECTION_MAX), f"election:{self.election_gen}")

    def on_timer(self, name: str) -> None:
        kind, _, gen = name.partition(":")
        if kind == "election" and int(gen) == self.election_gen:
            if self.sim.auto_elect and not self.leading:
                self.start_phase1()
            self.reset_election_timer()
        elif kind == "tick":
            self.set_timer(HEARTBEAT, "tick")
            if self.leading:
                self.broadcast(self.peers, {"t": "hb", "b": self.ballot})
                for slot, value in sorted(self.pending.items()):      # retransmit: accepts can be lost
                    self.broadcast(self.peers, {"t": "accept", "b": self.ballot, "slot": slot, "v": value})
                for p in self.peers:                                  # catch followers up
                    upto = self.follower_upto.get(p, 0)
                    entries = {s: self.chosen[s] for s in range(upto + 1, upto + 41) if s in self.chosen}
                    if p != self.id and entries:
                        self.send(p, {"t": "learn", "entries": entries})

    def step_down(self) -> None:
        if self.leading or self.electing:
            self.log(f"steps down (was ballot {self.ballot})")
        self.leading = self.electing = False
        self.pending.clear()
        self.votes.clear()
        self.promises.clear()

    def on_message(self, src: int, msg: dict) -> None:
        t = msg["t"]
        if "b" in msg:
            self.max_round = max(self.max_round, msg["b"][0])
        if t in ("prepare", "accept"):
            r = handle_acceptor(self, self.acc, src, msg)
            promised = self.disk["promised"]
            self.max_round = max(self.max_round, promised[0])
            if promised > self.ballot:               # somebody with a higher ballot has my acceptor's promise
                self.step_down()
            if r[0] != "nack" and src != self.id:    # a live proposer with a valid ballot: do not run against it
                if t == "accept":
                    self.leader_hint = src
                self.reset_election_timer()
        elif t == "nack":
            self.max_round = max(self.max_round, msg["promised"][0])
            if msg["promised"] > self.ballot:
                self.step_down()
        elif t == "promise":
            self.on_promise(src, msg)
        elif t == "accepted":
            self.on_accepted(src, msg)
        elif t == "learn":
            for slot, value in sorted(msg["entries"].items()):
                self.record_chosen(slot, value)
        elif t == "hb":
            if msg["b"] >= self.disk["promised"]:
                if msg["b"] > self.ballot:
                    self.step_down()
                self.leader_hint = src
                self.reset_election_timer()
                self.send(src, {"t": "hb_ack", "upto": self.applied})
            else:
                self.send(src, {"t": "nack", "b": msg["b"], "promised": self.disk["promised"]})
        elif t == "hb_ack":
            self.follower_upto[src] = msg["upto"]
        elif t == "req":
            self.on_client_request(src, msg)

    def on_client_request(self, src: int, msg: dict) -> None:
        if self.leading:
            self.propose(msg["cmd"])
        else:
            self.send(src, {"t": "redirect", "seq": msg["cmd"]["seq"], "leader": self.leader_hint})

    def commit(self, slot: int, value: Any) -> None:
        """GIVEN. A majority accepted (slot, value): it is chosen. Record it and tell everyone."""
        self.sim.observer.committed(self.id, slot, value)
        self.log(f"commits slot {slot} = {value!r}")
        self.record_chosen(slot, value)
        self.broadcast([p for p in self.peers if p != self.id],
                       {"t": "learn", "entries": {slot: value}})

    def record_chosen(self, slot: int, value: Any) -> None:
        """GIVEN. Learn that slot = value is chosen, then apply whatever is now applicable."""
        self.sim.observer.learned(self.id, slot, value)
        self.chosen[slot] = value
        self.apply_ready()

    def reply_to_client(self, cmd: dict, result: Any) -> None:
        """GIVEN. Only the current leader answers clients."""
        if self.leading and cmd.get("client") in self.sim.nodes:
            self.send(cmd["client"], {"t": "resp", "seq": cmd["seq"], "result": result})

    # ---------------- milestone 4: your code ----------------
    def start_phase1(self) -> None:
        """Phase 1a for the WHOLE log: campaign for leadership.

        1. Pick a ballot above every round you have seen: (self.max_round + 1, self.id),
           and set self.max_round to that round.
        2. Set self.ballot, self.electing = True, self.leading = False, and clear
           self.promises, self.pending and self.votes.
        3. Send {"t": "prepare", "b": ballot} to every peer (yourself included: your own
           acceptor counts towards the quorum like any other).

        There is no slot in a prepare. One promise covers every slot.
        """
        self.max_round += 1
        self.ballot = (self.max_round, self.id)
        self.electing, self.leading = True, False
        self.promises, self.pending, self.votes = {}, {}, {}
        self.log(f"starts phase 1 with ballot {self.ballot}")
        self.broadcast(self.peers, {"t": "prepare", "b": self.ballot})

    def on_promise(self, src: int, msg: dict) -> None:
        """Phase 1b arrives: {"t": "promise", "b": ballot, "accepted": {slot: (ballot, value)}}.

        1. Ignore it unless self.electing and msg["b"] == self.ballot.
        2. Record self.promises[src] = msg["accepted"]. Wait for a QUORUM of promises.
        3. At the quorum, you are the leader: set electing = False, leading = True.
        4. RECOVERY. For every slot, look at what the promises reported and keep the entry
           with the HIGHEST ballot. Let `last` be the highest slot mentioned by any promise
           or already in self.chosen. For each slot in 1..last that is not already in
           self.chosen, call self.send_accept(slot, value), where value is the highest-ballot
           reported value, or NOOP if no promise mentioned the slot (a GAP: fill it with a
           no-op so the log can advance).
        5. Set self.next_slot = last + 1: new commands go after the recovered ones.
        """
        if not self.electing or msg["b"] != self.ballot:
            return
        self.promises[src] = msg["accepted"]
        if len(self.promises) < self.quorum:
            return
        self.electing, self.leading = False, True
        best: Dict[int, tuple] = {}
        for accepted in self.promises.values():
            for slot, (b, v) in accepted.items():
                if slot not in best or b > best[slot][0]:
                    best[slot] = (b, v)
        last = max(list(best) + list(self.chosen) + [0])
        self.next_slot = last + 1
        self.log(f"is leader with ballot {self.ballot}; recovering slots 1..{last}")
        for slot in range(1, last + 1):
            if slot not in self.chosen:
                self.send_accept(slot, best[slot][1] if slot in best else NOOP)

    def send_accept(self, slot: int, value: Any) -> None:
        """Phase 2a for one slot: remember it and ask everybody to accept it.

        Set self.pending[slot] = value, self.votes[slot] = set(), and send
        {"t": "accept", "b": self.ballot, "slot": slot, "v": value} to every peer.
        """
        self.pending[slot] = value
        self.votes[slot] = set()
        self.broadcast(self.peers, {"t": "accept", "b": self.ballot, "slot": slot, "v": value})

    def propose(self, cmd: dict) -> None:
        """GIVEN. A leader puts a new command in the next free slot: no phase 1 needed."""
        slot = self.next_slot
        self.next_slot += 1
        self.send_accept(slot, cmd)

    def on_accepted(self, src: int, msg: dict) -> None:
        """Phase 2b arrives: {"t": "accepted", "b": ballot, "slot": s}.

        Ignore it unless we are leading and msg["b"] == self.ballot and the slot is still in
        self.pending. Add src to self.votes[slot]. When a QUORUM has accepted, remove the
        slot from pending and votes and call self.commit(slot, value).
        """
        slot = msg["slot"]
        if not self.leading or msg["b"] != self.ballot or slot not in self.pending:
            return
        self.votes[slot].add(src)
        if len(self.votes[slot]) >= self.quorum:
            value = self.pending.pop(slot)
            del self.votes[slot]
            self.commit(slot, value)

    # ---------------- milestone 5: your code ----------------
    def apply_ready(self) -> None:
        """Apply the chosen log to the state machine, IN SLOT ORDER, with no gaps.

        While slot self.applied + 1 is in self.chosen: advance self.applied, apply that
        command with self.kv.apply(cmd) (a NOOP just advances), and give the result to
        self.reply_to_client(cmd, result). Stop at the first slot you do not know: a later
        slot may be known, but it must wait.
        """
        while self.applied + 1 in self.chosen:
            self.applied += 1
            cmd = self.chosen[self.applied]
            if cmd["op"] == "noop":
                continue
            self.reply_to_client(cmd, self.kv.apply(cmd))


class Client(Node):
    """GIVEN: sends its operations one at a time, retrying with the SAME seq until answered."""

    def __init__(self, nid: int, sim: Sim, disk: dict, replicas: List[int], ops: List[tuple],
                 start_at: int = 0) -> None:
        super().__init__(nid, sim, disk)
        self.replicas, self.ops, self.start_at = list(replicas), list(ops), start_at
        self.index = 0                      # which operation we are on
        self.target = self.replicas[0]
        self.results: List[Any] = []
        self.done_at: Optional[int] = None

    def on_start(self) -> None:
        self.set_timer(self.start_at, "go")

    def current(self) -> Optional[dict]:
        if self.index >= len(self.ops):
            return None
        op, key, arg = self.ops[self.index]
        return {"client": self.id, "seq": self.index + 1, "op": op, "key": key, "arg": arg}

    def transmit(self) -> None:
        cmd = self.current()
        if cmd is None:
            return
        self.sim.observer.propose(cmd)
        self.send(self.target, {"t": "req", "cmd": cmd})
        self.set_timer(CLIENT_TIMEOUT, f"retry:{cmd['seq']}")

    def on_timer(self, name: str) -> None:
        kind, _, seq = name.partition(":")
        if kind == "go":
            self.transmit()
        elif self.index + 1 == int(seq):              # still waiting for that request: try elsewhere
            self.target = self.sim.rng.choice(self.replicas)
            self.transmit()

    def on_message(self, src: int, msg: dict) -> None:
        if msg["seq"] != self.index + 1:
            return                                    # an old answer to an old request
        if msg["t"] == "resp":
            self.results.append(msg["result"])
            self.index += 1
            if self.index == len(self.ops):
                self.done_at = self.sim.now
            self.transmit()
        elif msg["t"] == "redirect" and msg["leader"] is not None:
            self.target = msg["leader"]
            self.transmit()


# =====================================================================================
# GIVEN: a demo. Run `python3 solution.py` to watch a leader crash and a new one take over.
# =====================================================================================
def demo(seed: int = 7) -> None:
    sim = Sim(seed, drop=0.05, min_delay=1, max_delay=6)
    ids = [1, 2, 3]
    sim.observer.n_acceptors = 3
    for i in ids:
        sim.add(i, lambda nid, s, d: Replica(nid, s, d, ids))
    ops = [("incr", "n", 1), ("append", "log", "a"), ("incr", "n", 1), ("append", "log", "b"),
           ("put", "x", 42), ("get", "n", None)]
    sim.add(100, lambda nid, s, d: Client(nid, s, d, ids, ops, start_at=300))
    sim.run(500)
    leader = next((i for i in ids if sim.nodes[i].leading), None)
    if leader is not None:
        sim.crash(leader)                               # kill the leader mid-workload
        sim.schedule(sim.now + 400, lambda: sim.restart(leader))
    sim.run(2500, stop=lambda: sim.nodes[100].done_at is not None and sim.now > 1200)
    sim.run(sim.now + 200)
    for line in sim.format_trace(600):
        if "node" in line and ("commits" in line or "leader" in line or "CRASH" in line
                               or "RESTART" in line or "phase 1" in line or "steps down" in line):
            print(line)
    print("client results:", sim.nodes[100].results)
    for i in ids:
        n = sim.nodes[i]
        print(f"replica {i}: applied={n.applied} data={n.kv.data}")


if __name__ == "__main__":
    demo()
