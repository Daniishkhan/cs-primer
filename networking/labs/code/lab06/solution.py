"""Lab 6 solution: Toy Raft, in a deterministic simulation.

Reference: Diego Ongaro and John Ousterhout, "In Search of an Understandable
Consensus Algorithm" (the Raft paper), https://raft.github.io/raft.pdf
Section and figure numbers below refer to that paper. Figure 2 is the
one-page summary of the algorithm; keep it open while you work.

There are NO sockets here. A Network object carries messages between node
objects, with seeded random delays and drops, and time is a counter of
"ticks". Same seed, same run, every time.

    python3 solution.py demo [seed]     # a narrated run: election, commands, partition, heal

The simulator (Network, KVStateMachine, Cluster) is complete. You write the
RaftNode methods marked TODO.
"""
import heapq
import random
import sys

# ---------------------------------------------------------------------------
# Constants and message shapes
# ---------------------------------------------------------------------------

FOLLOWER, CANDIDATE, LEADER = "follower", "candidate", "leader"

ELECTION_TIMEOUT = (20, 40)   # a follower waits a random number of ticks in this range (inclusive)
HEARTBEAT_INTERVAL = 5        # a leader sends AppendEntries at least this often (must be << election timeout)
NET_DELAY = (1, 3)            # messages take this many ticks to arrive (never 0)

# Messages are plain dicts. Commands must be immutable (tuples) because
# messages are shallow-copied. The four kinds (Raft paper, Figure 2):
#
#   {"type": "RequestVote", "term", "candidate_id", "last_log_index", "last_log_term"}
#   {"type": "RequestVoteReply", "term", "vote_granted"}
#   {"type": "AppendEntries", "term", "leader_id", "prev_log_index", "prev_log_term",
#    "entries": [(term, command), ...], "leader_commit"}
#   {"type": "AppendEntriesReply", "term", "success", "match_index"}
#
# "match_index" in the reply is not in the paper's Figure 2; it is a convenience:
# on success it says how much of the leader's log the follower now has, so the
# leader needs no memory of which request this answers.
REQUEST_VOTE, VOTE_REPLY = "RequestVote", "RequestVoteReply"
APPEND_ENTRIES, APPEND_REPLY = "AppendEntries", "AppendEntriesReply"


# ---------------------------------------------------------------------------
# The simulator (complete: you do not change this part)
# ---------------------------------------------------------------------------

class Network:
    """Delivers messages between nodes after a random delay, or loses them.

    All randomness comes from one seeded generator, so a run is reproducible.
    A partition splits nodes into groups that cannot talk to each other; a
    message is checked when it is sent AND when it would arrive, so a
    partition also swallows messages that were already in flight.
    """

    def __init__(self, node_ids, rng, drop=0.0, delay=NET_DELAY):
        self.node_ids = list(node_ids)
        self.rng, self.drop, self.delay = rng, drop, delay
        self.group = {i: 0 for i in self.node_ids}      # node -> partition group
        self.queue = []                                 # heap of (arrive_tick, seq, src, dst, msg)
        self.seq = 0
        self.sent = self.dropped = 0

    def connected(self, a, b):
        return self.group[a] == self.group[b]

    def partition(self, *groups):
        """net.partition({0, 1}, {2, 3, 4}). Nodes not listed are cut off alone."""
        self.group = {i: -1 - i for i in self.node_ids}
        for g, members in enumerate(groups):
            for i in members:
                self.group[i] = g

    def isolate(self, node):
        self.partition({node}, set(self.node_ids) - {node})

    def heal(self):
        self.group = {i: 0 for i in self.node_ids}

    def send(self, now, src, dst, msg):
        self.sent += 1
        lost = self.rng.random() < self.drop            # always draw, so runs stay comparable
        delay = self.rng.randint(*self.delay)
        if lost or not self.connected(src, dst):
            self.dropped += 1
            return
        copy = dict(msg)
        if "entries" in copy:
            copy["entries"] = list(copy["entries"])
        self.seq += 1
        heapq.heappush(self.queue, (now + delay, self.seq, src, dst, copy))

    def deliver(self, now, handler):
        """Hand every message due at or before `now` to handler(src, dst, msg)."""
        while self.queue and self.queue[0][0] <= now:
            _, _, src, dst, msg = heapq.heappop(self.queue)
            if self.connected(src, dst):
                handler(src, dst, msg)
            else:
                self.dropped += 1


class KVStateMachine:
    """The replicated service: a dict. Commands are ("set", key, value) or
    ("del", key); None is a no-op. apply() reports every application to the
    cluster, which is how check.py notices if two nodes ever disagree."""

    def __init__(self, node_id, record):
        self.node_id, self.record = node_id, record
        self.data = {}

    def apply(self, index, command):
        self.record(self.node_id, index, command)
        if command is None:
            return
        if command[0] == "set":
            self.data[command[1]] = command[2]
        elif command[0] == "del":
            self.data.pop(command[1], None)

    def reset(self):
        self.data = {}


class Cluster:
    """N nodes, a network, and a logical clock."""

    def __init__(self, n=5, seed=0, node_cls=None, drop=0.0):
        node_cls = node_cls or RaftNode
        self.n, self.seed, self.now = n, seed, 0
        self.net = Network(range(n), random.Random(seed), drop)
        self.applied = {}            # index -> the command first applied at that index, anywhere
        self.violations = []         # State Machine Safety breaches seen at apply time
        self.observers = []          # callables(cluster), run after every tick
        self.up = set(range(n))
        self.nodes = []
        for i in range(n):
            peers = [j for j in range(n) if j != i]
            send = (lambda dst, msg, i=i: self.net.send(self.now, i, dst, msg))
            sm = KVStateMachine(i, self._record)
            self.nodes.append(node_cls(i, peers, send, random.Random(seed * 1000 + i), sm))

    def _record(self, node_id, index, command):
        first = self.applied.setdefault(index, command)
        if first != command:
            self.violations.append(
                f"index {index}: node {node_id} applied {command!r} but another node applied {first!r}")

    def _deliver(self, src, dst, msg):
        if dst in self.up:
            self.nodes[dst].on_message(src, msg)

    def step(self):
        """One tick: deliver due messages, then let every live node's clock advance."""
        self.now += 1
        self.net.deliver(self.now, self._deliver)
        for i in sorted(self.up):
            self.nodes[i].tick()
        for observe in self.observers:
            observe(self)

    def run(self, ticks):
        for _ in range(ticks):
            self.step()

    def run_until(self, predicate, max_ticks):
        """Step until predicate(cluster) is true. Returns ticks used, or None on timeout."""
        for used in range(max_ticks + 1):
            if predicate(self):
                return used
            if used < max_ticks:
                self.step()
        return None

    def crash(self, i):
        self.up.discard(i)

    def restart(self, i):
        """Bring a crashed node back: log, term and vote survive; the rest is rebuilt."""
        self.nodes[i].restart()
        self.up.add(i)

    def leaders(self):
        return [self.nodes[i] for i in sorted(self.up) if self.nodes[i].state == LEADER]

    def leader(self):
        """The live leader with the highest term, or None."""
        ls = self.leaders()
        return max(ls, key=lambda n: n.current_term) if ls else None

    def submit(self, command):
        """Offer a command to the current leader. Returns (leader_id, log_index) or None."""
        leader = self.leader()
        if leader is None:
            return None
        index = leader.client_request(command)
        return None if index is None else (leader.id, index)

    def describe(self):
        lines = [f"tick {self.now}"]
        for i, n in enumerate(self.nodes):
            status = n.state if i in self.up else "DOWN"
            log = " ".join(str(t) for t, _ in n.log) or "-"
            lines.append(f"  S{i} {status:<9} term {n.current_term:<3} log[terms]: {log:<24} "
                         f"commit {n.commit_index}  kv {n.sm.data}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# The Raft node (this is the part you write)
# ---------------------------------------------------------------------------

class RaftNode:
    """One Raft server. Log indexes start at 1, as in the paper; the entry at
    index i is self.log[i - 1] and is a pair (term, command). Index 0 means
    "before the first entry"."""

    def __init__(self, node_id, peers, send, rng, sm):
        self.id, self.peers, self.send, self.rng, self.sm = node_id, list(peers), send, rng, sm
        # Persistent state (survives a crash):
        self.current_term = 0
        self.voted_for = None
        self.log = []
        # Volatile state (rebuilt after a crash):
        self.state = FOLLOWER
        self.commit_index = 0
        self.last_applied = 0
        self.leader_id = None
        self.votes = set()                 # candidates: who voted for me this term
        self.next_index = {}               # leaders: next entry to send each peer
        self.match_index = {}              # leaders: highest entry known stored on each peer
        self.election_elapsed = 0
        self.election_timeout = 0
        self.heartbeat_elapsed = 0
        self.reset_election_timer()

    # -- provided helpers --------------------------------------------------
    def majority(self):
        return (len(self.peers) + 1) // 2 + 1

    def last_log_index(self):
        return len(self.log)

    def last_log_term(self):
        return self.log[-1][0] if self.log else 0

    def term_at(self, index):
        """Term of the entry at `index`; 0 for index 0 (the empty prefix)."""
        return self.log[index - 1][0] if index > 0 else 0

    def restart(self):
        """After a crash: term, vote and log are on 'disk'; everything else is lost."""
        self.state = FOLLOWER
        self.commit_index = self.last_applied = 0
        self.leader_id = None
        self.votes = set()
        self.next_index, self.match_index = {}, {}
        self.heartbeat_elapsed = 0
        self.sm.reset()
        self.reset_election_timer()

    def tick(self):
        """Called once per tick by the simulator."""
        if self.state == LEADER:
            self.heartbeat_elapsed += 1
            if self.heartbeat_elapsed >= HEARTBEAT_INTERVAL:
                self.broadcast_append_entries()
        else:
            self.election_elapsed += 1
            if self.election_elapsed >= self.election_timeout:
                self.start_election()

    # -- Milestone 1: terms, states, elections (paper section 5.2) -----------
    def reset_election_timer(self):
        """Restart the countdown with a fresh random timeout from ELECTION_TIMEOUT."""
        self.election_elapsed = 0
        self.election_timeout = self.rng.randint(*ELECTION_TIMEOUT)

    def become_follower(self, term):
        """Adopt `term` if it is newer (forgetting our vote), and become a follower."""
        if term > self.current_term:
            self.current_term = term
            self.voted_for = None
        self.state = FOLLOWER
        self.votes = set()

    def start_election(self):
        """Election timeout: new term, become candidate, vote for self, ask everyone."""
        self.current_term += 1
        self.state = CANDIDATE
        self.voted_for = self.id
        self.votes = {self.id}
        self.leader_id = None
        self.reset_election_timer()
        for peer in self.peers:
            self.send(peer, {"type": REQUEST_VOTE, "term": self.current_term,
                             "candidate_id": self.id,
                             "last_log_index": self.last_log_index(),
                             "last_log_term": self.last_log_term()})
        if len(self.votes) >= self.majority():          # a cluster of one
            self.become_leader()

    def become_leader(self):
        """We won. Set up per-follower bookkeeping and announce ourselves at once."""
        self.state = LEADER
        self.leader_id = self.id
        self.next_index = {p: self.last_log_index() + 1 for p in self.peers}
        self.match_index = {p: 0 for p in self.peers}
        self.broadcast_append_entries()

    def on_message(self, src, msg):
        """Every incoming message passes through here first."""
        if msg["term"] > self.current_term:             # rule for all servers (Figure 2)
            self.become_follower(msg["term"])
        kind = msg["type"]
        if kind == REQUEST_VOTE:
            self.on_request_vote(src, msg)
        elif kind == VOTE_REPLY:
            self.on_request_vote_reply(src, msg)
        elif kind == APPEND_ENTRIES:
            self.on_append_entries(src, msg)
        elif kind == APPEND_REPLY:
            self.on_append_entries_reply(src, msg)

    def on_request_vote(self, src, msg):
        grant = (msg["term"] == self.current_term
                 and self.voted_for in (None, msg["candidate_id"])
                 and self.candidate_log_ok(msg))
        if grant:
            self.voted_for = msg["candidate_id"]
            self.reset_election_timer()                 # we just backed a candidate: don't race it
        self.send(src, {"type": VOTE_REPLY, "term": self.current_term, "vote_granted": grant})

    def on_request_vote_reply(self, src, msg):
        if self.state != CANDIDATE or msg["term"] != self.current_term:
            return                                      # a late reply from an old election
        if msg["vote_granted"]:
            self.votes.add(src)
            if len(self.votes) >= self.majority():
                self.become_leader()

    # -- Milestone 2: heartbeats (section 5.2) -------------------------------
    def broadcast_append_entries(self):
        self.heartbeat_elapsed = 0
        for peer in self.peers:
            self.send_append_entries(peer)

    def send_append_entries(self, peer):
        """Send `peer` everything from next_index[peer] on (nothing, for a heartbeat)."""
        prev = self.next_index[peer] - 1
        self.send(peer, {"type": APPEND_ENTRIES, "term": self.current_term,
                         "leader_id": self.id,
                         "prev_log_index": prev, "prev_log_term": self.term_at(prev),
                         "entries": self.log[prev:],
                         "leader_commit": self.commit_index})

    def on_append_entries(self, src, msg):
        reply = {"type": APPEND_REPLY, "term": self.current_term, "success": False, "match_index": 0}
        if msg["term"] < self.current_term:             # from a deposed leader
            self.send(src, reply)
            return
        self.become_follower(msg["term"])               # a candidate of this term steps down
        self.leader_id = msg["leader_id"]
        self.reset_election_timer()                     # a live leader: stay quiet
        # Milestone 3: the consistency check, and conflict truncation (section 5.3)
        prev = msg["prev_log_index"]
        if prev > self.last_log_index() or self.term_at(prev) != msg["prev_log_term"]:
            self.send(src, reply)                       # we don't have the entry before the new ones
            return
        index = prev
        for entry in msg["entries"]:
            index += 1
            entry = tuple(entry)
            if index <= self.last_log_index():
                if self.log[index - 1][0] == entry[0]:
                    continue                            # already have it
                del self.log[index - 1:]                # conflict: drop it and everything after
            self.log.append(entry)
        match = prev + len(msg["entries"])
        # Milestone 4: learn what is committed, but never beyond what this message verified
        if msg["leader_commit"] > self.commit_index:
            self.commit_index = min(msg["leader_commit"], match)
            self.apply_committed()
        reply.update(success=True, match_index=match)
        self.send(src, reply)

    # -- Milestone 3: log replication (section 5.3) ----------------------------
    def client_request(self, command):
        """Leader only: append `command` to our log and start replicating it.
        Return its log index, or None if we are not the leader."""
        if self.state != LEADER:
            return None
        self.log.append((self.current_term, command))
        self.broadcast_append_entries()
        return self.last_log_index()

    def on_append_entries_reply(self, src, msg):
        if self.state != LEADER or msg["term"] != self.current_term:
            return
        if msg["success"]:
            self.match_index[src] = max(self.match_index[src], msg["match_index"])
            self.next_index[src] = self.match_index[src] + 1
            self.advance_commit_index()
        else:                                           # logs differ: back up one and try again
            self.next_index[src] = max(self.match_index[src] + 1, self.next_index[src] - 1)
            self.send_append_entries(src)

    # -- Milestone 4: the commit rule and the state machine (section 5.4.2) -----
    def advance_commit_index(self):
        """Leader: find the highest N stored on a majority AND from the current term."""
        for n in range(self.last_log_index(), self.commit_index, -1):
            if self.term_at(n) != self.current_term:
                break                                   # older-term entries commit only indirectly
            copies = 1 + sum(1 for p in self.peers if self.match_index[p] >= n)
            if copies >= self.majority():
                self.commit_index = n
                break
        self.apply_committed()

    def apply_committed(self):
        """Apply entries last_applied+1 .. commit_index to the state machine, in order."""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            self.sm.apply(self.last_applied, self.log[self.last_applied - 1][1])

    # -- Milestone 5: the voting restriction (section 5.4.1) -----------------------
    def candidate_log_ok(self, msg):
        """Is the candidate's log at least as up to date as ours?"""
        return ((msg["last_log_term"], msg["last_log_index"])
                >= (self.last_log_term(), self.last_log_index()))


# ---------------------------------------------------------------------------
# A narrated run (provided)
# ---------------------------------------------------------------------------

def demo(seed=1):
    c = Cluster(5, seed)
    c.run_until(lambda c: c.leader() is not None, 300)
    old = c.leader()
    print(f"-- an election: S{old.id} became leader of term {old.current_term} at tick {c.now}")
    for k in range(3):
        c.submit(("set", f"k{k}", k))
    c.run(40)
    print(c.describe())
    others = [i for i in range(5) if i != old.id]
    minority, majority = {old.id, others[0]}, set(others[1:])
    print(f"\n-- partition: {sorted(minority)} (with the old leader) | {sorted(majority)}")
    c.net.partition(minority, majority)
    old.client_request(("set", "lost", "?"))             # accepted by the old leader, but can it commit?
    c.run_until(lambda c: any(n.state == LEADER and n.id in majority for n in c.nodes), 300)
    new = next(n for n in c.nodes if n.state == LEADER and n.id in majority)
    new.client_request(("set", "won", "!"))
    c.run(60)
    print(c.describe())
    print("\n-- heal")
    c.net.heal()
    c.run(80)
    print(c.describe())


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "demo":
        demo(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    else:
        print(__doc__)
