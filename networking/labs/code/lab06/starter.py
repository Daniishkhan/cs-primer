"""Lab 6 starter: Toy Raft, in a deterministic simulation.

Reference: Diego Ongaro and John Ousterhout, "In Search of an Understandable
Consensus Algorithm" (the Raft paper), https://raft.github.io/raft.pdf
Section and figure numbers below refer to that paper. Figure 2 is the
one-page summary of the algorithm; keep it open while you work.

There are NO sockets here. A Network object carries messages between node
objects, with seeded random delays and drops, and time is a counter of
"ticks". Same seed, same run, every time.

    python3 starter.py demo [seed]     # a narrated run: election, commands, partition, heal

The simulator (Network, KVStateMachine, Cluster) is complete. You write the
RaftNode methods marked TODO, one milestone at a time, and run `python3 check.py`
after each one.
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
        """Restart the election countdown with a fresh random timeout.

        Set self.election_elapsed = 0 and self.election_timeout to a random
        integer in ELECTION_TIMEOUT (inclusive): self.rng.randint(*ELECTION_TIMEOUT).
        Why random? If every node used the same timeout they would all become
        candidates at the same tick and split the vote, forever (paper 5.2).
        """
        raise NotImplementedError("TODO milestone 1: reset_election_timer")

    def become_follower(self, term):
        """Move to `term` as a follower.

        If `term` is newer than self.current_term, adopt it and forget our vote
        (self.voted_for = None): a vote belongs to one term. Whatever we were
        before, we are now FOLLOWER. Clear self.votes. Never lower the term.
        """
        raise NotImplementedError("TODO milestone 1: become_follower")

    def start_election(self):
        """The election timeout fired: campaign (paper 5.2).

        1. Increment current_term; state = CANDIDATE.
        2. Vote for ourselves: voted_for = self.id, votes = {self.id}.
        3. Restart the election timer (so a failed election is retried later).
        4. Send a RequestVote to every peer with our term, our id, and
           last_log_index / last_log_term (self.last_log_index(), self.last_log_term()).
        Message shape: see the table at the top of this file.
        """
        raise NotImplementedError("TODO milestone 1: start_election")

    def become_leader(self):
        """A candidate won its election.

        state = LEADER; leader_id = self.id. Initialise, for every peer,
        next_index[peer] = last_log_index + 1 and match_index[peer] = 0
        (Figure 2, "Volatile state on leaders"). Then call
        self.broadcast_append_entries() so the other nodes learn at once that
        there is a leader and don't start their own elections.
        """
        raise NotImplementedError("TODO milestone 1: become_leader")

    def on_message(self, src, msg):
        """Every incoming message arrives here first.

        Rule for all servers (Figure 2): if the message's term is greater than
        ours, call self.become_follower(msg["term"]) BEFORE doing anything else.
        Then dispatch on msg["type"] to on_request_vote, on_request_vote_reply,
        on_append_entries or on_append_entries_reply (constants REQUEST_VOTE, ...).
        """
        raise NotImplementedError("TODO milestone 1: on_message")

    def on_request_vote(self, src, msg):
        """Decide whether to vote for the candidate, and answer with a RequestVoteReply.

        Grant the vote only if ALL of these hold:
          - msg["term"] == self.current_term (a request from an older term is refused;
            a newer one has already been adopted by on_message);
          - we have not voted for someone else this term: voted_for is None or
            equals msg["candidate_id"];
          - self.candidate_log_ok(msg)  (milestone 5; until then it is a stub that says yes).
        If we grant: record voted_for and restart our election timer.
        Always reply with our current_term and vote_granted True/False.
        """
        raise NotImplementedError("TODO milestone 1: on_request_vote")

    def on_request_vote_reply(self, src, msg):
        """Count votes.

        Ignore the reply unless we are still a CANDIDATE and msg["term"] ==
        self.current_term (it may be a late answer from an old election).
        If the vote was granted, add the sender to self.votes; once we hold a
        majority (self.majority()), call self.become_leader().
        """
        raise NotImplementedError("TODO milestone 1: on_request_vote_reply")

    # -- Milestone 2: heartbeats (section 5.2) -------------------------------
    def broadcast_append_entries(self):
        """Send an AppendEntries to every peer. Reset self.heartbeat_elapsed to 0.

        Called when we become leader, every HEARTBEAT_INTERVAL ticks (by tick()),
        and whenever there is something new to replicate. With nothing new it
        is a heartbeat: followers reset their election timers when they receive it.
        """
        raise NotImplementedError("TODO milestone 2: broadcast_append_entries")

    def send_append_entries(self, peer):
        """Send one AppendEntries to `peer`.

        Milestone 2 (heartbeats): an empty message is enough: entries = [].
        Milestone 3: fill the message in properly (paper 5.3):
          prev_log_index = next_index[peer] - 1
          prev_log_term  = self.term_at(prev_log_index)
          entries        = self.log[prev_log_index:]   # everything the peer is missing
          leader_commit  = self.commit_index           # milestone 4 uses this
        """
        raise NotImplementedError("TODO milestone 2: send_append_entries")

    def on_append_entries(self, src, msg):
        """Handle an AppendEntries from a (supposed) leader.

        Milestone 2:
          - If msg["term"] < current_term: reply success=False (with our term). Do NOT
            reset the election timer: this is a deposed leader.
          - Otherwise it is a real leader of this term: become_follower(msg["term"])
            (a candidate of the same term steps down), remember leader_id,
            reset_election_timer(), and reply success=True.
        Milestone 3 (paper 5.3, Figure 2): after the term check, run the consistency
          check. If prev_log_index > last_log_index, or term_at(prev_log_index) !=
          prev_log_term, reply success=False and change nothing.
          Otherwise walk the new entries: if an existing entry has the same index but a
          DIFFERENT term, delete it and everything after it; append entries we don't
          have yet. Do not truncate when entries already match (an old or duplicated
          message must not delete newer entries). Reply success=True with
          match_index = prev_log_index + len(entries).
        Milestone 4: if msg["leader_commit"] > commit_index, set
          commit_index = min(leader_commit, match_index) and call apply_committed().
          (Not the whole leader_commit: only the part this message verified.)
        Entries arrive as (term, command) pairs; tuple(entry) is safe.
        """
        raise NotImplementedError("TODO milestone 2: on_append_entries")

    # -- Milestone 3: log replication (section 5.3) ----------------------------
    def client_request(self, command):
        """Leader only: accept a client command.

        If we are not the leader return None. Otherwise append (current_term, command)
        to self.log, call broadcast_append_entries() to start replicating it, and
        return the new entry's log index (1-based, so the first entry is 1).
        """
        raise NotImplementedError("TODO milestone 3: client_request")

    def on_append_entries_reply(self, src, msg):
        """Leader: process a follower's answer.

        Ignore it unless we are LEADER and msg["term"] == current_term.
        success: match_index[src] = max(match_index[src], msg["match_index"]);
                 next_index[src] = match_index[src] + 1; then call advance_commit_index() (milestone 4).
        failure: the follower's log doesn't match at prev_log_index. Back up:
                 next_index[src] = max(match_index[src] + 1, next_index[src] - 1)
                 and call send_append_entries(src) again straight away.
        """
        raise NotImplementedError("TODO milestone 3: on_append_entries_reply")

    # -- Milestone 4: the commit rule and the state machine (section 5.4.2) -----
    def advance_commit_index(self):
        """Leader: move commit_index forward if a new entry is safely replicated (paper 5.4.2).

        Find the largest N > commit_index such that
          (a) log[N] was written in the CURRENT term: term_at(N) == current_term, and
          (b) a majority has it: 1 (us) + number of peers with match_index >= N
              is at least self.majority().
        Set commit_index = N, then call apply_committed().
        Rule (a) is the subtle one ("Figure 8"): never commit an entry from an older
        term just by counting copies; it commits indirectly when a current-term entry
        after it does.
        """
        raise NotImplementedError("TODO milestone 4: advance_commit_index")

    def apply_committed(self):
        """Apply entries last_applied+1 .. commit_index to the state machine, in order.

        For each: last_applied += 1, then self.sm.apply(index, command), where
        command is the second element of the log entry (index i is self.log[i - 1]).
        """
        raise NotImplementedError("TODO milestone 4: apply_committed")

    # -- Milestone 5: the voting restriction (section 5.4.1) -----------------------
    def candidate_log_ok(self, msg):
        """Is the candidate's log at least as up to date as ours? (paper 5.4.1)

        Compare the TERM of the last entries first; the higher term is more up to date.
        If the last terms are equal, the longer log (higher last index) is more up to date.
        Candidate's values: msg["last_log_term"], msg["last_log_index"].
        Ours: self.last_log_term(), self.last_log_index().
        Hint: Python compares tuples left to right.
        """
        raise NotImplementedError("TODO milestone 5: candidate_log_ok")


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
