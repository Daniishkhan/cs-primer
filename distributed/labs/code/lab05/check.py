"""Self-check for Lab 5: Two-Phase Commit & Recovery.

    python3 check.py                       # checks your starter.py
    python3 check.py solution              # checks the reference solution
    python3 check.py solution --seed 17    # replay ONE chaos seed with a readable trace
    python3 check.py solution --seed 17 --replicated
    python3 check.py solution --seed 17 --tx T5   # show only the messages and log records of T5

Everything is simulated in one process with seeded randomness: no sockets, no threads, no real
time.  The same seed always gives the same run, so a failing seed can be replayed exactly.
The whole check takes well under a minute.
"""
import importlib
import os
import random
import signal
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

args = sys.argv[1:]
replay_seed = int(args[args.index("--seed") + 1]) if "--seed" in args else None
replay_repl = "--replicated" in args
replay_tx = args[args.index("--tx") + 1] if "--tx" in args else None
pos = [a for i, a in enumerate(args) if not a.startswith("--") and not (i and args[i - 1] in ("--seed", "--tx"))]
target = pos[0] if pos else "starter"
if target not in ("starter", "solution"):
    sys.exit("usage: python3 check.py [starter|solution] [--seed N] [--replicated] [--tx T3]")
mod = importlib.import_module(target)

PARTS = ["P1", "P2", "P3"]
CHAOS_SEEDS = 300
REPL_SEEDS = 150
results, notes = [], []


class Violation(AssertionError):
    def __init__(self, msg, tx=None):
        super().__init__(msg)
        self.tx = tx


# ---------------------------------------------------------------------------------------------
# Scripted nodes: stand-ins for a coordinator or participants, so each milestone is tested alone
# ---------------------------------------------------------------------------------------------
class Probe(mod.Node):
    """Records everything it receives.  Used as a fake coordinator for participant tests."""

    def init_volatile(self):
        self.inbox = []

    def on_message(self, src, msg):
        self.inbox.append((self.now, src, msg))

    def of(self, tx, kind=None):
        return [(t, m) for t, s, m in self.inbox if m.get("tx") == tx and (kind is None or m["type"] == kind)]


class Script(Probe):
    """A fake participant with a fixed behaviour."""

    def __init__(self, sim, name, cfg=None, vote="YES", ignore_commits=0, silent=False, double_vote=False):
        super().__init__(sim, name, cfg)
        self.vote, self.ignore, self.silent, self.double = vote, ignore_commits, silent, double_vote
        self.commits = 0

    def on_message(self, src, msg):
        super().on_message(src, msg)
        tx = msg.get("tx")
        if msg["type"] == "PREPARE" and not self.silent:
            for _ in range(2 if self.double else 1):
                self.send(src, {"type": "VOTE", "tx": tx, "vote": self.vote})
        elif msg["type"] == "COMMIT":
            self.commits += 1
            if self.commits > self.ignore:
                self.send(src, {"type": "ACK", "tx": tx})
        elif msg["type"] == "ABORT":
            self.send(src, {"type": "ACK", "tx": tx})


def tell(sim, t, dst, msg, src="C"):
    sim.at(t, lambda: sim.inject(0.0, dst, msg, src=src))


def tindex(sim, pred):
    for i, e in enumerate(sim.trace):
        if pred(e):
            return i
    return None


# ---------------------------------------------------------------------------------------------
# Verification of a finished run
# ---------------------------------------------------------------------------------------------
def coord_commits(coord):
    return {r[1] for r in coord.log if r[0] == "COMMIT"}


def coord_ended(coord):
    return {r[1] for r in coord.log if r[0] == "END"}


def committed_anywhere(sim, tx):
    return any(mod.outcome(sim.nodes[p].log, tx["id"]) == "COMMIT" for p in tx["writes"])


def verify(sim, coord, ps, store, txs, replicated=False):
    """Atomicity, validity, and eventual resolution.  Raises Violation."""
    by = {p.name: p for p in ps}
    cc, ce = coord_commits(coord), coord_ended(coord)
    for n in list(by) + [coord.name]:
        if not sim.nodes[n].up:
            raise Violation(f"{n} is still down at the end of the run (restarts must work)")
    for tx in txs:
        t = tx["id"]
        dec = {p: mod.outcome(by[p].log, t) for p in tx["writes"]}
        prep = {p: mod.prepared_writes(by[p].log, t) is not None for p in tx["writes"]}
        kinds = {d for d in dec.values() if d}
        if len(kinds) > 1:
            raise Violation(f"ATOMICITY VIOLATED: {t} was decided differently: {dec}", t)
        for p in tx["writes"]:
            if prep[p] and dec[p] is None:
                raise Violation(f"UNRESOLVED: {p} is still in doubt about {t} (it holds its locks for ever)", t)
        if "COMMIT" in kinds:
            if not all(prep.values()):
                raise Violation(f"{t} committed although not every participant prepared: prepared={prep}", t)
            if tx["bad"]:
                raise Violation(f"{t} committed although {sorted(tx['bad'])} had to vote NO", t)
            if set(dec.values()) != {"COMMIT"}:
                raise Violation(f"{t} committed at some participants but not all: {dec}", t)
            if not replicated and t not in cc:
                raise Violation(f"{t} committed at participants but the coordinator has no COMMIT record", t)
        if t in cc:
            if kinds != {"COMMIT"}:
                raise Violation(f"coordinator logged COMMIT for {t} but participants say {dec}", t)
            if t not in ce:
                raise Violation(f"{t} was committed but the coordinator never wrote END (acks never completed)", t)
        if store is not None:
            st = {r[1]: r[2] for r in store.log}
            if "COMMIT" in kinds and st.get(t) != "COMMIT":
                raise Violation(f"{t} committed but the decision store says {st.get(t)}", t)
            if "ABORT" in kinds and st.get(t) == "COMMIT":
                raise Violation(f"{t} aborted at a participant but the decision store says COMMIT", t)
    for p in ps:
        if len(p.locks):
            raise Violation(f"{p.name} still holds locks at the end: {dict(p.locks.held)}")
        data, wo = {}, {}
        for rec in p.log:
            if rec[0] == "PREPARED":
                wo[rec[1]] = rec[2]
            elif rec[0] == "COMMIT":
                data.update(wo[rec[1]])
        if data != p.data:
            raise Violation(f"{p.name}: live data {p.data} differs from what its log implies {data}")


def gen_txs(seed, n=10, span=250.0):
    rng = random.Random(seed * 7919 + 1)
    txs = []
    for i in range(n):
        ps = sorted(rng.sample(PARTS, rng.randint(2, 3)))
        writes = {p: {f"k{rng.randrange(6)}": f"t{i}"} for p in ps}
        bad = set()
        if rng.random() < 0.12:
            q = rng.choice(ps)
            writes[q] = {"k0": "BAD"}
            bad = {q}
        txs.append({"id": f"T{i}", "writes": writes, "bad": bad, "at": rng.uniform(0, span)})
    return txs


def run_chaos(seed, replicated=False):
    """One seeded run with trouble everywhere: drops, duplicates, reordering, random crashes at
    every crash point, sometimes a long coordinator outage.  Returns (sim, error-or-None, info)."""
    sim = mod.Sim(seed, drop=0.06, dup=0.05)
    coord, ps, store = mod.make_cluster(sim, 3, replicated)
    rng = random.Random(seed * 31 + 7)
    sim.chaos(prob=0.02, until=300.0, max_crashes=10)
    if rng.random() < 0.4:
        sim.crash_at_time(rng.uniform(5, 100), "C", rng.uniform(50, 250))
    txs = gen_txs(seed)
    for tx in txs:
        mod.begin(sim, tx["id"], tx["writes"], at=tx["at"])
    err = None
    try:
        sim.run(until=4000.0)
        verify(sim, coord, ps, store, txs, replicated)
    except AssertionError as e:                # a Violation, or an assert inside your own code
        err = e if isinstance(e, Violation) else Violation(f"assertion in your code: {e}")
    return sim, err, {"crashes": sim.crashes, "txs": txs,
                      "commits": sum(1 for t in txs if committed_anywhere(sim, t))}


def trace_lines(sim, tx=None, limit=60):
    out = []
    for e in sim.trace:
        kind, t = e[0], e[1]
        if kind in ("crash", "restart"):
            out.append(f"    t={t:7.1f}  {e[2]:<3} {kind.upper()}" + (f" at {e[3]}" if kind == "crash" else ""))
            continue
        body = e[-1]
        if tx is not None and tx not in repr(body):
            continue
        if kind == "log":
            out.append(f"    t={t:7.1f}  {e[2]:<3} LOG {body}")
        elif kind == "send":
            out.append(f"    t={t:7.1f}  {e[2]:<3} -> {e[3]:<3} {body['type']} {body.get('vote', body.get('value', ''))}")
        elif kind == "lost":
            out.append(f"    t={t:7.1f}      (lost: {e[2]} -> {e[3]} {body['type']})")
        elif kind == "down":
            out.append(f"    t={t:7.1f}      (dropped, {e[2]} is down: {body['type']} from {e[3]})")
    return out[-limit:]


# ---------------------------------------------------------------------------------------------
# Milestone 1: participants
# ---------------------------------------------------------------------------------------------
def m1_participant():
    sim = mod.Sim(1)
    cfg = {"coord": "C", "parts": ["P1"], "store": None}
    probe = Probe(sim, "C", cfg)
    p = mod.Participant(sim, "P1", cfg)
    prep = lambda tx, w: {"type": "PREPARE", "tx": tx, "writes": w}
    dec = lambda k, tx: {"type": k, "tx": tx}
    tell(sim, 1, "P1", prep("T1", {"x": 1}))
    tell(sim, 10, "P1", prep("T2", {"x": 2}))          # x is locked by T1
    tell(sim, 20, "P1", prep("T3", {"y": "BAD"}))      # a local constraint fails
    tell(sim, 30, "P1", prep("T4", {"z": 5}))
    tell(sim, 40, "P1", dec("COMMIT", "T1"))
    tell(sim, 50, "P1", prep("T5", {"x": 7}))          # free again
    tell(sim, 60, "P1", dec("ABORT", "T5"))
    tell(sim, 70, "P1", dec("COMMIT", "T1"))           # duplicate
    tell(sim, 80, "P1", prep("T4", {"z": 5}))          # duplicate
    sim.run(until=200)
    vote = lambda tx: [m["vote"] for _, m in probe.of(tx, "VOTE")]
    assert vote("T1") == ["YES"], f"T1 should get one YES vote, got {vote('T1')}"
    assert vote("T2") == ["NO"], f"T2 wants a key T1 holds; it should get NO, got {vote('T2')}"
    assert vote("T3") == ["NO"], f"a participant that cannot commit locally must vote NO, got {vote('T3')}"
    assert vote("T4") == ["YES", "YES"], f"T4: {vote('T4')} (a duplicate PREPARE must repeat YES)"
    assert vote("T5") == ["YES"], "after T1 committed, its lock on x must be gone (T5 should get YES)"
    recs = list(p.log)
    assert ("PREPARED", "T1", {"x": 1}) in recs, f"the log must hold ('PREPARED', 'T1', {{'x': 1}}); it holds {recs}"
    assert not any(r[0] == "PREPARED" and r[1] in ("T2", "T3") for r in recs), "a NO vote must not write PREPARED"
    i_log = tindex(sim, lambda e: e[0] == "log" and e[2] == "P1" and e[3][:2] == ("PREPARED", "T1"))
    i_vote = tindex(sim, lambda e: e[0] == "send" and e[2] == "P1" and e[4]["type"] == "VOTE" and e[4]["tx"] == "T1")
    assert i_log is not None and i_vote is not None and i_log < i_vote, \
        "write PREPARED to the log BEFORE sending the YES vote (the promise must be durable first)"
    assert ("COMMIT", "T1") in recs and ("ABORT", "T5") in recs, "decisions must be logged as ('COMMIT', tx) / ('ABORT', tx)"
    assert p.data == {"x": 1}, f"only committed writes may reach the data: expected {{'x': 1}}, got {p.data}"
    assert p.locks.holder("x") is None, "COMMIT/ABORT must release the locks"
    assert p.locks.holder("z") == "T4", "T4 is prepared and undecided: it must still hold z"
    acks = lambda tx: len(probe.of(tx, "ACK"))
    assert acks("T1") == 2 and acks("T5") == 1, f"every COMMIT/ABORT is acknowledged (even a duplicate): T1 {acks('T1')}, T5 {acks('T5')}"
    assert len([r for r in recs if r == ("COMMIT", "T1")]) == 1, "a duplicate COMMIT must not be logged twice"
    for pt in mod.P_POINTS:
        assert ("P1", pt) in sim.hits, f"your participant never reached crash point {pt!r}: call self.point({pt!r}) there"


# ---------------------------------------------------------------------------------------------
# Milestone 2: the coordinator
# ---------------------------------------------------------------------------------------------
def mini(scripts, seed=3):
    sim = mod.Sim(seed)
    cfg = {"coord": "C", "parts": list(scripts), "store": None}
    c = mod.Coordinator(sim, "C", cfg)
    ss = {n: Script(sim, n, cfg, **a) for n, a in scripts.items()}
    return sim, c, ss


def m2_coordinator():
    W = {"P1": {"x": 1}, "P2": {"x": 1}, "P3": {"x": 1}}
    # (a) everybody votes YES
    sim, c, ss = mini({n: {} for n in W})
    mod.begin(sim, "T1", W)
    sim.run(until=300)
    recs = list(c.log)
    assert recs == [("COMMIT", "T1", ["P1", "P2", "P3"]), ("END", "T1")], \
        f"coordinator log should be [('COMMIT','T1',['P1','P2','P3']), ('END','T1')], is {recs}"
    i_log = tindex(sim, lambda e: e[0] == "log" and e[3][0] == "COMMIT")
    i_send = tindex(sim, lambda e: e[0] == "send" and e[2] == "C" and e[4]["type"] == "COMMIT")
    assert i_log < i_send, "log COMMIT BEFORE sending it to anybody: that log record is the commit point"
    i_end = tindex(sim, lambda e: e[0] == "log" and e[3][0] == "END")
    last_ack = max(i for i, e in enumerate(sim.trace) if e[0] == "recv" and e[2] == "C" and e[4]["type"] == "ACK")
    assert i_end > last_ack, "write END only after the LAST ack has arrived"
    for n, s in ss.items():
        pr = s.of("T1", "PREPARE")
        assert len(pr) == 1 and pr[0][1]["writes"] == {"x": 1}, f"{n} must get exactly one PREPARE carrying its own writes"
        assert s.of("T1", "COMMIT"), f"{n} never got COMMIT"
    # (b) one NO
    sim, c, ss = mini({"P1": {}, "P2": {"vote": "NO"}, "P3": {}})
    mod.begin(sim, "T1", W)
    sim.run(until=300)
    assert not any(e[0] == "send" and e[4]["type"] == "COMMIT" for e in sim.trace), "a single NO vote must mean nobody is told COMMIT"
    assert ss["P1"].of("T1", "ABORT") and ss["P3"].of("T1", "ABORT"), "the participants that voted YES must be told ABORT"
    assert len(c.log) == 0, f"presumed abort: an abort needs no log record at the coordinator, but it logged {list(c.log)}"
    # (c) a participant stays silent: silence counts as NO after the timeout
    sim, c, ss = mini({"P1": {}, "P2": {"silent": True}, "P3": {}})
    mod.begin(sim, "T1", W)
    sim.run(until=300)
    ab = ss["P1"].of("T1", "ABORT")
    assert ab, "a missing vote must lead to ABORT after a timeout"
    assert ab[0][0] >= 20, f"ABORT came at t={ab[0][0]:.1f}: wait for the vote timeout before giving up on a slow participant"
    assert len(c.log) == 0 and not ss["P3"].of("T1", "COMMIT")
    # (d) lost acks: resend until acked
    sim, c, ss = mini({"P1": {}, "P2": {"ignore_commits": 3}, "P3": {}})
    mod.begin(sim, "T1", W)
    sim.run(until=300)
    assert ss["P2"].commits >= 4, f"P2 ignores 3 COMMITs; the coordinator must keep resending (it sent {ss['P2'].commits})"
    assert list(c.log)[-1] == ("END", "T1"), "once the late ack arrives the coordinator must write END"
    # (e) a participant that never acks: keep resending, at a sane rate, and never write END
    sim, c, ss = mini({"P1": {}, "P2": {"ignore_commits": 10 ** 9}, "P3": {}})
    mod.begin(sim, "T1", W)
    sim.run(until=500)
    n = ss["P2"].commits
    assert 5 <= n <= 60, f"expected a resend roughly every {mod.RESEND_EVERY:g} time units over 500 (5 to 60 copies), saw {n}"
    assert ("END", "T1") not in list(c.log), "END before every ack arrived"
    assert ss["P1"].commits <= 3, "once P1 acked, stop resending to it"
    # (f) duplicated votes, and a NO among them
    sim, c, ss = mini({"P1": {"double_vote": True}, "P2": {"double_vote": True}, "P3": {"vote": "NO"}})
    mod.begin(sim, "T1", W)
    sim.run(until=300)
    assert len(c.log) == 0, "duplicate votes plus one NO must still be an abort with nothing logged"
    sim, c, ss = mini({"P1": {"double_vote": True}, "P2": {"double_vote": True}, "P3": {"double_vote": True}})
    mod.begin(sim, "T1", W)
    sim.run(until=300)
    assert [r[0] for r in c.log] == ["COMMIT", "END"], f"duplicate votes must not cause a second decision: {list(c.log)}"
    for pt in mod.C_POINTS:
        assert ("C", pt) in sim.hits, f"your coordinator never reached crash point {pt!r}: call self.point({pt!r}) there"


# ---------------------------------------------------------------------------------------------
# Milestone 3: recovery at every crash point
# ---------------------------------------------------------------------------------------------
EXPECT_P = {"p:before_prepare_log": "ABORT", "p:after_prepare_log": "ABORT", "p:after_vote_sent": "COMMIT",
            "p:before_decision_log": "COMMIT", "p:after_decision_log": "COMMIT"}
EXPECT_C = {"c:after_prepare_sent": "ABORT", "c:after_votes": "ABORT", "c:after_decision_log": "COMMIT",
            "c:mid_send": "COMMIT", "c:before_end": "COMMIT", "c:after_store_decide": "COMMIT"}


def one_crash(node, point, restart_after, replicated=False):
    sim = mod.Sim(5)
    coord, ps, store = mod.make_cluster(sim, 3, replicated)
    sim.crash_at_point(node, point, 1, restart_after)
    W1 = {p: {"x": "a"} for p in PARTS}
    W2 = {p: {"x": "b"} for p in PARTS}                 # same keys: stale locks would make T2 abort
    mod.begin(sim, "T1", W1, at=0.0)
    mod.begin(sim, "T2", W2, at=900.0)
    txs = [{"id": "T1", "writes": W1, "bad": set()}, {"id": "T2", "writes": W2, "bad": set()}]
    sim.error = None
    try:
        sim.run(until=3000)
    except AssertionError as e:
        sim.error = Violation(f"assertion in your code: {e}")
    return sim, coord, ps, store, txs


def enumerate_crashes(replicated):
    cases = [(p, pt, EXPECT_P[pt]) for p in PARTS for pt in mod.P_POINTS]
    pts = mod.C_POINTS + (mod.CR_POINTS if replicated else [])
    cases += [("C", pt, EXPECT_C[pt]) for pt in pts]
    bad = []
    for node, point, want in cases:
        for after in (8.0, 150.0):
            sim, coord, ps, store, txs = one_crash(node, point, after, replicated)
            tag = f"{node} crashes at {point}, back after {after:g}"
            try:
                if sim.error:
                    raise sim.error
                if (node, point) not in sim.hits:
                    raise Violation(f"never reached the crash point {point!r} on {node}")
                verify(sim, coord, ps, store, txs, replicated)
                got = {mod.outcome(p.log, "T1") for p in ps}
                if want == "COMMIT" and got != {"COMMIT"}:
                    raise Violation(f"T1 should commit everywhere, ended as {sorted(map(str, got))}", "T1")
                if want == "ABORT" and "COMMIT" in got:
                    raise Violation(f"T1 should have aborted, ended as {sorted(map(str, got))}", "T1")
                got2 = {mod.outcome(p.log, "T2") for p in ps}
                if got2 != {"COMMIT"}:
                    raise Violation(f"T2 (later, same keys) should commit: locks left behind? {sorted(map(str, got2))}", "T2")
            except Violation as e:
                bad.append((tag, e, sim))
    if bad:
        tag, e, sim = bad[0]
        notes.append(f"    first failing case: {tag}")
        notes.extend(trace_lines(sim, e.tx, 30))
        raise AssertionError(f"{len(bad)} of {2 * len(cases)} crash cases fail, e.g. [{tag}]: {e}")
    notes.append(f"    {2 * len(cases)} crash cases ({len(cases)} places x short and long outage): all atomic, all resolved, locks freed")


def m3_recovery():
    # (a) inquiries to the coordinator
    sim = mod.Sim(4)
    cfg = {"coord": "C", "parts": PARTS, "store": None}
    mod.Coordinator(sim, "C", cfg)
    ss = {"P1": Script(sim, "P1", cfg), "P2": Script(sim, "P2", cfg), "P3": Script(sim, "P3", cfg, silent=True)}
    W = {p: {"x": 1} for p in PARTS}
    mod.begin(sim, "T1", W, at=0)                       # P3 never votes: T1 stays in phase 1 for a while
    tell(sim, 10, "C", {"type": "INQUIRE", "tx": "T1"}, src="P1")
    tell(sim, 10, "C", {"type": "INQUIRE", "tx": "NEVER"}, src="P1")
    sim.run(until=300)
    early = [t for t, m in ss["P1"].of("T1") if m["type"] in ("COMMIT", "ABORT") and t < 28]
    assert not early, "while the coordinator is still collecting votes it must NOT answer INQUIRE (it may yet commit): stay silent"
    assert [m["type"] for _, m in ss["P1"].of("NEVER")] == ["ABORT"], "an unknown transaction must be answered ABORT (presumed abort)"
    sim, c, ss2 = mini({n: {} for n in PARTS})
    mod.begin(sim, "T1", W, at=0)
    tell(sim, 400, "C", {"type": "INQUIRE", "tx": "T1"}, src="P1")
    sim.run(until=600)
    late = [m["type"] for t, m in ss2["P1"].of("T1") if t > 399]
    assert late == ["COMMIT"], f"even after END, an inquiry about a committed transaction must be answered COMMIT, got {late}"
    # (b) locks survive: a conflicting PREPARE must get NO while in doubt, also after a participant restart
    sim = mod.Sim(6)
    coord, ps, _ = mod.make_cluster(sim, 3)
    probe = Probe(sim, "probe")
    sim.crash_at_point("C", "c:after_votes", 1, 300.0)
    sim.crash_at_point("P2", "p:after_vote_sent", 1, 30.0)
    W1 = {p: {"x": "a"} for p in PARTS}
    mod.begin(sim, "T1", W1)
    for p in PARTS:
        tell(sim, 100, p, {"type": "PREPARE", "tx": "X", "writes": {"x": "zzz"}}, src="probe")
    sim.run(until=120)
    votes = {s: m["vote"] for t, s, m in probe.inbox if m["type"] == "VOTE"}
    assert votes == {"P1": "NO", "P2": "NO", "P3": "NO"}, \
        f"at t=100 the coordinator is down and T1 is in doubt everywhere: every participant (P2 was restarted) must still hold its lock and say NO, got {votes}"
    sim.run(until=3000)
    verify(sim, coord, ps, None, [{"id": "T1", "writes": W1, "bad": set()}])
    # (c) every crash point, both kinds of node, short and long outages
    enumerate_crashes(False)


# ---------------------------------------------------------------------------------------------
# Milestone 4: atomicity under chaos
# ---------------------------------------------------------------------------------------------
def chaos_many(n, replicated, label):
    fails, commits, crashes, txs = [], 0, 0, 0
    for seed in range(1, n + 1):
        sim, err, info = run_chaos(seed, replicated)
        commits += info["commits"]
        crashes += info["crashes"]
        txs += len(info["txs"])
        if err is not None:
            fails.append((seed, err, sim))
    if fails:
        seeds = [s for s, _, _ in fails]
        s, e, sim = fails[0]
        more = " ..." if len(seeds) > 12 else ""
        flag = " --replicated" if replicated else ""
        notes.append(f"    failing seeds: {seeds[:12]}{more}   replay one: python3 check.py {target} --seed {s}{flag}")
        notes.append(f"    seed {s}: {e}")
        notes.extend(trace_lines(sim, e.tx, 30))
        raise AssertionError(f"{len(fails)} of {n} seeds broke an invariant: {e}")
    assert txs * 0.2 < commits < txs * 0.9, \
        f"only {commits} of {txs} transactions committed: the runs are vacuous (is everything aborting?)"
    notes.append(f"    {label}: {n} seeds, {txs} transactions ({commits} committed), {crashes} injected crashes: all atomic, all resolved")


def m4_atomicity():
    chaos_many(CHAOS_SEEDS, False, "baseline 2PC")


# ---------------------------------------------------------------------------------------------
# Milestone 5: the blocking window, and shrinking it
# ---------------------------------------------------------------------------------------------
def windows(ps, tx="T1"):
    out = []
    for p in ps:
        t0 = p.log.time_of("PREPARED", tx)
        t1 = p.log.time_of("COMMIT", tx) or p.log.time_of("ABORT", tx)
        out.append(None if t0 is None else (t1 - t0 if t1 is not None else float("inf")))
    return out


def blocking(point, down, replicated):
    sim = mod.Sim(2)
    coord, ps, store = mod.make_cluster(sim, 3, replicated)
    sim.crash_at_point("C", point, 1, down)
    W = {p: {"x": 1} for p in PARTS}
    mod.begin(sim, "T1", W)
    sim.run(until=down * 4 + 500)
    verify(sim, coord, ps, store, [{"id": "T1", "writes": W, "bad": set()}], replicated)
    return windows(ps), {mod.outcome(p.log, "T1") for p in ps}


def m5_blocking():
    DOWN = 300.0
    rows = []
    for point, label in (("c:after_votes", "coordinator dies before it decides"),
                         ("c:after_decision_log", "coordinator dies right after logging COMMIT")):
        base, bo = blocking(point, DOWN, False)
        repl, ro = blocking(point, DOWN, True)
        rows.append((label, max(base), max(repl)))
        assert bo == ro and len(bo) == 1, f"the two variants must reach the same outcome here: {bo} vs {ro}"
        assert min(base) >= DOWN * 0.9, f"baseline: with the coordinator down for {DOWN:g}, in-doubt participants should wait about that long, saw {base}"
        bound = mod.STORE_WAIT + mod.INQUIRE_EVERY + 25
        assert max(repl) <= bound, \
            f"replicated: every in-doubt participant should resolve within about {bound:g} time units ({mod.STORE_WAIT:g} of patience, a poll, a round trip), saw {repl}"
        assert max(repl) * 4 < min(base), f"the blocking window must shrink a lot: {max(base):.0f} -> {max(repl):.0f}"
    notes.append(f"    longest time an in-doubt participant held its locks, coordinator down for {DOWN:g} time units:")
    for label, b, r in rows:
        notes.append(f"      {label:<46} baseline {b:6.1f}   replicated {r:6.1f}")
    enumerate_crashes(True)
    chaos_many(REPL_SEEDS, True, "replicated decision")


# ---------------------------------------------------------------------------------------------
MILESTONES = [
    ("Milestone 1: participant with a write-ahead log (prepare, vote, commit, abort)", m1_participant),
    ("Milestone 2: coordinator: log the decision, resend until acked, then END", m2_coordinator),
    ("Milestone 3: recovery at every crash point; in-doubt participants ask and keep their locks", m3_recovery),
    ("Milestone 4: atomicity and liveness over seeded runs with random crashes", m4_atomicity),
    ("Milestone 5: measure the blocking window, then shrink it with a replicated decision", m5_blocking),
]


def _alarm(signum, frame):
    raise AssertionError("this milestone took more than 55 seconds: is something looping, or are timers never stopping?")


def run_milestone(name, fn):
    del notes[:]
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(55)
    try:
        fn()
        print(f"  ✔ {name}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
        del notes[:]
    except mod.Crash:
        print(f"  ✘ {name}: a simulated Crash escaped (only self.point() may raise it, and the simulator catches it)")
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


def replay():
    sim, err, info = run_chaos(replay_seed, replay_repl)
    print(f"seed {replay_seed} ({'replicated' if replay_repl else 'baseline'}): {info['crashes']} crashes injected, "
          f"{info['commits']} of {len(info['txs'])} transactions committed")
    for tx in info["txs"]:
        decs = {p: mod.outcome(sim.nodes[p].log, tx["id"]) for p in tx["writes"]}
        print(f"  {tx['id']}: {decs}")
    print("verdict:", "OK" if err is None else f"FAILED: {err}")
    focus = replay_tx or (err.tx if err is not None else None)
    print("trace" + (f" for {focus} (crashes and restarts always shown)" if focus else " (everything; use --tx T5 to filter)") + ":")
    for line in trace_lines(sim, focus, 80):
        print(line)


if __name__ == "__main__":
    if replay_seed is not None:
        try:
            replay()
        except NotImplementedError as e:
            print(f"not implemented yet ({e})")
        sys.exit(0)
    print(f"Lab 5 checks against {target}.py\n")
    for name, fn in MILESTONES:
        run_milestone(name, fn)
    ok = sum(results)
    print(f"\n{ok}/{len(MILESTONES)} milestones passing")
    sys.exit(0 if ok == len(MILESTONES) else 1)
