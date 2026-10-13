"""Lab 5: Two-Phase Commit & Recovery  --  starter.

Everything runs inside ONE process.  A seeded simulator (class Sim) plays the part of the
network (delays, drops, duplicates, reordering), of time, and of crashes.  There are no
threads, sockets or real clocks, so a run is fully determined by its seed.

The file has two halves:

  GIVEN        the simulator, the log, the lock table and a few helpers.  Read it, don't edit it.
  YOURS        Participant, Coordinator, ReplicatedCoordinator, ReplicatedParticipant.
               (DecisionStore is given too: it is the "fake consensus" of milestone 5.)

The one rule of the simulated machine room:

  * `self.log` is DURABLE.  It survives a crash.  It is the only thing that does.
  * Everything else on a node is VOLATILE.  When a node crashes, every attribute except
    name/sim/cfg/log/up/epoch is deleted, and on restart init_volatile() and then on_start()
    run again.  So whatever you need after a crash must be rebuilt from self.log.
"""
import copy
import heapq
import random

# =============================================================================================
# GIVEN: the simulated machine room
# =============================================================================================

NET_DELAY = (1.0, 5.0)        # every message takes between 1 and 5 time units
VOTE_TIMEOUT = 30.0           # coordinator: how long to wait for votes before aborting
RESEND_EVERY = 15.0           # coordinator: resend the decision this often until acked
INQUIRE_EVERY = 15.0          # participant: ask about an in-doubt transaction this often
STORE_WAIT = 20.0             # replicated variant: ask the decision store after this long in doubt

# Crash points.  Your code must call self.point(NAME) at each of these places (see the page).
P_POINTS = ["p:before_prepare_log", "p:after_prepare_log", "p:after_vote_sent",
            "p:before_decision_log", "p:after_decision_log"]
C_POINTS = ["c:after_prepare_sent", "c:after_votes", "c:after_decision_log",
            "c:mid_send", "c:before_end"]
CR_POINTS = ["c:after_store_decide"]          # only the replicated coordinator reaches this one


class Crash(Exception):
    """Raised by Node.point() when the simulator decides this node dies right here."""

    def __init__(self, restart_after=40.0, why=""):
        super().__init__(why)
        self.restart_after = restart_after
        self.why = why


class Log:
    """A node's durable write-ahead log: an append-only list of (time, record) pairs.

    Records are tuples such as ("PREPARED", tx, writes).  Appending deep-copies the record, so
    the log never shares memory with live objects.  Iterating gives the records in order."""

    def __init__(self, sim, owner):
        self.sim, self.owner, self.records = sim, owner, []

    def append(self, rec):
        rec = copy.deepcopy(rec)
        self.records.append((self.sim.time, rec))
        self.sim.trace.append(("log", self.sim.time, self.owner, rec))

    def __iter__(self):
        return (rec for _, rec in self.records)

    def __len__(self):
        return len(self.records)

    def time_of(self, kind, tx):
        """Time the first record of this kind for this transaction was written, or None."""
        for t, rec in self.records:
            if rec[0] == kind and rec[1] == tx:
                return t
        return None


class LockTable:
    """key -> transaction id.  Volatile: a crash empties it, so rebuild it from the log."""

    def __init__(self):
        self.held = {}

    def holder(self, key):
        return self.held.get(key)

    def try_acquire(self, tx, keys):
        """All-or-nothing.  Re-entrant for the same tx.  Returns False if another tx holds a key."""
        keys = list(keys)
        if any(self.held.get(k, tx) != tx for k in keys):
            return False
        for k in keys:
            self.held[k] = tx
        return True

    def release(self, tx):
        for k in [k for k, v in self.held.items() if v == tx]:
            del self.held[k]

    def __len__(self):
        return len(self.held)


def outcome(log, tx):
    """"COMMIT" or "ABORT" if this PARTICIPANT's log holds a decision for tx, else None."""
    for rec in log:
        if rec[0] in ("COMMIT", "ABORT") and rec[1] == tx:
            return rec[0]
    return None


def prepared_writes(log, tx):
    """The writes from this participant's PREPARED record for tx, or None if it never prepared."""
    for rec in log:
        if rec[0] == "PREPARED" and rec[1] == tx:
            return rec[2]
    return None


class Node:
    """Base class.  Override init_volatile / on_start / on_message / on_timer."""

    immortal = False                 # True: the simulator never crashes this node
    KEEP = {"name", "sim", "cfg", "log", "up", "epoch"}

    def __init__(self, sim, name, cfg=None):
        self.sim, self.name, self.cfg = sim, name, cfg or {}
        self.log = Log(sim, name)
        self.up, self.epoch = True, 0
        sim.nodes[name] = self
        self.init_volatile()

    # ---- hooks -------------------------------------------------------------------------
    def init_volatile(self):
        """Create all volatile state here.  Runs at creation and again after every crash."""

    def on_start(self):
        """Runs at boot and after every restart.  This is where recovery happens."""

    def on_message(self, src, msg):
        pass

    def on_timer(self, tag):
        pass

    # ---- services ----------------------------------------------------------------------
    @property
    def now(self):
        return self.sim.time

    def send(self, dst, msg):
        self.sim.send(self.name, dst, msg)

    def set_timer(self, delay, tag):
        self.sim.set_timer(self, delay, tag)

    def point(self, name):
        """A place where the simulator may crash this node (it raises Crash)."""
        self.sim.hit(self, name)


class Sim:
    """The whole world: time, an event queue, a lossy network, and crash injection."""

    def __init__(self, seed=0, drop=0.0, dup=0.0, delay=NET_DELAY):
        self.seed, self.rng = seed, random.Random(seed)
        self.time = 0.0
        self.drop, self.dup, self.delay = drop, dup, delay
        self.nodes, self.trace = {}, []
        self._q, self._n = [], 0
        self._specs, self._chaos = [], None
        self.hits, self.crashes, self._started = {}, 0, False

    # ---- scheduling --------------------------------------------------------------------
    def _push(self, t, kind, *args):
        self._n += 1
        heapq.heappush(self._q, (t, self._n, kind, args))

    def at(self, t, fn):
        """Run fn() at absolute simulated time t (used by checks and demos)."""
        self._push(t, "call", fn)

    def set_timer(self, node, delay, tag):
        self._push(self.time + delay, "timer", node.name, node.epoch, tag)

    def inject(self, delay, dst, msg, src="client"):
        """Deliver msg to dst after `delay`, bypassing drops (a reliable client request)."""
        self._push(self.time + delay, "msg", dst, src, copy.deepcopy(msg))

    def send(self, src, dst, msg):
        msg = copy.deepcopy(msg)
        self.trace.append(("send", self.time, src, dst, msg))
        if self.rng.random() < self.drop:
            self.trace.append(("lost", self.time, src, dst, msg))
            return
        copies = 2 if self.rng.random() < self.dup else 1
        for _ in range(copies):
            self._push(self.time + self.rng.uniform(*self.delay), "msg", dst, src, copy.deepcopy(msg))

    # ---- crash injection -----------------------------------------------------------------
    def crash_at_point(self, node, point, nth=1, restart_after=40.0):
        """Crash `node` the nth time it reaches `point`; restart it restart_after later."""
        self._specs.append({"node": node, "point": point, "nth": nth, "after": restart_after, "done": False})

    def crash_at_time(self, t, node, restart_after=40.0):
        self.at(t, lambda: self._crash(self.nodes[node], restart_after, "timed"))

    def chaos(self, prob, until, restart=(5.0, 80.0), max_crashes=12):
        """Until time `until`, crash a node with probability `prob` at every crash point."""
        self._chaos = {"prob": prob, "until": until, "restart": restart, "max": max_crashes}

    def hit(self, node, point):
        if node.immortal:
            return
        k = (node.name, point)
        self.hits[k] = self.hits.get(k, 0) + 1
        for s in self._specs:
            if not s["done"] and s["node"] == node.name and s["point"] == point and s["nth"] == self.hits[k]:
                s["done"] = True
                raise Crash(s["after"], point)
        c = self._chaos
        if c and self.time < c["until"] and self.crashes < c["max"] and self.rng.random() < c["prob"]:
            raise Crash(self.rng.uniform(*c["restart"]), point)

    def _crash(self, node, restart_after, why):
        if node.immortal or not node.up:
            return
        node.up = False
        node.epoch += 1
        for k in [k for k in vars(node) if k not in Node.KEEP]:
            delattr(node, k)                       # volatile state is gone
        self.crashes += 1
        self.trace.append(("crash", self.time, node.name, why))
        self._push(self.time + restart_after, "restart", node.name)

    def _run(self, node, fn, *args):
        try:
            fn(*args)
        except Crash as c:
            self._crash(node, c.restart_after, c.why)

    # ---- main loop -----------------------------------------------------------------------
    def run(self, until=3000.0):
        if not self._started:
            self._started = True
            for n in list(self.nodes.values()):
                self._run(n, n.on_start)
        while self._q and self._q[0][0] <= until:
            t, _, kind, a = heapq.heappop(self._q)
            self.time = t
            if kind == "call":
                a[0]()
            elif kind == "msg":
                dst, src, msg = a
                node = self.nodes[dst]
                if not node.up:
                    self.trace.append(("down", t, dst, src, msg))
                else:
                    self.trace.append(("recv", t, dst, src, msg))
                    self._run(node, node.on_message, src, msg)
            elif kind == "timer":
                name, epoch, tag = a
                node = self.nodes[name]
                if node.up and node.epoch == epoch:
                    self._run(node, node.on_timer, tag)
            elif kind == "restart":
                node = self.nodes[a[0]]
                node.up = True
                self.trace.append(("restart", t, node.name))
                node.init_volatile()
                self._run(node, node.on_start)


def make_cluster(sim, n_parts=3, replicated=False):
    """Build coordinator "C", participants "P1".."Pn" and (replicated) the decision store "S"."""
    parts = [f"P{i + 1}" for i in range(n_parts)]
    cfg = {"coord": "C", "parts": parts, "store": "S" if replicated else None}
    cc, pc = (ReplicatedCoordinator, ReplicatedParticipant) if replicated else (Coordinator, Participant)
    coord = cc(sim, "C", cfg)
    ps = [pc(sim, p, cfg) for p in parts]
    store = DecisionStore(sim, "S", cfg) if replicated else None
    return coord, ps, store


def begin(sim, tx, writes, at=0.0):
    """A client asks the coordinator to run transaction tx.  writes = {participant: {key: value}}."""
    sim.at(at, lambda: sim.inject(0.5, "C", {"type": "BEGIN", "tx": tx, "writes": writes}))


# =============================================================================================
# YOURS: the protocol
#
# Messages are dicts with a "type" and a "tx":
#   BEGIN   client -> coordinator        {"writes": {participant: {key: value}}}
#   PREPARE coordinator -> participant   {"writes": {key: value}}      (this participant's part only)
#   VOTE    participant -> coordinator   {"vote": "YES" | "NO"}
#   COMMIT / ABORT   coordinator -> participant        (the decision)
#   ACK     participant -> coordinator   (decision received AND logged)
#   INQUIRE participant -> coordinator   ("I am in doubt: what was decided?")
#
# Log records (tuples):
#   participant:  ("PREPARED", tx, writes)   ("COMMIT", tx)   ("ABORT", tx)
#   coordinator:  ("COMMIT", tx, [participants])   ("END", tx)        (abort is presumed: no record)
#
# Crash points: call self.point("name") exactly where the page says.  The simulator may raise
# Crash there; your code does not catch it.
# =============================================================================================


class Participant(Node):
    """A resource manager: it holds data and locks, and keeps a write-ahead log."""

    def init_volatile(self):
        self.data = {}                 # key -> value.  Rebuilt from the log: only COMMITs apply.
        self.locks = LockTable()       # Rebuilt from the log: PREPARED and undecided holds locks.
        self.waiting = {}              # tx -> time I started being in doubt about it

    def on_message(self, src, msg):
        if msg["type"] == "PREPARE":
            self.on_prepare(src, msg)
        elif msg["type"] in ("COMMIT", "ABORT"):
            self.on_decision(src, msg)

    # ---- milestone 1 -----------------------------------------------------------------------
    def on_prepare(self, src, msg):
        """PREPARE {tx, writes}.  Vote NO (and take no locks) if any key is locked by another
        transaction or any written value is the string "BAD".  Otherwise take the locks, force
        ("PREPARED", tx, writes) to the log, and ONLY THEN send VOTE YES.

        Hints: a duplicate PREPARE (already prepared) just repeats the YES; one for a
        transaction you already aborted gets NO.  Crash points, in order:
        p:before_prepare_log, p:after_prepare_log, p:after_vote_sent.
        (Milestone 3 adds one more line at the end: self.start_inquiry(tx), because a prepared
        participant that hears nothing must go and ask.  Leave it out for now.)"""
        raise NotImplementedError("TODO milestone 1: Participant.on_prepare")

    def on_decision(self, src, msg):
        """COMMIT or ABORT {tx}.  If prepared and undecided: log the decision FIRST, then apply
        the writes (commit only), release the locks.  Always answer ACK, even for a duplicate.

        Crash points: p:before_decision_log, p:after_decision_log (right after the append).
        If you never prepared this transaction, an ABORT is simply acknowledged (log it, so a
        late PREPARE for it votes NO); a COMMIT for it would be a bug."""
        raise NotImplementedError("TODO milestone 1: Participant.on_decision")

    # ---- milestone 3 -----------------------------------------------------------------------
    def start_inquiry(self, tx):
        """Remember when I became in doubt about tx and arm a timer ("inquire", tx)."""
        raise NotImplementedError("TODO milestone 3: Participant.start_inquiry")

    def ask(self, tx):
        """Send INQUIRE {tx} to the coordinator (self.cfg["coord"])."""
        raise NotImplementedError("TODO milestone 3: Participant.ask")

    def on_timer(self, tag):
        """tag == ("inquire", tx): if tx is still undecided, ask again and re-arm the timer."""
        raise NotImplementedError("TODO milestone 3: Participant.on_timer")

    def on_start(self):
        """Recovery.  Replay self.log: rebuild self.data from the COMMITs, and for every
        transaction that is PREPARED with no decision re-take its locks (it must succeed),
        start the inquiry and ask at once.  Volatile state was wiped: the log is all you have."""
        if len(self.log) == 0:
            return                     # first boot: nothing to recover yet
        raise NotImplementedError("TODO milestone 3: Participant.on_start")


class Coordinator(Node):
    """The transaction manager.  Presumed abort: it logs only COMMIT (and END)."""

    def init_volatile(self):
        self.pending = {}              # tx -> {"writes", "votes", "phase"}   (phase 1: collecting votes)
        self.committing = {}           # tx -> set of participants that have not acked COMMIT yet

    def on_message(self, src, msg):
        kind, tx = msg["type"], msg["tx"]
        if kind == "BEGIN":
            self.on_begin(msg)
        elif kind == "VOTE":
            self.on_vote(src, msg)
        elif kind == "ACK":
            self.on_ack(src, tx)
        elif kind == "INQUIRE":
            self.on_inquire(src, tx)

    # ---- milestone 2 -----------------------------------------------------------------------
    def on_begin(self, msg):
        """BEGIN {tx, writes}.  Remember the transaction in self.pending, send every participant
        a PREPARE carrying ITS part of the writes, call self.point("c:after_prepare_sent"), and
        arm a timer ("votes", tx) for VOTE_TIMEOUT.  Ignore a BEGIN you already know."""
        raise NotImplementedError("TODO milestone 2: Coordinator.on_begin")

    def on_vote(self, src, msg):
        """VOTE {tx, vote}.  Late or duplicate votes (no pending phase-1 entry) are ignored.
        One NO: self.abort(tx).  All YES: self.point("c:after_votes"), then self.make_decision(tx)."""
        raise NotImplementedError("TODO milestone 2: Coordinator.on_vote")

    def make_decision(self, tx):
        """All voted YES.  Log ("COMMIT", tx, sorted participants) -- THIS is the commit point --
        then self.point("c:after_decision_log"), move tx from pending to committing, send COMMIT
        to everyone (self.send_decisions) and arm a ("resend", tx) timer for RESEND_EVERY.
        (Milestone 5 overrides make_decision, so keep the logging in a separate method if you like.)"""
        raise NotImplementedError("TODO milestone 2: Coordinator.make_decision")

    def send_decisions(self, tx, kind, only=None):
        """Send `kind` (COMMIT or ABORT) to the participants in self.committing[tx] (COMMIT) or in
        `only` (ABORT).  Call self.point("c:mid_send") after EACH send."""
        raise NotImplementedError("TODO milestone 2: Coordinator.send_decisions")

    def abort(self, tx):
        """Presumed abort: forget tx, tell everyone ABORT, write nothing, expect no acks."""
        raise NotImplementedError("TODO milestone 2: Coordinator.abort")

    def on_ack(self, src, tx):
        """ACK.  When the last participant in self.committing[tx] has acked: self.point("c:before_end"),
        then log ("END", tx) and forget tx.  Ignore acks for transactions you are not committing."""
        raise NotImplementedError("TODO milestone 2: Coordinator.on_ack")

    def on_timer(self, tag):
        """("votes", tx): still in phase 1?  Silence counts as NO: abort.
        ("resend", tx): still committing?  Resend COMMIT to those who have not acked; re-arm."""
        raise NotImplementedError("TODO milestone 2: Coordinator.on_timer")

    # ---- milestone 3 -----------------------------------------------------------------------
    def on_inquire(self, src, tx):
        """INQUIRE {tx}.  Still collecting votes: say nothing (they will ask again).  A COMMIT
        record in the log: answer COMMIT.  Otherwise answer ABORT (presumed abort)."""
        raise NotImplementedError("TODO milestone 3: Coordinator.on_inquire")

    def on_start(self):
        """Recovery.  For every ("COMMIT", ...) in the log with no ("END", ...): rebuild
        self.committing, resend COMMIT, arm the resend timer.  Transactions that were still
        collecting votes are forgotten: that is presumed abort."""
        if len(self.log) == 0:
            return                     # first boot: nothing to recover yet
        raise NotImplementedError("TODO milestone 3: Coordinator.on_start")


# ---- milestone 5: take the decision off the coordinator's disk ---------------------------

class DecisionStore(Node):
    """A write-once decision register per transaction.  Stands in for a small consensus group
    (a replicated log of 3 or 5 nodes): the simulator never crashes it.  First write wins."""

    immortal = True

    def decide(self, tx, value):
        for rec in self.log:
            if rec[1] == tx:
                return rec[2]
        self.log.append(("DECIDED", tx, value))
        return value

    def on_message(self, src, msg):
        tx = msg["tx"]
        if msg["type"] == "DECIDE":                       # the coordinator proposes COMMIT
            self.send(src, {"type": "DECISION", "tx": tx, "value": self.decide(tx, msg["value"])})
        elif msg["type"] == "TERMINATE":                  # an in-doubt participant forces an answer
            value = self.decide(tx, "ABORT")              # no decision yet? then it is ABORT, for ever
            self.send(msg["reply_to"], {"type": value, "tx": tx})


class ReplicatedCoordinator(Coordinator):
    """Writes the decision to the store BEFORE its own log, so it outlives the coordinator."""

    def make_decision(self, tx):
        """Instead of logging at once: mark tx as deciding (phase 2, so the vote timeout no
        longer applies) and send DECIDE {tx, value: "COMMIT"} to self.cfg["store"], re-sending
        on a timer until the store answers.  The store replies DECISION {tx, value}."""
        raise NotImplementedError("TODO milestone 5: ReplicatedCoordinator.make_decision")

    def on_message(self, src, msg):
        """DECISION: if the store says COMMIT, self.point("c:after_store_decide"), then do the
        usual commit steps (log COMMIT, send decisions).  If it says ABORT, a participant beat
        you to it: abort.  Everything else goes to the parent class."""
        raise NotImplementedError("TODO milestone 5: ReplicatedCoordinator.on_message")

    def on_inquire(self, src, tx):
        """Same as before, with one change: 'no record' no longer proves ABORT, because you may
        have crashed after the store said COMMIT but before you logged it.  For a transaction
        that is neither pending nor in your log, send TERMINATE {tx, reply_to: src} to the store."""
        raise NotImplementedError("TODO milestone 5: ReplicatedCoordinator.on_inquire")


class ReplicatedParticipant(Participant):
    """After STORE_WAIT in doubt, stop waiting for the coordinator and ask the store."""

    def ask(self, tx):
        """Ask the coordinator as before.  If I have been in doubt for at least STORE_WAIT,
        also send TERMINATE {tx, reply_to: my name} to the store (the answer arrives as an
        ordinary COMMIT or ABORT message)."""
        raise NotImplementedError("TODO milestone 5: ReplicatedParticipant.ask")
