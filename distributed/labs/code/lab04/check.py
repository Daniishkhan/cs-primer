"""Self-check for Lab 4: Multi-Paxos Replicated Log.

    python3 check.py                      # checks your starter.py
    python3 check.py solution             # checks the reference solution
    python3 check.py solution replay 4 17 # replay milestone 4, seed 17, with a long trace

Everything runs in one process on a seeded simulated network: no sockets, no threads, no
real time. The same seed gives the same run, so a failure names a seed you can replay.
Each milestone first runs small deterministic tests (so you can see which rule is wrong),
then hundreds of seeded runs. An omniscient Observer (see starter.py) watches every
accept and flags the moment two values are chosen for one slot, or a value nobody
proposed is chosen, or a node believes something is chosen that is not.

Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import os
import random
import signal
import sys
import traceback

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

args = sys.argv[1:]
target = args[0] if args and args[0] in ("starter", "solution") else "starter"
if args and args[0] in ("starter", "solution"):
    args = args[1:]
replay = None
if args:
    if len(args) == 3 and args[0] == "replay" and args[1].isdigit() and args[2].isdigit():
        replay = (int(args[1]), int(args[2]))
    else:
        sys.exit("usage: python3 check.py [starter|solution] [replay MILESTONE SEED]")
mod = importlib.import_module(target)
NOOP = mod.NOOP

# how many seeded runs each milestone does
SEEDS_M2, SEEDS_M3, SEEDS_M4, SEEDS_M5 = 300, 200, 120, 100
M3_BOUND = 2500            # simulated time units within which every proposer must have learned the value
M3_MEAN_MSGS, M3_MAX_MSGS = 1500, 4000   # duelling shows up as wasted messages
M3_REQUIRED = 0.95         # fraction of seeds that must finish within the bound

results = []
CUR = {"sim": None}


class Fail(AssertionError):
    """A check failed; `seed` (if any) is printed so it can be replayed."""

    def __init__(self, msg, seed=None):
        super().__init__(msg)
        self.seed = seed


def must(cond, msg):
    if not cond:
        raise Fail(msg)


def new_sim(seed, **kw):
    sim = mod.Sim(seed, **kw)
    CUR["sim"] = sim
    return sim


def no_violations(sim):
    if sim.observer.violations:
        raise Fail(sim.observer.violations[0])


# -------------------------------------------------------------------------------------
# Milestone 1: the acceptor
# -------------------------------------------------------------------------------------
def m1():
    A = mod.Acceptor
    # a fresh acceptor promises anything, and reports nothing
    d = {}
    a = A(d)
    r = a.on_prepare((1, 1))
    must(r == ("promise", {}), f"a fresh acceptor should answer prepare(1,1) with ('promise', {{}}), got {r!r}")
    # a lower or equal-lower ballot is refused, and the nack names the ballot to beat
    r = a.on_prepare((0, 5))
    must(r == ("nack", (1, 1)), f"prepare with a ballot below the promise must return ('nack', (1, 1)), got {r!r}")
    a.on_prepare((3, 1))
    r = a.on_prepare((2, 9))
    must(r == ("nack", (3, 1)), f"after promising (3,1), prepare(2,9) must be refused with ('nack', (3,1)), got {r!r}")
    # ballots are compared as (round, id): round first
    r = a.on_prepare((3, 2))
    must(r[0] == "promise", "ballot (3,2) is higher than (3,1) (the id breaks ties), so it should be promised")
    # accept rules
    r = a.on_accept((2, 1), 0, "late")
    must(r == ("nack", (3, 2)), f"accept below the promise must be refused: ('nack', (3, 2)), got {r!r}")
    must(0 not in d["accepted"], "a refused accept must not be stored")
    r = a.on_accept((3, 2), 0, "x")
    must(r[0] == "accepted", "accept with ballot == promised must be accepted (it is the ballot we promised to)")
    must(d["accepted"][0] == ((3, 2), "x"), "an accepted proposal is stored as accepted[slot] = (ballot, value)")
    r = a.on_accept((5, 1), 3, "z")
    must(r[0] == "accepted", "accept with a ballot ABOVE the promise is accepted too (no prepare needed)")
    must(d["promised"] == (5, 1), "accepting (5,1) must also raise promised to (5,1)")
    r = a.on_prepare((4, 1))
    must(r[0] == "nack", "after accepting at (5,1), prepare(4,1) must be refused")
    # the promise reports everything accepted, for every slot, and it is a copy
    r = a.on_prepare((6, 1))
    must(r == ("promise", {0: ((3, 2), "x"), 3: ((5, 1), "z")}),
         f"promise must carry every accepted proposal {{slot: (ballot, value)}}, got {r!r}")
    r[1].clear()
    must(d["accepted"] != {}, "the promise must carry a COPY of the accepted map: clearing it changed the acceptor")
    # a later accept at a higher ballot replaces the earlier one for that slot
    a.on_accept((7, 1), 0, "y")
    must(d["accepted"][0] == ((7, 1), "y"), "a higher-ballot accept replaces the stored proposal for that slot")
    # durability: a restarted acceptor is a NEW object over the SAME disk
    b = A(d)
    must(b.on_prepare((6, 9))[0] == "nack", "after a restart the acceptor forgot its promise: keep it in disk['promised']")
    must(b.on_prepare((8, 1)) == ("promise", {0: ((7, 1), "y"), 3: ((5, 1), "z")}),
         "after a restart the acceptor forgot what it accepted: keep it in disk['accepted']")
    # a duplicated accept is harmless
    b.on_accept((8, 1), 0, "w")
    must(b.on_accept((8, 1), 0, "w")[0] == "accepted", "a duplicate accept (same ballot, same value) must be accepted again")
    return "the two rules differ by one character: promise needs `>`, accept needs `>=`"


# -------------------------------------------------------------------------------------
# Milestone 2: single-decree Paxos
# -------------------------------------------------------------------------------------
def build_single(seed, n_acc, values, starts, **net):
    sim = new_sim(seed, auto_elect=False, **net)
    sim.observer.n_acceptors = n_acc
    acc = list(range(1, n_acc + 1))
    for a in acc:
        sim.add(a, mod.AcceptorNode)
    props = []
    for i, v in enumerate(values):
        sim.observer.propose(v)
        props.append(sim.add(11 + i, lambda nid, s, d, v=v, st=starts[i]: mod.Proposer(nid, s, d, acc, v, st)))
    return sim, acc, props


def single_consistent(sim, props):
    no_violations(sim)
    chosen = sim.observer.chosen.get(0)
    for p in props:
        if p.chosen is not None:
            must(chosen is not None, f"proposer {p.id} claims {p.chosen!r} is chosen, but no majority accepted anything")
            must(mod.vkey(p.chosen) == chosen[0],
                 f"proposer {p.id} claims {p.chosen!r} is chosen, but the value really chosen is {chosen[1]!r}")
    return chosen


def m2_unit():
    # 1. one proposer, perfect network: it must choose its own value
    sim, acc, (p,) = build_single(1, 3, ["X"], [0], min_delay=1, max_delay=1)
    sim.run(200, stop=lambda: p.chosen is not None)
    must(p.chosen == "X", f"a lone proposer on a perfect network should learn its own value 'X', got {p.chosen!r}")
    single_consistent(sim, [p])
    # 2. adoption: a value is already chosen (accepted by 3 of 5 acceptors); a rival proposing 'Y' must adopt it
    sim, acc, (p,) = build_single(2, 5, ["Y"], [0], min_delay=1, max_delay=1)
    for a in (1, 2, 3):
        sim.disks[a]["promised"] = (1, 9)
        sim.disks[a]["accepted"] = {0: ((1, 9), "X")}
    sim.observer.propose("X")
    sim.run(300, stop=lambda: p.chosen is not None)
    must(p.chosen == "X", f"'X' was already accepted by a majority, so the proposer must adopt it, not propose its own "
         f"'Y' (it learned {p.chosen!r}): phase 2 must use the value of the highest-ballot accepted proposal")
    # 3. the HIGHEST ballot wins, wherever it sits in the replies
    for new_first in (True, False):
        sim, acc, (p,) = build_single(3, 5, ["Z"], [0], min_delay=1, max_delay=1)
        sim.disks[1]["accepted"] = {0: ((1, 2), "new-value") if new_first else ((1, 1), "old-value")}
        sim.disks[2]["accepted"] = {0: ((1, 1), "old-value") if new_first else ((1, 2), "new-value")}
        for a in (1, 2):
            sim.observer.propose(sim.disks[a]["accepted"][0][1])
            sim.disks[a]["promised"] = sim.disks[a]["accepted"][0][0]
        sim.run(300, stop=lambda: p.chosen is not None)
        must(p.chosen == "new-value", f"two acceptors reported different accepted values; the one with the HIGHER ballot "
             f"must be adopted ('new-value'), but the proposer learned {p.chosen!r}")
    # 4. a proposal that was nacked starts a higher round
    sim, acc, (p,) = build_single(4, 3, ["V"], [0], min_delay=1, max_delay=1)
    for a in acc:
        sim.disks[a]["promised"] = (7, 3)
    sim.run(400, stop=lambda: p.chosen is not None)
    must(p.chosen == "V", "acceptors had promised ballot (7,3); the proposer must jump to a higher round after the nacks "
         "(round = max(round, promised round)) and then succeed")


def m2_seed(seed):
    rng = random.Random(seed * 31 + 5)
    n_acc = 3 if seed % 2 else 5
    values = ["X", "Y", "Z"][: 2 + seed % 2]
    starts = [rng.randint(0, 80) for _ in values]
    sim, acc, props = build_single(seed, n_acc, values, starts, drop=0.2, dup=0.1, min_delay=1, max_delay=15)
    if seed % 2 == 0:                      # crash one acceptor and restart it: its disk survives
        victim = rng.choice(acc)
        t = rng.randint(10, 150)
        sim.schedule(t, lambda: sim.crash(victim))
        sim.schedule(t + rng.randint(20, 120), lambda: sim.restart(victim))
    sim.run(700)
    chosen = single_consistent(sim, props)
    return chosen is not None


def m2():
    m2_unit()
    got = 0
    for seed in range(SEEDS_M2):
        try:
            got += bool(m2_seed(seed))
        except Fail as e:
            e.seed = seed
            raise
    must(got >= SEEDS_M2 * 0.6, f"safety held, but a value was chosen in only {got}/{SEEDS_M2} runs: the protocol is not making progress")
    return f"{SEEDS_M2} seeded runs on a network that drops 20%, duplicates 10% and reorders: never two values, never an invented value ({got} runs chose one)"


# -------------------------------------------------------------------------------------
# Milestone 3: liveness with randomized backoff
# -------------------------------------------------------------------------------------
def m3_unit():
    sim, acc, props = build_single(0, 3, ["X"], [0], min_delay=1, max_delay=1)     # needs milestone 2 to run at all
    sim.run(100, stop=lambda: props[0].chosen is not None)
    sim, acc, (p,) = build_single(1, 3, ["X"], [0])
    draws = {a: [p.retry_delay(a) for _ in range(40)] for a in (1, 2, 4, 6)}
    flat = [x for v in draws.values() for x in v]
    must(all(isinstance(x, int) or float(x).is_integer() for x in flat), "retry_delay must return a whole number of ticks")
    must(all(x >= 0 for x in flat), "retry_delay must not be negative")
    must(max(flat) > 0, "retry_delay returns 0: the proposer retries at once, which is what lets duelling proposers livelock. "
         "Return a randomized delay that grows with `attempt`")
    must(len(set(draws[4])) >= 5, "retry_delay(4) gave the same few values every time: it must be RANDOMIZED (use self.sim.rng)")
    mean = {a: sum(v) / len(v) for a, v in draws.items()}
    must(mean[4] > mean[1] * 1.5, f"the delay must grow with the attempt number (exponential backoff): "
         f"average {mean[1]:.0f} for attempt 1 but {mean[4]:.0f} for attempt 4")
    must(max(flat) <= 2000, "keep the delay bounded (a cap), or a proposer that failed 6 times sleeps for ages")


def m3_seed(seed):
    n = 8
    sim, acc, props = build_single(seed, 5, [chr(65 + i) for i in range(n)], [0] * n, drop=0.05, dup=0.05, min_delay=1, max_delay=3)
    sim.run(M3_BOUND, stop=lambda: all(p.chosen is not None for p in props))
    single_consistent(sim, props)
    return all(p.chosen is not None for p in props), sim.now, sum(sim.sent.values())


def m3():
    m3_unit()
    done, slowest, total, worst = 0, 0, 0, 0
    late = []
    for seed in range(SEEDS_M3):
        try:
            ok, t, msgs = m3_seed(seed)
        except Fail as e:
            e.seed = seed
            raise
        done += ok
        total += msgs
        if msgs > worst:
            worst, worst_seed = msgs, seed
        if ok:
            slowest = max(slowest, t)
        else:
            late.append(seed)
    if done < SEEDS_M3 * M3_REQUIRED:
        e = Fail(f"8 proposers with 8 different values should all have learned the chosen value within {M3_BOUND} ticks "
                 f"on at least {int(M3_REQUIRED * 100)}% of seeds, but only {done}/{SEEDS_M3} did "
                 f"(e.g. seeds {late[:4]}). They are probably duelling: back off, and randomize")
        e.seed = late[0]
        raise e
    mean = total / SEEDS_M3
    if mean > M3_MEAN_MSGS or worst > M3_MAX_MSGS:
        e = Fail(f"the proposers do finish, but they burn messages duelling: {mean:.0f} messages per run on average "
                 f"(limit {M3_MEAN_MSGS}), worst {worst} (limit {M3_MAX_MSGS}). A rejected proposer should wait a "
                 f"random, growing time before it tries again")
        e.seed = worst_seed
        raise e
    return (f"{done}/{SEEDS_M3} runs: 8 rival proposers all learn the one chosen value (slowest {slowest} ticks); "
            f"average {mean:.0f} messages per run, worst {worst}")


# -------------------------------------------------------------------------------------
# Milestone 4: Multi-Paxos
# -------------------------------------------------------------------------------------
def build_cluster(seed, n, ops_by_client=None, **net):
    sim = new_sim(seed, **net)
    sim.observer.n_acceptors = n
    ids = list(range(1, n + 1))
    for i in ids:
        sim.add(i, lambda nid, s, d: mod.Replica(nid, s, d, ids))
    return sim, ids


def leader_of(sim, ids):
    ls = [sim.nodes[i] for i in ids if sim.up[i] and sim.nodes[i].leading]
    return max(ls, key=lambda r: r.ballot) if ls else None


def cmd(k):
    return {"op": "put", "key": "k", "arg": k, "id": k, "client": 0, "seq": k}


def m4_unit():
    # (a) a stable leader runs phase 1 ONCE, then every command costs one round trip
    sim, ids = build_cluster(1, 3, auto_elect=False, min_delay=1, max_delay=4)
    r = sim.nodes[1]
    r.start_phase1()
    sim.run(200, stop=lambda: r.leading)
    must(r.leading and r.ballot == (1, 1), "replica 1 ran phase 1 on a quiet cluster and got promises from everyone: "
         f"it should be leading with ballot (1, 1); leading={r.leading}, ballot={r.ballot}")
    for k in range(1, 11):
        sim.observer.propose(cmd(k))
        r.propose(cmd(k))
    sim.run(400)
    no_violations(sim)
    got = [sim.observer.chosen.get(s, (None, None))[1] for s in range(1, 11)]
    must(got == [cmd(k) for k in range(1, 11)], f"ten commands proposed by a stable leader should fill slots 1..10 in order, got {got}")
    must(sim.sent["prepare"] == 3, f"a stable leader must NOT repeat phase 1 for each command: expected 3 prepare messages "
         f"(one phase 1 to 3 replicas), saw {sim.sent['prepare']}")
    for i in ids:
        must(sim.nodes[i].chosen == {s: cmd(s) for s in range(1, 11)},
             f"replica {i} should have learned slots 1..10, it knows {sorted(sim.nodes[i].chosen)}")
    # (b) recovery: the situation of the chapter's slot diagram. Slots 1-3 are chosen everywhere; slot 4 ('d') reached
    # only R1; slot 5 ('e') reached R1 and R2. R1 is down. A new leader (R2) must re-propose 'e' and fill slot 4 with a no-op.
    sim, ids = build_cluster(2, 3, auto_elect=False, min_delay=1, max_delay=3)
    b1 = (1, 1)
    full = {1: (b1, cmd(101)), 2: (b1, cmd(102)), 3: (b1, cmd(103))}
    for k in (101, 102, 103, 104, 105, 106):
        sim.observer.propose(cmd(k))
    sim.disks[1].update(promised=b1, accepted={**full, 4: (b1, cmd(104)), 5: (b1, cmd(105))})
    sim.disks[2].update(promised=b1, accepted={**full, 5: (b1, cmd(105))})
    sim.disks[3].update(promised=b1, accepted=dict(full))
    for i in ids:                                    # acceptors reload their (pre-seeded) disks
        sim.nodes[i] = mod.Replica(i, sim, sim.disks[i], ids)
        sim.nodes[i].on_start()
    sim.crash(1)
    r2 = sim.nodes[2]
    r2.start_phase1()
    sim.run(300, stop=lambda: r2.leading and r2.next_slot > 5)
    must(r2.leading, "replica 2 (with replica 3) should have completed phase 1: a majority of 3 is 2")
    must(r2.next_slot == 6, f"the new leader must continue AFTER the recovered slots: next_slot should be 6, it is {r2.next_slot}")
    r2.propose(cmd(106))
    sim.run(800)
    no_violations(sim)
    ch = {s: v[1] for s, v in sim.observer.chosen.items()}
    must(ch.get(4) == NOOP, f"slot 4 was accepted by nobody the new leader could reach: it must be filled with a no-op "
         f"so the log can advance (chosen: {ch.get(4)!r}). A gap that is never filled blocks every later slot")
    must(ch.get(5) == cmd(105), f"slot 5 had been accepted by replica 2, so the new leader must re-propose that value, got {ch.get(5)!r}")
    must(ch.get(6) == cmd(106), f"the new command should land in slot 6, got {ch.get(6)!r}")
    sim.restart(1)                                   # R1 returns, still holding the discarded 'd' for slot 4
    sim.run(sim.now + 600)
    no_violations(sim)
    for i in ids:
        must(sim.nodes[i].chosen == {1: cmd(101), 2: cmd(102), 3: cmd(103), 4: NOOP, 5: cmd(105), 6: cmd(106)},
             f"replica {i} should end with the same log [101,102,103,noop,105,106]; it has {sim.nodes[i].chosen}")


def m4_votes():
    # (c) counting: only replies for MY ballot count, and each acceptor counts once
    sim, ids = build_cluster(3, 3, auto_elect=False, min_delay=1, max_delay=1)
    r = sim.nodes[1]
    r.start_phase1()
    old = {"t": "promise", "b": (0, 2), "accepted": {}}
    r.on_promise(2, old)
    r.on_promise(3, old)
    must(not r.leading, "promises that answer an OLD ballot must not count: check msg['b'] == self.ballot")
    good = {"t": "promise", "b": r.ballot, "accepted": {}}
    r.on_promise(2, good)
    r.on_promise(2, good)
    must(not r.leading, "the same acceptor's promise twice (a duplicated message) is still ONE acceptor: keep promises in a dict or set")
    r.on_promise(3, good)
    must(r.leading, "promises from two different acceptors out of three are a majority")
    r.propose(cmd(1))
    must(1 in r.pending, "propose() must register the slot in self.pending")
    stale = {"t": "accepted", "b": (0, 2), "slot": 1}
    r.on_accepted(2, stale)
    r.on_accepted(3, stale)
    must(1 in r.pending, "accepted replies for an OLD ballot must not count towards this ballot's quorum")
    ok = {"t": "accepted", "b": r.ballot, "slot": 1}
    r.on_accepted(2, ok)
    r.on_accepted(2, ok)
    must(1 in r.pending, "the same acceptor's accepted twice (a duplicated message) must count once")
    sim.observer.chosen[1] = (mod.vkey(cmd(1)), cmd(1))      # pretend a majority really accepted it
    r.on_accepted(3, ok)
    must(1 not in r.pending and r.chosen.get(1) == cmd(1), "two different acceptors accepted slot 1: it is chosen, call self.commit")


def m4_seed(seed):
    n = 5
    wild = seed % 3 == 0                              # every third run: long delays and many duplicates, so old messages arrive very late
    sim, ids = build_cluster(seed, n, drop=0.1, dup=0.2 if wild else 0.05, min_delay=1, max_delay=30 if wild else 8)
    rng = random.Random(seed * 77 + 3)
    submitted = []
    counter = [0]
    CHAOS_END, FINAL = 1500, 2200

    def submit():
        if sim.now < CHAOS_END:
            ld = leader_of(sim, ids)
            if ld is not None and rng.random() < 0.7:
                kill = rng.random() < 0.2 and sum(not sim.up[i] for i in ids) < 2
                for _ in range(rng.randint(4, 8) if kill else rng.randint(1, 3)):   # bursts: pipelined slots
                    counter[0] += 1
                    c = cmd(counter[0])
                    sim.observer.propose(c)
                    submitted.append(c)
                    ld.propose(c)
                if kill:                                    # the leader dies with accepts still in flight: gaps
                    sim.schedule(sim.now + rng.randint(1, 9), lambda v=ld.id: sim.crash(v))
                    sim.schedule(sim.now + rng.randint(60, 300), lambda v=ld.id: sim.restart(v))
            sim.schedule(sim.now + 10, submit)
    sim.schedule(5, submit)

    def nemesis():
        if sim.now < CHAOS_END:
            down = [i for i in ids if not sim.up[i]]
            if len(down) < 2:
                ld = leader_of(sim, ids)
                victim = ld.id if (ld and rng.random() < 0.6) else rng.choice([i for i in ids if sim.up[i]])
                sim.crash(victim)
                sim.schedule(sim.now + rng.randint(40, 300), lambda v=victim: sim.restart(v))
            sim.schedule(sim.now + rng.randint(80, 260), nemesis)
    sim.schedule(rng.randint(100, 300), nemesis)
    sim.run(CHAOS_END)
    no_violations(sim)
    for i in ids:
        sim.restart(i)                                       # heal everything
    sim.run(FINAL)
    no_violations(sim)
    final = []
    for k in range(5):                                        # progress after healing: these must all get through
        counter[0] += 1
        c = cmd(counter[0])
        sim.observer.propose(c)
        final.append(c)
    for k, c in enumerate(final):
        def push(c=c):
            ld = leader_of(sim, ids)
            if ld is not None:
                ld.propose(c)
        sim.schedule(FINAL + 10 + 30 * k, push)
    sim.run(FINAL + 1500)
    no_violations(sim)
    obs = sim.observer
    top = max(obs.chosen, default=0)
    holes = [s for s in range(1, top + 1) if s not in obs.chosen]
    must(not holes, f"slots {holes[:5]} below the highest chosen slot ({top}) were never chosen: gaps must be filled with no-ops")
    seen = {}
    for s, (k, v) in sorted(obs.chosen.items()):
        if v != NOOP:
            if k in seen:
                raise Fail(f"command {v['id']} appears in two slots ({seen[k]} and {s}): recovery must not duplicate commands")
            seen[k] = s
    for (s, k) in obs.acked:
        must(obs.chosen.get(s, (None,))[0] == k, f"a committed value in slot {s} is not what the log contains")
    for c in final:
        must(mod.vkey(c) in seen, f"after the cluster healed, command {c['id']} never got chosen: the new leader is not making progress")
    for i in ids:
        r = sim.nodes[i]
        must(r.chosen == {s: v for s, (k, v) in obs.chosen.items()},
             f"after healing, replica {i} knows slots {sorted(r.chosen)} but the log has slots 1..{top}: catch-up is stuck")
    return obs.noops, len(obs.acked)


def m4():
    m4_unit()
    m4_votes()
    noops = acked = 0
    for seed in range(SEEDS_M4):
        try:
            n, a = m4_seed(seed)
        except Fail as e:
            e.seed = seed
            raise
        noops += n
        acked += a
    return f"{SEEDS_M4} runs with 5 replicas, 10% loss and leaders crashed at random: one log, no gaps, no lost commits ({acked} commits, {noops} gaps filled with no-ops)"


# -------------------------------------------------------------------------------------
# Milestone 5: the replicated key-value store
# -------------------------------------------------------------------------------------
def c(client, seq, op, key=None, arg=None):
    return {"client": client, "seq": seq, "op": op, "key": key, "arg": arg}


def m5_unit():
    kv = mod.KVStore()
    must(kv.apply(c(1, 1, "incr", "n", 1)) == 1, "incr on a missing key starts from 0 and returns the new value")
    must(kv.apply(c(1, 1, "incr", "n", 1)) == 1 and kv.data["n"] == 1,
         "the same (client, seq) applied twice (a retry chosen in a second slot) must return the first result and NOT run again")
    must(kv.apply(c(1, 2, "incr", "n", 1)) == 2, "the next seq is a new request and must execute")
    must(kv.apply(c(1, 1, "incr", "n", 1)) is None and kv.data["n"] == 2,
         "a request older than the client's last executed seq must be ignored (return None) and must not run")
    must(kv.apply(c(2, 1, "incr", "n", 5)) == 7, "another client has its own session: seq 1 from client 2 is new")
    must(kv.apply(NOOP) is None and kv.data["n"] == 7, "a no-op returns None and changes nothing")
    must(kv.apply(c(1, 3, "put", "k", "v")) == "ok" and kv.apply(c(1, 4, "get", "k")) == "v", "put then get")
    # apply_ready: strictly in slot order, no gaps, no-ops skipped
    sim = new_sim(1, auto_elect=False)
    sim.observer.n_acceptors = 3
    r = mod.Replica(1, sim, {}, [1, 2, 3])
    cmds = {1: c(1, 1, "append", "log", "a"), 2: c(1, 2, "append", "log", "b"), 3: NOOP, 4: c(1, 3, "append", "log", "c")}

    def learn(slot):
        sim.observer.chosen[slot] = (mod.vkey(cmds[slot]), cmds[slot])
        r.record_chosen(slot, cmds[slot])
    learn(2)
    must(r.applied == 0 and r.kv.data == {}, "slot 2 is known but slot 1 is not: nothing may be applied yet (slots apply in order)")
    learn(4)
    must(r.applied == 0, "slots 2 and 4 are known, slot 1 is not: still nothing may be applied")
    learn(1)
    must(r.applied == 2 and r.kv.data == {"log": "ab"}, f"slot 1 arrived: slots 1 and 2 must now be applied in order (log == 'ab'); "
         f"applied={r.applied}, data={r.kv.data}")
    learn(3)
    must(r.applied == 4 and r.kv.data == {"log": "abc"}, f"slot 3 is a no-op: it must be skipped, then slot 4 applied; "
         f"applied={r.applied}, data={r.kv.data}")


def client_ops(cid):
    ops = []
    for k in range(1, 4):
        ops += [("incr", "n", 1), ("append", "log", f"{cid}.{k};"), ("put", f"k{cid}", k), ("get", f"k{cid}", None)]
    return ops


def m5_seed(seed):
    n = 5
    wild = seed % 3 == 0
    sim, ids = build_cluster(seed, n, drop=0.1, dup=0.2 if wild else 0.05, min_delay=1, max_delay=30 if wild else 8)
    clients = []
    for j, cid in enumerate((101, 102, 103)):
        clients.append(sim.add(cid, lambda nid, s, d, cid=cid, j=j: mod.Client(nid, s, d, ids, client_ops(cid), start_at=50 + 70 * j)))
    rng = random.Random(seed * 91 + 11)
    CHAOS_END = 1500

    def nemesis():
        if sim.now < CHAOS_END:
            down = [i for i in ids if not sim.up[i]]
            if len(down) < 2:
                ld = leader_of(sim, ids)
                victim = ld.id if (ld and rng.random() < 0.6) else rng.choice([i for i in ids if sim.up[i]])
                sim.crash(victim)
                sim.schedule(sim.now + rng.randint(40, 300), lambda v=victim: sim.restart(v))
            sim.schedule(sim.now + rng.randint(80, 260), nemesis)
    sim.schedule(rng.randint(60, 200), nemesis)
    sim.run(CHAOS_END)
    no_violations(sim)
    for i in ids:
        sim.restart(i)
    sim.run(9000, stop=lambda: all(cl.done_at is not None for cl in clients))
    no_violations(sim)
    for cl in clients:
        must(cl.done_at is not None, f"client {cl.id} finished only {cl.index}/{len(cl.ops)} operations: the cluster stopped making progress "
             "(or an applied command never produced a reply)")
    sim.run(sim.now + 600)                                     # let the followers catch up
    no_violations(sim)
    reps = [sim.nodes[i] for i in ids]
    for r in reps[1:]:
        must(r.applied == reps[0].applied, f"replica {r.id} applied {r.applied} slots but replica {reps[0].id} applied {reps[0].applied}")
        must(r.kv.data == reps[0].kv.data, f"replicas disagree: replica {r.id} has {r.kv.data}, replica {reps[0].id} has {reps[0].kv.data}")
        must(r.kv.sessions == reps[0].kv.sessions, f"replica {r.id} and replica {reps[0].id} hold different client sessions")
    data = reps[0].kv.data
    total_incr = sum(1 for cl in clients for op in cl.ops if op[0] == "incr")
    must(data.get("n") == total_incr, f"EXACTLY-ONCE broken: clients issued {total_incr} increments, the counter is {data.get('n')}. "
         "A retry that was chosen twice must be applied once")
    got = sorted(res for cl in clients for op, res in zip(cl.ops, cl.results) if op[0] == "incr")
    must(got == list(range(1, total_incr + 1)), f"the increments' replies should be exactly 1..{total_incr}, got {got}")
    for cl in clients:
        tokens = [t for t in data.get("log", "").split(";") if t.startswith(f"{cl.id}.")]
        must(tokens == [f"{cl.id}.{k}" for k in (1, 2, 3)], f"client {cl.id}'s appends should each appear once, in order; found {tokens}")
        gets = [res for op, res in zip(cl.ops, cl.results) if op[0] == "get"]
        must(gets == [1, 2, 3], f"client {cl.id} reads its own key right after writing it: expected [1, 2, 3], got {gets}")
    return sim.observer.noops


def m5():
    m5_unit()
    noops = 0
    for seed in range(SEEDS_M5):
        try:
            noops += m5_seed(seed)
        except Fail as e:
            e.seed = seed
            raise
    return f"{SEEDS_M5} runs: 3 clients retrying through leader crashes and 10% loss; all replicas identical, every request applied exactly once"


# -------------------------------------------------------------------------------------
# driver
# -------------------------------------------------------------------------------------
MILESTONES = [
    ("Milestone 1: the acceptor's two rules", m1),
    ("Milestone 2: single-decree Paxos is safe", m2),
    ("Milestone 3: duelling proposers, randomized backoff", m3),
    ("Milestone 4: Multi-Paxos, recovery and no-op gaps", m4),
    ("Milestone 5: a replicated key-value store, exactly once", m5),
]


def _alarm(signum, frame):
    raise Fail("this milestone took more than 50 seconds: is something looping forever?")


def where(exc):
    for fr in reversed(traceback.extract_tb(exc.__traceback__)):
        if os.path.basename(fr.filename) == target + ".py":
            return f"{os.path.basename(fr.filename)}:{fr.lineno}, in {fr.name}"
    return None


def show_failure(name, e, replay_no):
    seed = getattr(e, "seed", None)
    print(f"  ✘ {name}")
    print(f"      {e}")
    if seed is not None:
        print(f"      failing seed: {seed}   (replay: python3 check.py {target} replay {replay_no} {seed})")
    sim = CUR["sim"]
    if sim is not None and sim.trace:
        print("      trace (most recent last):")
        for line in sim.format_trace(25):
            print("        " + line)


def run_one(i, name, fn):
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(50)
    CUR["sim"] = None
    try:
        note = fn()
        print(f"  ✔ {name}")
        if note:
            print(f"      {note}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except Fail as e:
        show_failure(name, e, i)
        results.append(False)
    except Exception as e:
        loc = where(e)
        print(f"  ✘ {name}")
        print(f"      your code raised {type(e).__name__}: {e}" + (f"  (at {loc})" if loc else ""))
        sim = CUR["sim"]
        if sim is not None and sim.trace:
            print("      trace (most recent last):")
            for line in sim.format_trace(15):
                print("        " + line)
        results.append(False)
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)


def do_replay(m, seed):
    fns = {2: m2_seed, 3: m3_seed, 4: m4_seed, 5: m5_seed}
    if m not in fns:
        sys.exit("replay works for milestones 2 to 5 (milestone 1 has no seeds)")
    print(f"Replaying milestone {m}, seed {seed} against {target}.py\n")
    try:
        fns[m](seed)
        print("no failure on this seed")
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
    sim = CUR["sim"]
    if sim:
        print("\nlast events:")
        for line in sim.format_trace(250):
            print("  " + line)


if replay:
    do_replay(*replay)
    sys.exit(0)

print(f"Lab 4 checks against {target}.py\n")
for i, (name, fn) in enumerate(MILESTONES, 1):
    run_one(i, name, fn)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
