"""Self-check for Lab 6.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

There are no sockets: every scenario runs on the deterministic simulator, so a
failure names a seed you can replay. Each milestone first runs small unit tests
on a single node (so you can see exactly which rule is wrong), then runs 50
seeded cluster scenarios while a Monitor watches the safety properties of the
Raft paper (Figure 3):

  Election Safety        at most one leader per term
  Log Matching           same index + same term  =>  identical logs up to there
  Leader Completeness    a new leader already holds every entry committed earlier
  State Machine Safety   no two nodes apply different commands at the same index

Prints ✔ / ✘ / … (not implemented yet).
"""
import importlib
import random
import sys

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
LEADER, FOLLOWER, CANDIDATE = mod.LEADER, mod.FOLLOWER, mod.CANDIDATE
SEEDS = range(50)
results = []


class NotStarted(Exception):
    pass


def check(name, fn):
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
    except Exception as e:  # a crash inside your node is a bug worth seeing
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


# ---------------------------------------------------------------------------
# Running only the milestones you have reached: later methods become no-ops
# ---------------------------------------------------------------------------

FIRST = {
    "reset_election_timer": 1, "become_follower": 1, "start_election": 1, "become_leader": 1,
    "on_message": 1, "on_request_vote": 1, "on_request_vote_reply": 1,
    "broadcast_append_entries": 2, "send_append_entries": 2, "on_append_entries": 2,
    "client_request": 3, "on_append_entries_reply": 3,
    "advance_commit_index": 4, "apply_committed": 4,
    "candidate_log_ok": 5,
}


def node_class(k):
    """RaftNode with every method from a later milestone replaced by a harmless stub."""
    stubs = {}
    for name, first in FIRST.items():
        if first > k:
            stubs[name] = (lambda self, *a, **kw: True) if name == "candidate_log_ok" else (lambda self, *a, **kw: None)
    return type("StubbedRaftNode", (mod.RaftNode,), stubs) if stubs else mod.RaftNode


# ---------------------------------------------------------------------------
# The Monitor: checks the Raft safety properties after every tick
# ---------------------------------------------------------------------------

class Monitor:
    def __init__(self, label=""):
        self.label = label
        self.problems = []
        self.leader_of_term = {}
        self.announced = set()
        self.committed = {}          # index -> (term, command), as seen in some node's committed prefix
        self.last_term = {}
        self.first_leader_term = None
        self.leader_terms = set()
        self.ticks = 0

    def bad(self, c, text):
        if len(self.problems) < 3:
            self.problems.append(f"{self.label} tick {c.now}: {text}")

    def observe(self, c):
        self.ticks += 1
        for i in sorted(c.up):
            n = c.nodes[i]
            if n.current_term < self.last_term.get(i, 0):
                self.bad(c, f"S{i}'s term went backwards ({self.last_term[i]} -> {n.current_term})")
            self.last_term[i] = n.current_term
            if n.state == LEADER:
                self.leader_terms.add(n.current_term)
                if self.leader_of_term.setdefault(n.current_term, i) != i:
                    self.bad(c, f"ELECTION SAFETY: S{self.leader_of_term[n.current_term]} and S{i} are both leader of term {n.current_term}")
                if (i, n.current_term) not in self.announced:
                    self.announced.add((i, n.current_term))
                    for idx, entry in self.committed.items():
                        if idx > len(n.log) or tuple(n.log[idx - 1]) != entry:
                            self.bad(c, f"LEADER COMPLETENESS: S{i} became leader of term {n.current_term} "
                                        f"without committed entry {idx} {entry}")
                            break
        for i in sorted(c.up):
            n = c.nodes[i]
            if n.commit_index > len(n.log):
                self.bad(c, f"S{i} commit_index {n.commit_index} is beyond its log ({len(n.log)} entries)")
                continue
            for idx in range(1, n.commit_index + 1):
                entry = tuple(n.log[idx - 1])
                seen = self.committed.setdefault(idx, entry)
                if seen != entry:
                    self.bad(c, f"S{i} has committed entry {idx} = {entry} but {seen} was committed there before")
        if c.now % 5 == 0:
            self.log_matching(c)
        if c.violations:
            self.bad(c, "STATE MACHINE SAFETY: " + c.violations[0])
            del c.violations[:]

    def log_matching(self, c):
        ids = sorted(c.up)
        for a in ids:
            for b in ids:
                if a < b:
                    la, lb = c.nodes[a].log, c.nodes[b].log
                    for k in range(min(len(la), len(lb)) - 1, -1, -1):
                        if la[k][0] == lb[k][0]:
                            if [tuple(e) for e in la[:k + 1]] != [tuple(e) for e in lb[:k + 1]]:
                                self.bad(c, f"LOG MATCHING: S{a} and S{b} both have term {la[k][0]} at index {k + 1} "
                                            f"but their logs differ before it")
                            break

    def assert_clean(self, c=None):
        if c is not None:
            self.log_matching(c)
        assert not self.problems, " | ".join(self.problems)


def new_cluster(k, seed, drop=0.0, n=5, label="scenario"):
    c = mod.Cluster(n, seed, node_cls=node_class(k), drop=drop)
    m = Monitor(f"[{label}, seed {seed}]")
    c.observers.append(m.observe)
    return c, m


def wait_leader(c, seed, within=200, what="elect a leader"):
    t = c.run_until(lambda c: c.leader() is not None, within)
    assert t is not None, f"seed {seed}: the cluster failed to {what} within {within} ticks"
    return c.leader()


def same_logs(c):
    logs = [[tuple(e) for e in c.nodes[i].log] for i in sorted(c.up)]
    return all(l == logs[0] for l in logs)


# ---------------------------------------------------------------------------
# Single-node unit-test helpers
# ---------------------------------------------------------------------------

def unit_node(k, node_id=0, n=5, term=0, log=None, seed=1):
    sent = []
    sm = mod.KVStateMachine(node_id, lambda *a: None)
    peers = [j for j in range(n) if j != node_id]
    node = node_class(k)(node_id, peers, lambda dst, msg: sent.append((dst, msg)), random.Random(seed), sm)
    node.current_term = term
    node.log = list(log or [])
    return node, sent


def make_leader(k, term=3, log=None, n=5):
    """Run a real election on a lone node by feeding it votes, then forget the traffic."""
    node, sent = unit_node(k, 0, n, term - 1, log)
    node.start_election()
    for peer in (1, 2):
        node.on_message(peer, {"type": mod.VOTE_REPLY, "term": node.current_term, "vote_granted": True})
    assert node.state == LEADER, "a candidate with votes from itself and two others (3 of 5) should have become leader"
    del sent[:]
    return node, sent


def rv(term, cand, last_index=0, last_term=0):
    return {"type": mod.REQUEST_VOTE, "term": term, "candidate_id": cand,
            "last_log_index": last_index, "last_log_term": last_term}


def ae(term, prev=0, prev_term=0, entries=(), commit=0, leader=1):
    return {"type": mod.APPEND_ENTRIES, "term": term, "leader_id": leader, "prev_log_index": prev,
            "prev_log_term": prev_term, "entries": list(entries), "leader_commit": commit}


def reply_to(sent, dst):
    got = [m for d, m in sent if d == dst]
    assert got, f"expected a reply to S{dst}, but nothing was sent to it"
    return got[-1]


# ---------------------------------------------------------------------------
# Milestone 1: terms, states, elections
# ---------------------------------------------------------------------------

def m1():
    # randomized timeouts
    node, _ = unit_node(1)
    seen = set()
    for _ in range(300):
        node.reset_election_timer()
        assert node.election_elapsed == 0, "reset_election_timer must restart the countdown (election_elapsed = 0)"
        lo, hi = mod.ELECTION_TIMEOUT
        assert lo <= node.election_timeout <= hi, f"timeout {node.election_timeout} is outside ELECTION_TIMEOUT {lo}-{hi}"
        seen.add(node.election_timeout)
    assert len(seen) >= 10, "election timeouts should be random (use self.rng.randint), not a constant"
    # an election timeout starts an election
    node, sent = unit_node(1, node_id=2, term=4)
    for _ in range(mod.ELECTION_TIMEOUT[1]):
        node.tick()
    assert node.state == CANDIDATE, f"after a full election timeout a follower should be a candidate, not {node.state}"
    assert node.current_term == 5 and node.voted_for == 2, "a candidate increments its term and votes for itself"
    reqs = [(d, m) for d, m in sent if m["type"] == mod.REQUEST_VOTE]
    assert sorted(d for d, _ in reqs) == [0, 1, 3, 4], f"RequestVote should go to every other node, went to {[d for d, _ in reqs]}"
    assert all(m["term"] == 5 and m["candidate_id"] == 2 for _, m in reqs), "RequestVote must carry the new term and our id"
    # voting: one vote per term, first come first served
    node, sent = unit_node(1, node_id=0, term=0)
    node.on_message(2, rv(1, 2))
    r = reply_to(sent, 2)
    assert r["type"] == mod.VOTE_REPLY and r["vote_granted"] is True and r["term"] == 1, f"should grant the first request of a term, got {r}"
    assert node.current_term == 1 and node.voted_for == 2, "granting a vote records it in voted_for (and adopts the term)"
    node.on_message(3, rv(1, 3))
    assert reply_to(sent, 3)["vote_granted"] is False, "a second candidate in the same term must be refused (one vote per term)"
    node.on_message(2, rv(1, 2))
    assert reply_to(sent, 2)["vote_granted"] is True, "repeating the same candidate's request is fine to grant again"
    node.on_message(4, rv(0, 4))
    r = reply_to(sent, 4)
    assert r["vote_granted"] is False and r["term"] == 1, "a request from an older term is refused, and the reply carries our newer term"
    node.on_message(3, rv(2, 3))
    assert reply_to(sent, 3)["vote_granted"] is True and node.voted_for == 3, "a higher term resets the vote: grant to the new term's first candidate"
    # winning
    node, sent = unit_node(1, node_id=0)
    node.start_election()
    t = node.current_term
    node.on_message(1, {"type": mod.VOTE_REPLY, "term": t, "vote_granted": True})
    assert node.state == CANDIDATE, "2 votes of 5 (self + one) is not a majority"
    node.on_message(2, {"type": mod.VOTE_REPLY, "term": t, "vote_granted": False})
    node.on_message(3, {"type": mod.VOTE_REPLY, "term": t - 1, "vote_granted": True})
    assert node.state == CANDIDATE, "a refused vote, or a vote from an older term, must not count"
    node.on_message(4, {"type": mod.VOTE_REPLY, "term": t, "vote_granted": True})
    assert node.state == LEADER, "3 votes of 5 is a majority: the candidate should become leader"
    # a higher term anywhere means 'I am out of date': step down
    node.on_message(3, {"type": mod.VOTE_REPLY, "term": t + 3, "vote_granted": False})
    assert node.state == FOLLOWER and node.current_term == t + 3 and node.voted_for is None, \
        "seeing a higher term must make a leader a follower in that term, with no vote cast"
    # whole clusters
    leaders_seen = 0
    for seed in SEEDS:
        c, m = new_cluster(1, seed, drop=0.05 if seed % 2 else 0.0, label="election")
        c.run(300)
        m.assert_clean(c)
        assert m.leader_terms, f"seed {seed}: nobody was elected in 300 ticks"
        first = min(m.leader_terms)
        assert first >= 1
        leaders_seen += len(m.leader_terms)
    return f"50 seeds, 300 ticks each, no term ever had two leaders ({leaders_seen} leaders elected in total)"


# ---------------------------------------------------------------------------
# Milestone 2: heartbeats and re-election
# ---------------------------------------------------------------------------

def m2():
    node, sent = make_leader(2)
    node.broadcast_append_entries()
    hb = [(d, m) for d, m in sent if m["type"] == mod.APPEND_ENTRIES]
    assert sorted(d for d, _ in hb) == [1, 2, 3, 4], "a leader's broadcast goes to every peer"
    assert all(m["term"] == node.current_term and m["leader_id"] == 0 and m["entries"] == [] for _, m in hb), \
        "a heartbeat is an AppendEntries with the leader's term and no entries"
    del sent[:]
    for _ in range(mod.HEARTBEAT_INTERVAL - 1):
        node.tick()
    assert not sent, f"no heartbeat should go out before {mod.HEARTBEAT_INTERVAL} ticks have passed"
    node.tick()
    assert len([1 for d, m in sent if m["type"] == mod.APPEND_ENTRIES]) == 4, \
        f"every {mod.HEARTBEAT_INTERVAL} ticks the leader must heartbeat all four followers"
    # followers
    node, sent = unit_node(2, node_id=3, term=2)
    node.election_elapsed = mod.ELECTION_TIMEOUT[0] - 2
    node.on_message(1, ae(2))
    assert node.election_elapsed == 0, "a valid AppendEntries from the current leader must reset the election timer"
    r = reply_to(sent, 1)
    assert r["type"] == mod.APPEND_REPLY and r["success"] is True and r["term"] == 2, f"heartbeat should be acknowledged, got {r}"
    node.election_elapsed = 10
    node.on_message(0, ae(1, leader=0))
    assert node.election_elapsed == 10, "an AppendEntries from an OLD term is not a live leader: don't reset the timer"
    r = reply_to(sent, 0)
    assert r["success"] is False and r["term"] == 2, "reject an old-term AppendEntries, telling the sender our newer term"
    node, sent = unit_node(2, node_id=3, term=2)
    node.start_election()
    assert node.state == CANDIDATE
    node.on_message(1, ae(node.current_term, leader=1))
    assert node.state == FOLLOWER, "a candidate that hears from a leader of its own term must step down"
    # clusters: quiet while the leader lives, re-election when it dies
    for seed in SEEDS:
        c, m = new_cluster(2, seed, label="heartbeats")
        wait_leader(c, seed)
        c.run(60)
        old = c.leader()
        t0, terms = old.current_term, {x.current_term for x in c.nodes}
        assert terms == {t0}, f"seed {seed}: 60 ticks after an election every node should be in term {t0}, found {sorted(terms)}"
        c.run(300)
        assert c.leader() is old and {x.current_term for x in c.nodes} == {t0}, \
            f"seed {seed}: with a healthy leader and no message loss, nobody should start an election (heartbeats keep followers quiet)"
        c.crash(old.id)
        t = c.run_until(lambda c: c.leader() is not None and c.leader().id != old.id, 200)
        assert t is not None, f"seed {seed}: the cluster did not elect a new leader after the leader crashed"
        new = c.leader()
        assert new.current_term > t0, "the new leader must have a higher term than the crashed one"
        c.restart(old.id)
        c.run(100)
        assert c.nodes[old.id].state == FOLLOWER and c.nodes[old.id].current_term == new.current_term, \
            f"seed {seed}: the restarted old leader should be a follower in term {new.current_term}, it is {c.nodes[old.id].state} in term {c.nodes[old.id].current_term}"
        assert len(c.leaders()) == 1
        m.assert_clean(c)
    return "50 seeds: quiet for 300 ticks under a live leader; re-election after a crash; the old leader rejoins as a follower"


# ---------------------------------------------------------------------------
# Milestone 3: log replication and the consistency check
# ---------------------------------------------------------------------------

A_LOG = [(1, ("set", "a", 1)), (1, ("set", "b", 2)), (2, ("set", "c", 3))]


def m3():
    # follower side: the consistency check
    node, sent = unit_node(3, node_id=3, term=2, log=A_LOG)
    node.on_message(1, ae(2, prev=3, prev_term=2, entries=[(2, ("set", "d", 4))]))
    r = reply_to(sent, 1)
    assert r["success"] and r["match_index"] == 4 and len(node.log) == 4, "a matching prevLogIndex/prevLogTerm should append the new entry (match_index 4)"
    node, sent = unit_node(3, node_id=3, term=2, log=A_LOG)
    node.on_message(1, ae(2, prev=5, prev_term=2, entries=[(2, ("set", "x", 0))]))
    assert reply_to(sent, 1)["success"] is False and node.log == A_LOG, "prevLogIndex beyond our log: refuse, change nothing"
    node.on_message(1, ae(2, prev=3, prev_term=1, entries=[(2, ("set", "x", 0))]))
    assert reply_to(sent, 1)["success"] is False and node.log == A_LOG, "same index but a different term at prevLogIndex: refuse, change nothing"
    node.on_message(1, ae(2, prev=1, prev_term=1, entries=[(3, ("set", "x", 9))]))
    r = reply_to(sent, 1)
    assert r["success"] and node.log == [A_LOG[0], (3, ("set", "x", 9))], \
        f"a conflicting entry (index 2: term 1 vs 3) must delete it and everything after it; log is now {node.log}"
    node, sent = unit_node(3, node_id=3, term=2, log=A_LOG)
    node.on_message(1, ae(2, prev=0, prev_term=0, entries=A_LOG[:2]))
    r = reply_to(sent, 1)
    assert r["success"] and node.log == A_LOG and r["match_index"] == 2, \
        "an old or duplicated AppendEntries that matches our log must NOT truncate entries it doesn't mention"
    node, sent = unit_node(3, node_id=3, term=2)
    node.on_message(1, ae(2, prev=0, prev_term=0, entries=A_LOG))
    assert node.log == A_LOG and reply_to(sent, 1)["match_index"] == 3, "an empty follower accepts a whole log from prevLogIndex 0"
    # leader side
    node, sent = unit_node(3)
    assert node.client_request(("set", "k", 1)) is None and node.log == [], "only a leader accepts client commands"
    node, sent = make_leader(3, term=3)
    assert node.client_request(("set", "k", 1)) == 1, "client_request returns the new entry's log index (1)"
    assert node.client_request(("set", "k", 2)) == 2
    assert node.log == [(3, ("set", "k", 1)), (3, ("set", "k", 2))], f"entries are stored as (term, command); log is {node.log}"
    msgs = [m for d, m in sent if d == 4 and m["type"] == mod.APPEND_ENTRIES]
    assert msgs and msgs[-1]["prev_log_index"] == 0 and len(msgs[-1]["entries"]) == 2, "the leader should replicate new entries to followers"
    del sent[:]
    node.on_message(4, {"type": mod.APPEND_REPLY, "term": 3, "success": False, "match_index": 0})
    node.next_index[4] = 3
    node.on_message(4, {"type": mod.APPEND_REPLY, "term": 3, "success": False, "match_index": 0})
    retry = [m for d, m in sent if d == 4]
    assert retry and retry[-1]["prev_log_index"] == 1 and node.next_index[4] == 2, \
        "after a failed AppendEntries the leader must step next_index back and retry with an earlier prevLogIndex"
    node.on_message(4, {"type": mod.APPEND_REPLY, "term": 3, "success": True, "match_index": 2})
    assert node.match_index[4] == 2 and node.next_index[4] == 3, "success: match_index = what the follower reports, next_index = match_index + 1"
    # clusters: replicate, then repair diverged logs
    for seed in SEEDS:
        c, m = new_cluster(3, seed, drop=0.1 if seed % 3 == 0 else 0.0, label="replication")
        wait_leader(c, seed)
        c.run(40)
        leader = c.leader()
        for k in range(8):
            assert c.submit(("set", f"k{k}", k)) is not None
            c.run(3)
        t = c.run_until(lambda c: same_logs(c) and len(c.nodes[0].log) >= 8, 400)
        if t is None and c.leader() is not leader:
            continue                       # a leadership change legitimately reshuffles uncommitted entries
        assert t is not None, f"seed {seed}: after 400 ticks the logs still differ: " + "; ".join(
            f"S{i}:{[e[0] for e in c.nodes[i].log]}" for i in range(5))
        m.assert_clean(c)
    # a leader repairing wildly different logs (Figure 7 of the paper)
    for seed in range(20):
        c, m = new_cluster(3, seed, label="divergent logs")
        logs = [[(1, ("set", "a", 1)), (2, ("set", "b", 2)), (3, ("set", "c", 3))],
                [(1, ("set", "a", 1)), (2, ("set", "b", 2))],
                [(1, ("set", "a", 1)), (1, ("set", "x", 0)), (1, ("set", "y", 0)), (1, ("set", "z", 0))],
                [(1, ("set", "a", 1)), (2, ("set", "b", 2)), (2, ("set", "q", 0))],
                []]
        for i, n in enumerate(c.nodes):
            n.log, n.current_term = list(logs[i]), 3
        c.nodes[0].become_leader()
        c.nodes[0].state = LEADER
        c.run(150)
        for i in range(1, 5):
            assert [tuple(e) for e in c.nodes[i].log] == [tuple(e) for e in logs[0]], \
                f"seed {seed}: S{i}'s log {[e[0] for e in c.nodes[i].log]} was not repaired to the leader's {[e[0] for e in logs[0]]}"
        m.assert_clean(c)
    return "50 seeds replicated 8 commands to all 5 logs; 20 seeds repaired five very different logs"


# ---------------------------------------------------------------------------
# Milestone 4: the commit rule and the state machine
# ---------------------------------------------------------------------------

def m4():
    cmd = lambda i: ("set", f"k{i}", i)
    # Figure 8: an old-term entry on a majority is NOT committed by counting
    node, sent = make_leader(4, term=3, log=[(1, cmd(1)), (2, cmd(2))])
    node.match_index = {1: 2, 2: 2, 3: 0, 4: 0}
    node.advance_commit_index()
    assert node.commit_index == 0, ("FIGURE 8: entry 2 is from term 2 and sits on 3 of 5 servers, but the leader is in term 3. "
                                    "It must not be committed by counting replicas (it could still be overwritten); commit_index should stay 0")
    node.client_request(cmd(3))
    node.match_index = {1: 3, 2: 2, 3: 0, 4: 0}
    node.advance_commit_index()
    assert node.commit_index == 0, "entry 3 (current term) is only on 2 of 5 servers: not committed yet"
    node.match_index[2] = 3
    node.advance_commit_index()
    assert node.commit_index == 3, "entry 3 is from the current term and on 3 of 5 servers: commit it, and entries 1-2 with it"
    assert node.sm.data == {"k1": 1, "k2": 2, "k3": 3} and node.last_applied == 3, "committed entries must be applied to the state machine in order"
    node.match_index = {1: 0, 2: 0, 3: 0, 4: 0}
    node.advance_commit_index()
    assert node.commit_index == 3, "commit_index never goes backwards"
    node, _ = make_leader(4, term=2)
    for i in (1, 2, 3):
        node.client_request(cmd(i))
    node.match_index = {1: 2, 2: 1, 3: 0, 4: 0}
    node.advance_commit_index()
    assert node.commit_index == 1, f"entry 1 is on 3 of 5 servers (leader, S1, S2), entry 2 on only 2: commit_index should be 1, got {node.commit_index}"
    # applying
    node, _ = unit_node(4, term=1, log=[(1, ("set", "x", 1)), (1, ("set", "y", 2)), (1, ("del", "x"))])
    node.commit_index = 2
    node.apply_committed()
    assert node.sm.data == {"x": 1, "y": 2} and node.last_applied == 2, "apply_committed applies entries last_applied+1 .. commit_index"
    node.apply_committed()
    node.commit_index = 3
    node.apply_committed()
    assert node.sm.data == {"y": 2} and node.last_applied == 3, "each entry is applied exactly once, in order"
    # followers learn the commit index from the leader, but only up to what they verified
    node, sent = unit_node(4, node_id=3, term=1, log=[(1, cmd(1)), (1, cmd(2)), (1, cmd(3))])
    node.on_message(1, ae(1, prev=1, prev_term=1, entries=[(1, cmd(2))], commit=3))
    assert node.commit_index == 2, ("leader_commit is 3 but this message only verified entries up to index 2 (prev 1 + 1 new entry). "
                                    f"commit_index = min(leader_commit, index of last new entry) = 2, got {node.commit_index}")
    node.on_message(1, ae(1, prev=3, prev_term=1, entries=[], commit=3))
    assert node.commit_index == 3 and node.sm.data == {"k1": 1, "k2": 2, "k3": 3}, "a heartbeat can carry the commit index forward"
    # clusters
    unchanged = 0
    for seed in SEEDS:
        c, m = new_cluster(4, seed, drop=0.04 if seed % 2 else 0.0, label="commit")
        wait_leader(c, seed)
        term0 = c.leader().current_term
        for k in range(15):
            c.submit(cmd(k))
            c.run(4)
        c.run(200)
        m.assert_clean(c)
        assert len({n.commit_index for n in c.nodes}) == 1 and c.nodes[0].commit_index >= 1, \
            f"seed {seed}: the nodes disagree on commit_index: {[n.commit_index for n in c.nodes]}"
        assert len({tuple(sorted(n.sm.data.items())) for n in c.nodes}) == 1, f"seed {seed}: the state machines differ"
        if max(m.leader_terms) == term0 and min(m.leader_terms) == term0:
            unchanged += 1
            assert c.nodes[0].commit_index == 15 and c.nodes[0].sm.data == {f"k{k}": k for k in range(15)}, \
                f"seed {seed}: with one stable leader all 15 commands should be committed and applied, got commit_index {c.nodes[0].commit_index}"
    return f"50 seeds: logs, commit indexes and key-value stores identical everywhere ({unchanged} seeds had one stable leader and committed all 15 commands)"


# ---------------------------------------------------------------------------
# Milestone 5: the voting restriction
# ---------------------------------------------------------------------------

def chaos(seed, partitions, label):
    """Random crashes (or partitions) while clients keep writing, then heal and require recovery."""
    c, m = new_cluster(5, seed, drop=0.02, label=label)
    rnd = random.Random(seed + 777)
    sent = 0
    for _ in range(700):
        r = rnd.random()
        if partitions:
            if r < 0.012:
                ids = list(range(5))
                rnd.shuffle(ids)
                cut = rnd.choice([1, 2])
                c.net.partition(set(ids[:cut]), set(ids[cut:]))
            elif r < 0.03:
                c.net.heal()
            if rnd.random() < 0.006 and len(c.up) > 3:
                c.crash(rnd.choice(sorted(c.up)))
            elif rnd.random() < 0.02 and len(c.up) < 5:
                c.restart(rnd.choice(sorted(set(range(5)) - c.up)))
        else:
            if r < 0.02 and len(c.up) > 3:
                c.crash(rnd.choice(sorted(c.up)))
            elif r < 0.05 and len(c.up) < 5:
                c.restart(rnd.choice(sorted(set(range(5)) - c.up)))
        if rnd.random() < 0.15:
            c.submit(("set", f"k{sent % 7}", sent))
            sent += 1
        c.step()
    m.assert_clean(c)
    c.net.heal()
    for i in sorted(set(range(5)) - c.up):
        c.restart(i)
    c.run(250)
    # liveness: with everyone connected again, a new command must commit everywhere
    tag = ("set", "final", seed)

    def done(c):
        return all(n.sm.data.get("final") == seed for n in c.nodes)
    for _ in range(12):
        if c.leader() is not None:
            c.submit(tag)
        if c.run_until(done, 60) is not None:
            break
    assert done(c), f"{m.label} LIVENESS: after healing, a new command never committed on every node ({[n.sm.data.get('final') for n in c.nodes]})"
    c.run(60)
    m.assert_clean(c)
    assert same_logs(c), f"{m.label}: after healing, the logs never converged"
    assert len({tuple(sorted(n.sm.data.items())) for n in c.nodes}) == 1, f"{m.label}: the state machines differ"
    return c


def m5():
    full = node_class(5)
    node, sent = unit_node(5, node_id=0, term=2, log=[(1, ("set", "a", 1)), (2, ("set", "b", 2))])
    table = [
        ((1, 5), False, "last term 1 < ours 2: older log loses even if it is longer"),
        ((2, 1), False, "same last term, but a shorter log"),
        ((2, 2), True, "identical log: at least as up to date"),
        ((2, 7), True, "same last term, longer log"),
        ((3, 1), True, "higher last term wins even with a shorter log"),
    ]
    for (lterm, lidx), want, why in table:
        got = node.candidate_log_ok(rv(2, 1, last_index=lidx, last_term=lterm))
        assert got is want, f"candidate (last term {lterm}, last index {lidx}) vs ours (2, 2): expected {want}: {why}"
    node, sent = unit_node(5, node_id=0, term=2, log=[(1, ("set", "a", 1)), (2, ("set", "b", 2))])
    node.on_message(3, rv(4, 3, last_index=1, last_term=1))
    r = reply_to(sent, 3)
    assert r["vote_granted"] is False, "a candidate with a stale log must be refused even though its term is higher"
    assert node.current_term == 4 and r["term"] == 4, "...but we still adopt its higher term"
    assert node.voted_for is None, "a refused request must not use up our vote for the term"
    node.on_message(2, rv(4, 2, last_index=2, last_term=2))
    assert reply_to(sent, 2)["vote_granted"] is True, "a candidate with an up-to-date log can still get our vote in that term"
    for seed in SEEDS:
        chaos(seed, partitions=False, label="crash chaos")
    return "50 seeds of random crashes and restarts under client load: no safety violation, and every cluster recovered"


# ---------------------------------------------------------------------------
# Milestone 6: partitions
# ---------------------------------------------------------------------------

def m6():
    stale_seen = 0
    for seed in SEEDS:
        c, m = new_cluster(6, seed, label="partition")
        wait_leader(c, seed)
        c.run(40)
        for k in range(3):
            c.submit(("set", f"before{k}", k))
            c.run(4)
        c.run(40)
        old = c.leader()
        base = old.commit_index
        assert base >= 3, f"seed {seed}: the first 3 commands should be committed before the partition (commit_index {base})"
        others = [i for i in range(5) if i != old.id]
        friends = {old.id} | ({others[0]} if seed % 2 else set())
        rest = set(range(5)) - friends
        c.net.partition(friends, rest)
        for k in range(3):                                 # the old leader keeps accepting commands...
            assert old.client_request(("set", f"minority{k}", k)) is not None
            c.run(3)
        c.run(100)
        assert old.commit_index == base, (f"seed {seed}: the leader in the minority ({len(friends)} of 5 nodes) committed "
                                          f"entries (commit_index {base} -> {old.commit_index}); it cannot reach a majority")
        new = next((n for n in c.nodes if n.id in rest and n.state == LEADER), None)
        assert new is not None and new.current_term > old.current_term, \
            f"seed {seed}: the majority side ({sorted(rest)}) should have elected a new leader with a higher term"
        for k in range(3):
            assert new.client_request(("set", f"majority{k}", k)) is not None
            c.run(3)
        c.run(60)
        assert new.commit_index >= base + 3, f"seed {seed}: the majority side should commit its commands (commit_index {new.commit_index})"
        assert old.state == LEADER, "the old leader has heard nothing, so it still believes it is leader (that is expected)"
        stale_seen += 1
        c.net.heal()
        c.run_until(lambda c: old.state == FOLLOWER, 100)
        assert old.state == FOLLOWER, f"seed {seed}: after healing, the old leader should have stepped down"
        for _ in range(8):
            if c.leader() is not None:
                c.submit(("set", "after", seed))
            if c.run_until(lambda c: same_logs(c) and all(n.sm.data.get("after") == seed for n in c.nodes), 40) is not None:
                break
        assert same_logs(c), f"seed {seed}: after healing, the logs did not converge: " + "; ".join(
            f"S{i}:{[e[0] for e in c.nodes[i].log]}" for i in range(5))
        for n in c.nodes:
            assert not any(key.startswith("minority") for key in n.sm.data), \
                f"seed {seed}: S{n.id} applied a command that was only ever accepted by the minority leader"
            assert all(n.sm.data.get(f"majority{k}") == k for k in range(3)), f"seed {seed}: S{n.id} is missing a committed majority command"
        m.assert_clean(c)
    for seed in SEEDS:
        chaos(seed, partitions=True, label="partition chaos")
    return ("50 seeds: the minority leader never committed, stepped down after healing, and its uncommitted commands vanished\n"
            "50 seeds of random partitions and crashes under load: all four safety properties held and every cluster recovered")


print(f"Lab 6 checks against {target}.py\n")
check("Milestone 1: terms, states, elections (one leader per term)", m1)
check("Milestone 2: heartbeats keep followers quiet; a crashed leader is replaced", m2)
check("Milestone 3: log replication and the consistency check", m3)
check("Milestone 4: the commit rule and the state machine", m4)
check("Milestone 5: the voting restriction (Leader Completeness)", m5)
check("Milestone 6: partitions, stale leaders, healing", m6)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
