"""Lab 1: gossip and failure detection on a simulated cluster.

Everything runs inside ONE process. There are no sockets and no threads: a seeded
random number generator, a priority queue of in-flight messages and timers, and a
simulated clock measured in "ticks" (think milliseconds). The same seed always
gives the same run, so a failing seed can be replayed exactly.

What is GIVEN (read it, do not change it):
    Sim        the network and the clock: loss, duplicates, random delay, node
               crash, node pause (a long GC-style freeze), and a blocked link
    Node       the base class every protocol node extends

What YOU write (look for the TODOs; each names its milestone):
    1  GossipNode        push gossip of one rumour
    2  HeartbeatNode     a fixed-timeout heartbeat failure detector
    3  SwimNode          ping, ping-req through k helpers, the suspect state
    4  SwimNode          incarnation numbers and piggybacked dissemination
    5  Replica / MerkleTree / sync     (optional) anti-entropy with a Merkle tree

Run `python3 check.py` after each milestone. The lab page explains every step.
"""
import hashlib
import heapq
import math
import random
import zlib

# ---- time constants, in ticks -------------------------------------------------
ROUND = 10              # one gossip round
HB_PERIOD = 10          # heartbeat interval (milestone 2)
PERIOD = 100            # one SWIM protocol period (milestones 3 and 4)
PING_TIMEOUT = 30       # how long a direct ping may take before we ask helpers
PROBE_END = PERIOD - 10 # the verdict on this period's probe is due here
SUSPECT_MULT = 3        # suspicion timeout = SUSPECT_MULT * PERIOD * ceil(log2 n)
MAX_PIGGY = 4           # membership updates carried by one message
BUCKETS = 256           # leaves of the Merkle tree (milestone 5); a power of two


# =============================================================================
# GIVEN: the simulated world
# =============================================================================
class Sim:
    """A deterministic cluster of n nodes joined by an unreliable network.

    Messages are dicts with a "t" (type) key. Between send and delivery a message
    may be dropped (`loss`), duplicated (`dup`), and always gets a random delay in
    `delay` ticks, so messages sent in order can arrive out of order.

    Failures you can schedule with sim.at(time, fn):
        sim.crash(i)           node i stops for good (events for it are discarded)
        sim.pause(i, ticks)    node i freezes for `ticks`; everything addressed to
                               it waits and is delivered when it wakes
        sim.block(a, b)        the link a<->b drops everything, other links fine
    """

    def __init__(self, seed, n, make_node, loss=0.0, dup=0.0, delay=(1, 5)):
        self.seed = seed
        self.n = n
        self.rng = random.Random(seed)
        self.now = 0
        self.loss, self.dup, self.delay = loss, dup, delay
        self.q = []                          # heap of (time, counter, event)
        self.counter = 0
        self.alive = [True] * n
        self.paused_until = [0] * n
        self.blocked = set()
        self.log = []                        # (time, kind, observer, subject)
        self.sent = {}                       # message type -> how many were sent
        self.sent_by = [0] * n
        self.nodes = [make_node(self, i, [j for j in range(n) if j != i]) for i in range(n)]
        for node in self.nodes:
            node.start()

    # -- plumbing ----------------------------------------------------------
    def _push(self, time, event):
        self.counter += 1
        heapq.heappush(self.q, (time, self.counter, event))

    def send(self, src, dst, msg):
        assert src != dst, "a node sent a message to itself"
        self.sent[msg["t"]] = self.sent.get(msg["t"], 0) + 1
        self.sent_by[src] += 1
        if (min(src, dst), max(src, dst)) in self.blocked or self.rng.random() < self.loss:
            return
        copies = 2 if self.rng.random() < self.dup else 1
        for _ in range(copies):
            self._push(self.now + self.rng.randint(*self.delay), ("msg", dst, src, msg))

    def set_timer(self, node, delay, tag):
        self._push(self.now + delay, ("timer", node, tag))

    def at(self, time, fn):
        self._push(time, ("call", fn))

    # -- failures ----------------------------------------------------------
    def crash(self, i):
        self.alive[i] = False

    def pause(self, i, ticks):
        self.paused_until[i] = self.now + ticks

    def block(self, a, b):
        self.blocked.add((min(a, b), max(a, b)))

    # -- running -----------------------------------------------------------
    def run(self, until):
        while self.q and self.q[0][0] <= until:
            time, _, ev = heapq.heappop(self.q)
            self.now = time
            if ev[0] == "call":
                ev[1]()
                continue
            node = ev[1]
            if not self.alive[node]:
                continue
            if time < self.paused_until[node]:          # frozen: try again on waking
                self._push(self.paused_until[node], ev)
                continue
            if ev[0] == "msg":
                self.nodes[node].on_message(ev[2], ev[3])
            else:
                self.nodes[node].on_timer(ev[2])
        self.now = until

    def events(self, kind, subject=None):
        return [e for e in self.log if e[1] == kind and (subject is None or e[3] == subject)]


class Node:
    """Base class. Subclasses override start / on_message / on_timer."""

    def __init__(self, sim, id, peers):
        self.sim, self.id, self.peers = sim, id, peers
        self.rng = random.Random(sim.seed * 1000003 + id)    # this node's private dice

    def send(self, dst, msg):
        self.sim.send(self.id, dst, msg)

    def set_timer(self, delay, tag):
        self.sim.set_timer(self.id, delay, tag)

    def report(self, kind, subject):
        """Tell the checker something happened: ("suspect", 3) means 'I now suspect node 3'."""
        self.sim.log.append((self.sim.now, kind, self.id, subject))

    def start(self):
        pass

    def on_message(self, src, msg):
        pass

    def on_timer(self, tag):
        pass


# =============================================================================
# MILESTONE 1: push gossip
# =============================================================================
class GossipNode(Node):
    """One node of a push-gossip cluster.

    Every ROUND ticks, a node that knows the rumour pushes it to `fanout` peers
    chosen at random. A node that learns the rumour starts pushing in the NEXT
    round. Remember the moment you were informed in `informed_at`: the checker
    reads it to count rounds.
    """

    def __init__(self, sim, id, peers, fanout=1, origin=False):
        super().__init__(sim, id, peers)
        self.fanout = fanout
        self.informed = origin
        self.informed_at = 0 if origin else None

    def start(self):
        """Arm the first round timer: self.set_timer(ROUND, "round")."""
        raise NotImplementedError("TODO milestone 1: GossipNode.start")

    def on_timer(self, tag):
        """Each round: re-arm the timer; if informed, send {"t": "rumour"} to
        `fanout` DIFFERENT random peers (self.rng.sample(self.peers, k))."""
        raise NotImplementedError("TODO milestone 1: GossipNode.on_timer")

    def on_message(self, src, msg):
        """First time you hear the rumour: mark yourself informed and record the time."""
        raise NotImplementedError("TODO milestone 1: GossipNode.on_message")


# =============================================================================
# MILESTONE 2: a heartbeat detector with a fixed timeout
# =============================================================================
class HeartbeatNode(Node):
    """All-to-all heartbeats. Every HB_PERIOD ticks send {"t": "hb"} to every peer,
    then look at how long each peer has been silent.

    A peer is suspected when it has been silent for MORE than `timeout` ticks.
    Call self.report("suspect", peer) when you start suspecting it, and
    self.report("unsuspect", peer) when a heartbeat from a suspected peer arrives.
    """

    def __init__(self, sim, id, peers, timeout=40):
        super().__init__(sim, id, peers)
        self.timeout = timeout
        self.last_heard = {p: 0 for p in peers}
        self.suspects = set()

    def start(self):
        raise NotImplementedError("TODO milestone 2: HeartbeatNode.start")

    def on_timer(self, tag):
        """Re-arm the timer, send a heartbeat to every peer, then suspect (once)
        each peer with sim.now - last_heard[peer] > timeout."""
        raise NotImplementedError("TODO milestone 2: HeartbeatNode.on_timer")

    def on_message(self, src, msg):
        """Record when you last heard from src; if you were suspecting it, stop."""
        raise NotImplementedError("TODO milestone 2: HeartbeatNode.on_message")


# =============================================================================
# MILESTONES 3 AND 4: SWIM
# =============================================================================
class SwimNode(Node):
    """A SWIM member (Das, Gupta & Motivala, 2002).

    self.members maps every member id (including your own) to [state, incarnation]
    where state is "alive", "suspect" or "dead". The group is static: nobody joins.

    Messages (dicts):
        {"t": "ping",     "seq": s}                       "are you there?"
        {"t": "ack",      "seq": s, "subject": id}        "yes, `subject` is alive"
        {"t": "ping-req", "seq": s, "target": id}         "please ping `target` for me"
    With dissem=True (milestone 4) every message also carries "u": a list of
    (subject, state, incarnation) membership updates piggybacked by self.out().

    Timers you receive (on_timer dispatches them for you):
        "period"                  start of a protocol period
        ("ping_to", seq)          the direct ping of probe `seq` has had PING_TIMEOUT
        ("probe_end", seq)        the verdict on probe `seq` is due
        ("suspect", id, inc)      member `id` has been suspect at `inc` for long enough
    """

    def __init__(self, sim, id, peers, k=3, dissem=False):
        super().__init__(sim, id, peers)
        self.k = k                            # how many helpers for an indirect probe
        self.dissem = dissem                  # milestone 4 switch
        self.members = {m: ["alive", 0] for m in [id] + peers}
        self.seq = 0                          # one counter for probes AND relays
        self.probe = None                     # {"target", "seq", "acked"} of this period
        self.relays = {}                      # seq -> (origin, origin_seq, target), when we are a helper
        self.order = []                       # round-robin probe order (given)
        self.buf = {}                         # subject -> [state, inc, times_sent]   (milestone 4)
        group = len(peers) + 1
        self.suspect_timeout = SUSPECT_MULT * PERIOD * max(1, math.ceil(math.log2(group)))
        self.retransmit = 3 * math.ceil(math.log2(group + 1))    # sends per update

    # ---- given helpers ----------------------------------------------------
    def start(self):
        self.set_timer(self.rng.randint(1, PERIOD), "period")    # members are not in lockstep

    def on_timer(self, tag):
        if tag == "period":
            self.set_timer(PERIOD, "period")
            self.on_period()
        elif tag[0] == "ping_to":
            self.on_ping_timeout(tag[1])
        elif tag[0] == "probe_end":
            self.on_probe_end(tag[1])
        elif tag[0] == "suspect":
            self.on_suspect_timeout(tag[1], tag[2])

    def on_message(self, src, msg):
        if self.dissem:
            self.absorb(msg.get("u", []))
        kind = msg["t"]
        if kind == "ping":
            self.on_ping(src, msg)
        elif kind == "ack":
            self.on_ack(src, msg)
        elif kind == "ping-req":
            self.on_ping_req(src, msg)

    def out(self, dst, msg):
        """Send a message, piggybacking membership updates when dissem is on."""
        if self.dissem:
            msg["u"] = self.piggyback()
        self.send(dst, msg)

    def next_target(self):
        """Round-robin over a shuffled list, skipping the dead: every member is probed
        at least once every n-1 periods (the bounded-detection trick from the SWIM paper)."""
        if not self.order:
            self.order = [p for p in self.peers if self.members[p][0] != "dead"]
            self.rng.shuffle(self.order)
        while self.order:
            target = self.order.pop()
            if self.members[target][0] != "dead":
                return target
        return None

    def _commit(self, subject, state, inc):
        """Write one member's new state and do what follows from it: log it for the
        checker, start the suspicion timer for a suspect, queue the news for gossip."""
        self.members[subject] = [state, inc]
        self.report(state, subject)
        if state == "suspect":
            self.set_timer(self.suspect_timeout, ("suspect", subject, inc))
        if self.dissem:
            self.queue_update(subject, state, inc)

    # ---- MILESTONE 3 ---------------------------------------------------------
    def on_period(self):
        """Once per period. Pick self.next_target(); if None, do nothing. Otherwise:
        bump self.seq, set self.probe = {"target": t, "seq": seq, "acked": False},
        self.out(t, {"t": "ping", "seq": seq}), and arm two timers:
            self.set_timer(PING_TIMEOUT, ("ping_to", seq))
            self.set_timer(PROBE_END, ("probe_end", seq))"""
        raise NotImplementedError("TODO milestone 3: SwimNode.on_period")

    def on_ping(self, src, msg):
        """Answer with {"t": "ack", "seq": msg["seq"], "subject": self.id}."""
        raise NotImplementedError("TODO milestone 3: SwimNode.on_ping")

    def on_ping_req(self, src, msg):
        """You are a helper. `src` asks you to probe msg["target"]. Bump self.seq,
        remember self.relays[seq] = (src, msg["seq"], msg["target"]), and ping the
        target with that NEW seq (so its ack comes back to you, not to src)."""
        raise NotImplementedError("TODO milestone 3: SwimNode.on_ping_req")

    def on_ack(self, src, msg):
        """Three jobs, in this order:
        a) (milestone 3 only, when not self.dissem) an ack proves msg["subject"] is
           alive: if you hold it as "suspect", self._commit(subject, "alive", its inc).
           With dissem on, only the member itself can clear a suspicion (milestone 4).
        b) if msg["seq"] is in self.relays you are the helper: pop it and forward
           {"t": "ack", "seq": origin_seq, "subject": target} to the origin;
        c) otherwise, if it answers your current probe (same seq), mark it acked."""
        raise NotImplementedError("TODO milestone 3: SwimNode.on_ack")

    def on_ping_timeout(self, seq):
        """No direct ack yet. If this is still the current probe, unacked, and k > 0:
        choose min(k, available) helpers at random among members other than yourself,
        the target and the dead, and send each {"t": "ping-req", "seq": seq, "target": t}."""
        raise NotImplementedError("TODO milestone 3: SwimNode.on_ping_timeout")

    def on_probe_end(self, seq):
        """The period's verdict. Still unacked (direct AND indirect)? If the target is
        "alive", self._commit(target, "suspect", its current incarnation)."""
        raise NotImplementedError("TODO milestone 3: SwimNode.on_probe_end")

    def on_suspect_timeout(self, subject, inc):
        """The suspicion has run its course. If subject is STILL "suspect" at exactly
        this incarnation, nobody refuted it: self._commit(subject, "dead", inc)."""
        raise NotImplementedError("TODO milestone 3: SwimNode.on_suspect_timeout")

    # ---- MILESTONE 4 -------------------------------------------------------------
    def apply_update(self, subject, state, inc):
        """Decide whether the news (subject, state, inc) beats what we know, and if so
        self._commit it. Return True if it was accepted.

        About OTHER members (cur_state, cur_inc is what you hold):
            dead is final: ignore everything about a member you hold as dead
            "dead" news beats anything
            alive(i)   beats the current entry only if i > cur_inc
            suspect(i) beats alive(j) if i >= j, and beats suspect(j) only if i > j
        About YOURSELF (subject == self.id):
            suspect(i) with i >= your incarnation: REFUTE it. Commit alive at i + 1
            (only you may raise your own incarnation). Everything else: ignore."""
        raise NotImplementedError("TODO milestone 4: SwimNode.apply_update")

    def queue_update(self, subject, state, inc):
        """Remember news worth telling others: self.buf[subject] = [state, inc, 0]
        (the 0 counts how many times it has been sent; newer news replaces older)."""
        raise NotImplementedError("TODO milestone 4: SwimNode.queue_update")

    def piggyback(self):
        """Pick up to MAX_PIGGY buffered updates, those sent the FEWEST times first.
        Return them as (subject, state, inc) tuples, add 1 to each one's send count,
        and drop an update from the buffer once it has been sent self.retransmit times."""
        raise NotImplementedError("TODO milestone 4: SwimNode.piggyback")

    def absorb(self, updates):
        """Feed every piggybacked (subject, state, inc) through apply_update."""
        raise NotImplementedError("TODO milestone 4: SwimNode.absorb")


# =============================================================================
# MILESTONE 5 (optional): anti-entropy with a Merkle tree
# =============================================================================
def bucket_of(key, buckets=BUCKETS):
    """Which leaf a key belongs to (a hash range; crc32 is stable across runs)."""
    return zlib.crc32(key.encode()) % buckets


class Replica:
    """A key-value replica. data maps key -> (value, version); the higher version wins."""

    def __init__(self, data=None):
        self.data = dict(data or {})

    def put(self, key, value, version):
        self.data[key] = (value, version)


def _h(text):
    return hashlib.sha1(text.encode()).hexdigest()


class MerkleTree:
    """A hash tree over BUCKETS key ranges.

    self.items[b]   sorted list of (key, value, version) in bucket b
    self.levels[0]  one hash per bucket (the leaves); levels[-1] == [root]
    A parent's hash is the hash of its two children's hashes joined together.
    """

    def __init__(self, data, buckets=BUCKETS):
        self.buckets = buckets
        raise NotImplementedError("TODO milestone 5: MerkleTree.__init__")

    def root(self):
        return self.levels[-1][0]


def diff_buckets(a, b):
    """Walk two trees from the root, descending only into subtrees whose hashes differ.
    Return (sorted list of differing bucket numbers, number of hash comparisons made).
    Count one comparison every time you compare a pair of node hashes."""
    raise NotImplementedError("TODO milestone 5: diff_buckets")


def sync(ra, rb):
    """Make two replicas identical, touching only the buckets that differ.
    Build both trees, find the differing buckets with diff_buckets, and for each one
    exchange that bucket's items in BOTH directions, keeping the entry with the higher
    version (on a tie keep the larger repr of the value, so both sides agree).
    Return {"comparisons": c, "buckets": number of differing buckets, "keys_sent": s}
    where s counts every (key, value, version) item either side sent, in all."""
    raise NotImplementedError("TODO milestone 5: sync")
