"""Self-check for Lab 1: Gossip & Failure Detection.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 17    # milestone 4, replaying ONLY seed 17

Everything is simulated in one process with seeded randomness, so every run is
identical. Each milestone runs many seeds; when one fails, the message names the
seed and shows a short trace so you can replay it with the third form above.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
Sim, ROUND, HB_PERIOD, PERIOD = mod.Sim, mod.ROUND, mod.HB_PERIOD, mod.PERIOD
results = []


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def trace(sim, subject=None, limit=10):
    rows = [e for e in sim.log if subject is None or e[3] == subject][:limit]
    return "; ".join(f"t={t}: node {o} marks node {s} {k}" for t, k, o, s in rows) or "(no events)"


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


# =============================================================================
# Milestone 1: gossip
# =============================================================================
def run_gossip(n, seed, fanout=1, loss=0.0, crash=0):
    sim = Sim(seed, n, lambda s, i, p: mod.GossipNode(s, i, p, fanout=fanout, origin=(i == 0)), loss=loss)
    dead = random.Random(seed + 99).sample(range(1, n), crash) if crash else []
    for c in dead:
        sim.crash(c)
    live = [x for x in sim.nodes if sim.alive[x.id]]
    for rnd in range(1, 301):
        sim.run(rnd * ROUND)
        if all(x.informed for x in live):
            return max(x.informed_at for x in live) // ROUND, sim
    return None, sim


def m1():
    out = []
    means = {}
    plan = [(32, 30), (128, 30), (512, 15), (1024, 8)]
    for n, count in plan:
        total = 0
        for s in seeds(range(count)):
            r, sim = run_gossip(n, s)
            informed = sum(1 for x in sim.nodes if x.informed)
            assert r is not None, f"seed {s}, n={n}: after 300 rounds only {informed}/{n} nodes know the rumour"
            total += r
        means[n] = total / len(seeds(range(count)))
        est = math.log2(n) + math.log(n)
        ratio = means[n] / est
        assert 0.7 <= ratio <= 1.7, (f"n={n}: mean {means[n]:.1f} rounds, but log2 n + ln n = {est:.1f}; "
                                     f"the ratio {ratio:.2f} is outside 0.7..1.7. Is each informed node pushing once per round?")
        out.append(f"n={n:5d}: {means[n]:5.1f} rounds   (log2 n + ln n = {est:4.1f})")
    if ONLY_SEED is None:
        for a, b in zip(plan, plan[1:]):
            gain = means[b[0]] - means[a[0]]
            assert 0.5 < gain < 8, (f"going from n={a[0]} to n={b[0]} added {gain:.1f} rounds; "
                                    f"logarithmic growth adds about {math.log2(b[0] / a[0]) + math.log(b[0] / a[0]):.1f}")
        assert means[1024] < 2.5 * means[32], "growth looks linear in n, not logarithmic"
        # more fan-out is faster
        f1 = sum(run_gossip(256, s, fanout=1)[0] for s in range(15)) / 15
        f3 = sum(run_gossip(256, s, fanout=3)[0] for s in range(15)) / 15
        assert f3 < 0.8 * f1, f"fan-out 3 should clearly beat fan-out 1 at n=256 ({f3:.1f} vs {f1:.1f} rounds)"
        out.append(f"n=256: fan-out 1 needs {f1:.1f} rounds, fan-out 3 needs {f3:.1f}")
    # loss and crashes slow it down but do not stop it
    worst = 0
    for s in seeds(range(25)):
        r, sim = run_gossip(128, s, loss=0.3, crash=13)
        informed = sum(1 for x in sim.nodes if x.informed and sim.alive[x.id])
        assert r is not None, f"seed {s}: with 30% loss and 13 crashed nodes only {informed}/115 live nodes were informed"
        worst = max(worst, r)
    est = math.log2(128) + math.log(128)
    assert worst <= 4 * est, f"30% loss should cost a few extra rounds, not {worst}"
    out.append(f"30% loss + 13 crashed of 128: slowest of 25 seeds {worst} rounds, everyone alive informed")
    return "\n".join(out)


# =============================================================================
# Milestone 2: heartbeats
# =============================================================================
def run_hb(seed, timeout, loss=0.0, n=6, crash=None, pause=None, until=3000):
    sim = Sim(seed, n, lambda s, i, p: mod.HeartbeatNode(s, i, p, timeout=timeout), loss=loss)
    if crash:
        sim.at(crash[1], lambda: sim.crash(crash[0]))
    if pause:
        sim.at(pause[1], lambda: sim.pause(pause[0], pause[2]))
    sim.run(until)
    return sim


def false_positives(sim, dead_node=None):
    return [e for e in sim.events("suspect") if e[3] != dead_node]


def m2():
    out = []
    for s in seeds(range(10)):
        sim = run_hb(s, 40)
        assert not sim.log, f"seed {s}: no loss, no crash, yet {trace(sim)}"
    # detection time
    detect = {}
    for timeout in (25, 40, 70):
        times = []
        for s in seeds(range(20)):
            sim = run_hb(s, timeout, crash=(0, 500), until=1000)
            first = {}
            for t, k, o, subj in sim.events("suspect", 0):
                first.setdefault(o, t)
            assert set(first) == {1, 2, 3, 4, 5}, (f"seed {s}, timeout {timeout}: node 0 crashed at t=500 but only "
                                                  f"{sorted(first)} suspect it by t=1000")
            assert min(first.values()) > 500 - timeout, f"seed {s}: node 0 was suspected before it crashed"
            times.append(max(first.values()) - 500)
        detect[timeout] = sum(times) / len(times)
        assert max(times) <= timeout + HB_PERIOD + 15, (f"timeout {timeout}: slowest detection {max(times)} ticks; "
                                                         f"expected at most about timeout + period + delay")
    # false positives under loss
    fp = {}
    for timeout in (25, 40, 70):
        fp[timeout] = sum(len(false_positives(run_hb(s, timeout, loss=0.2, crash=None, until=3000))) for s in seeds(range(20)))
    for timeout in (25, 40, 70):
        out.append(f"timeout {timeout:2d}: detection {detect[timeout]:5.1f} ticks, "
                   f"{fp[timeout]:4d} false suspicions in 20 runs with 20% loss")
    if ONLY_SEED is None:
        assert fp[25] > 0, "a 25-tick timeout with 20% loss should produce false suspicions; is the timeout test missing?"
        assert fp[25] > fp[40] >= fp[70], "a longer timeout should give fewer false suspicions"
        assert detect[70] > detect[25] + 20, "a longer timeout should detect crashes later"
    # a slow node: frozen for 120 ticks, longer than the 70-tick timeout
    for s in seeds(range(10)):
        sim = run_hb(s, 70, pause=(2, 1000, 120), until=2000)
        accusers = {o for _, k, o, subj in sim.events("suspect", 2) if o != 2}
        assert accusers == {0, 1, 3, 4, 5}, (f"seed {s}: node 2 froze for 120 ticks (timeout 70), expected all five peers "
                                            f"to suspect it, got {sorted(accusers)}")
        assert all(not x.suspects for x in sim.nodes if x.id != 2), \
            f"seed {s}: node 2 woke up and sent heartbeats, but someone still suspects it: {[ (x.id, x.suspects) for x in sim.nodes ]}"
    out.append("a node frozen for 120 ticks is suspected by everyone, then forgiven once it speaks again")
    return "\n".join(out)


# =============================================================================
# Milestones 3 and 4: SWIM
# =============================================================================
def run_swim(seed, n=8, k=3, dissem=False, loss=0.0, dup=0.0, crash=(), pause=None, block=None, until=5000):
    sim = Sim(seed, n, lambda s, i, p: mod.SwimNode(s, i, p, k=k, dissem=dissem), loss=loss, dup=dup)
    for node, when in crash:
        sim.at(when, lambda node=node: sim.crash(node))
    if pause:
        sim.at(pause[1], lambda: sim.pause(pause[0], pause[2]))
    if block:
        sim.block(*block)
    sim.run(until)
    return sim


def m3():
    out = []
    # a healthy cluster stays quiet, and the load per node does not depend on n
    for s in seeds(range(10)):
        sim = run_swim(s, n=8, until=6000)
        assert not sim.log, f"seed {s}: nothing is wrong, yet {trace(sim)}"
    for n in (8, 32):
        sim = run_swim(1, n=n, until=100 * PERIOD)
        per_node = sum(sim.sent_by) / n / 100
        assert sim.sent.get("ping-req", 0) == 0, "healthy cluster, yet someone sent ping-req (only ask helpers after a direct ping fails)"
        assert 1.8 <= per_node <= 2.4, (f"n={n}: each member sent {per_node:.2f} messages per period; "
                                         f"expected 2 (one ping + one ack received and answered)")
        out.append(f"n={n:2d}: {per_node:.2f} messages sent per member per period (constant, independent of n)")
    # a crashed member is found by everybody, using nothing but its own probes
    for s in seeds(range(20)):
        sim = run_swim(s, n=8, crash=[(0, 300)], until=300 + 12 * PERIOD + 1000)
        for x in sim.nodes[1:]:
            assert x.members[0][0] == "dead", (f"seed {s}: node {x.id} still thinks node 0 is {x.members[0][0]!r} "
                                              f"long after it crashed. {trace(sim, 0)}")
        wrong = [e for e in sim.events("dead") if e[3] != 0]
        assert not wrong, f"seed {s}: a live node was declared dead: {trace(sim, wrong[0][3])}"
    out.append("a crashed member was declared dead by all 7 others in every seed")
    # a bad link between two live members: ping-req routes around it
    for s in seeds(range(15)):
        sim = run_swim(s, n=8, k=3, block=(2, 5), until=8000)
        assert not sim.log, (f"seed {s}: the link 2<->5 is dead but both nodes are fine; with k=3 helpers nobody "
                             f"should even suspect. {trace(sim)}")
    bad = [s for s in seeds(range(15)) if not run_swim(s, n=8, k=0, block=(2, 5), until=8000).events("suspect")]
    assert not bad or ONLY_SEED is not None, f"with k=0 and a dead link, nodes 2 and 5 should suspect each other (seeds without: {bad})"
    out.append("bad link 2<->5: no suspicion with k=3 helpers, but suspicion with k=0")
    # a short freeze: suspected, then cleared by a late ack, never declared dead
    suspected = 0
    for s in seeds(range(10)):
        sim = run_swim(s, n=8, pause=(3, 1000, 700), until=6000)
        assert not sim.events("dead"), f"seed {s}: node 3 froze for 700 ticks (suspicion timeout is longer) but {trace(sim, 3)}"
        suspected += bool(sim.events("suspect", 3))
        for x in sim.nodes:
            assert x.members[3][0] == "alive", f"seed {s}: node {x.id} still holds node 3 as {x.members[3][0]!r} long after it woke up"
    assert suspected >= 8 or ONLY_SEED is not None, f"only {suspected}/10 seeds ever suspected the frozen node; is probe_end committing 'suspect'?"
    out.append(f"frozen member: suspected in {suspected}/10 seeds, never declared dead, alive again everywhere")
    return "\n".join(out)


def m4():
    out = []
    # the override rules, one at a time, on a bare node
    sim = Sim(0, 3, lambda s, i, p: mod.SwimNode(s, i, p, dissem=True))
    nd = sim.nodes[0]

    def state(m):
        return list(nd.members[m])
    assert nd.apply_update(1, "suspect", 0) and state(1) == ["suspect", 0], "suspect(1, 0) must beat alive(1, 0): i >= j"
    assert not nd.apply_update(1, "alive", 0) and state(1) == ["suspect", 0], "alive(1, 0) must NOT beat suspect(1, 0): it needs i > j"
    assert nd.apply_update(1, "alive", 1) and state(1) == ["alive", 1], "alive(1, 1) must beat suspect(1, 0)"
    assert not nd.apply_update(1, "suspect", 0) and state(1) == ["alive", 1], "a STALE suspect(1, 0) must lose to alive(1, 1) however late it arrives"
    assert nd.apply_update(1, "suspect", 1) and state(1) == ["suspect", 1], "a fresh suspect(1, 1) beats alive(1, 1)"
    assert not nd.apply_update(1, "suspect", 1), "suspect(1, 1) over suspect(1, 1) is no news"
    assert nd.apply_update(1, "suspect", 2) and state(1) == ["suspect", 2], "suspect(1, 2) beats suspect(1, 1)"
    assert nd.apply_update(1, "dead", 0) and state(1)[0] == "dead", "dead beats everything"
    assert not nd.apply_update(1, "alive", 99) and state(1)[0] == "dead", "dead is final in this lab"
    assert nd.apply_update(0, "suspect", 0) and state(0) == ["alive", 1], "accused at incarnation 0: refute by committing alive(0, 1)"
    assert nd.buf.get(0, [None])[:2] == ["alive", 1], "the refutation must be queued for piggybacking (queue_update)"
    assert not nd.apply_update(0, "suspect", 0) and state(0) == ["alive", 1], "the old accusation (inc 0) must not force a second refutation"
    assert nd.apply_update(0, "suspect", 1) and state(0) == ["alive", 2], "accused again at the current incarnation: refute at 2"
    nd.apply_update(0, "dead", 5)
    assert state(0)[0] == "alive", "a node never accepts its own death certificate from gossip in this lab"
    # piggyback buffer
    nd.buf.clear()
    for subj in range(6):
        nd.queue_update(subj, "suspect", subj)
    first = nd.piggyback()
    assert len(first) == mod.MAX_PIGGY and all(len(u) == 3 for u in first), f"piggyback should return {mod.MAX_PIGGY} (subject, state, inc) tuples"
    second = nd.piggyback()
    assert {u[0] for u in second} >= ({0, 1, 2, 3, 4, 5} - {u[0] for u in first}), \
        "updates sent the fewest times should go first, so the two left-over updates must be in the second batch"
    for _ in range(6 * nd.retransmit):
        nd.piggyback()
    assert not nd.buf, f"an update must be dropped from the buffer once it has been sent {nd.retransmit} times"

    # completeness: crashed members are eventually confirmed dead by everyone
    slowest = 0
    for s in seeds(range(40)):
        sim = run_swim(s, n=16, dissem=True, loss=0.05, dup=0.02, crash=[(3, 1000), (11, 1000)], until=1000 + 70 * PERIOD)
        for x in sim.nodes:
            if not sim.alive[x.id]:
                continue
            for c in (3, 11):
                assert x.members[c][0] == "dead", (f"seed {s}: node {x.id} still sees crashed node {c} as {x.members[c][0]!r} "
                                                  f"after 70 periods (completeness). {trace(sim, c, 6)}")
        done = [max(t for t, k, o, subj in sim.events("dead", c)) for c in (3, 11)]
        slowest = max(slowest, max(done) - 1000)
    out.append(f"completeness: 2 crashed of 16, 5% loss, 40 seeds: all confirmed dead everywhere; slowest took {slowest // PERIOD} periods")

    # accuracy: with 5% loss, live nodes are almost never declared dead
    bad = []
    wrong_total = 0
    count = len(seeds(range(80)))
    for s in seeds(range(80)):
        sim = run_swim(s, n=16, dissem=True, loss=0.05, dup=0.02, until=200 * PERIOD)
        wrongly = sim.events("dead")
        if wrongly:
            first_failure = not bad
            bad.append(s)
            wrong_total += 1
            first = wrongly[0]
            if first_failure:
                last = (f"seed {s}: node {first[2]} declared live node {first[3]} dead at t={first[0]}. "
                        f"Trace for that node: {trace(sim, first[3], 8)}")
    assert len(bad) <= 0.1 * count, (f"accuracy: live nodes were declared dead in {len(bad)} of {count} seeds (limit 10%). "
                                     f"Failing seeds: {bad[:12]}. {last}")
    out.append(f"accuracy: 16 live nodes, 200 periods, 5% loss: a live node was declared dead in {len(bad)} of {count} seeds")

    # refutation: a frozen member is suspected, refutes with a higher incarnation, and survives
    refuted = 0
    suspected = 0
    for s in seeds(range(30)):
        sim = run_swim(s, n=12, dissem=True, pause=(5, 1500, 800), until=9000)
        assert not sim.events("dead"), (f"seed {s}: node 5 froze for 800 ticks, which is shorter than the suspicion timeout "
                                        f"({sim.nodes[0].suspect_timeout}), yet {trace(sim, None, 6)}")
        if sim.events("suspect", 5):
            suspected += 1
            inc = sim.nodes[5].members[5][1]
            assert inc >= 1, f"seed {s}: node 5 was suspected but never raised its incarnation (still {inc})"
            refuted += 1
        for x in sim.nodes:
            assert x.members[5][0] == "alive", (f"seed {s}: node {x.id} still holds node 5 as {x.members[5]!r} at the end; "
                                               f"its alive(5, {sim.nodes[5].members[5][1]}) refutation did not arrive or lost")
    assert suspected >= 24 or ONLY_SEED is not None, f"only {suspected}/30 seeds ever suspected the frozen node"
    out.append(f"refutation: frozen node suspected in {suspected}/30 seeds; refuted with a higher incarnation in {refuted}")

    # dissemination rides on existing messages
    sim = run_swim(3, n=16, dissem=True, loss=0.05, crash=[(4, 500)], until=100 * PERIOD)
    kinds = set(sim.sent)
    assert kinds <= {"ping", "ack", "ping-req"}, f"membership news must be piggybacked, but you sent extra message types: {sorted(kinds)}"
    per_node = sum(sim.sent_by) / 16 / 100
    assert per_node < 3.2, f"load per member is {per_node:.2f} messages per period; piggybacking should add none"
    out.append(f"only {sorted(kinds)} messages exist; {per_node:.2f} sent per member per period")
    return "\n".join(out)


# =============================================================================
# Milestone 5: Merkle anti-entropy
# =============================================================================
def make_pair(rng, keys, differ):
    a = mod.Replica()
    for i in range(keys):
        a.put(f"key{i:05d}", f"v{i}", 1)
    b = mod.Replica(a.data)
    names = sorted(a.data)
    chosen = rng.sample(names, differ)
    for j, key in enumerate(chosen):
        if j % 3 == 0:
            b.data[key] = (f"newer-{j}", 2)          # b has a newer version
        elif j % 3 == 1:
            del b.data[key]                          # b is missing the key
        else:
            a.data[key] = (f"a-newer-{j}", 5)        # a has a newer version
    if differ >= 3:
        b.put("extra-on-b", "x", 1)                  # a key only b has
    return a, b


def m5():
    out = []
    # identical replicas cost one comparison and zero keys
    rng = random.Random(1)
    a, b = make_pair(rng, 2000, 0)
    b.data.pop("extra-on-b", None)
    stats = mod.sync(a, b)
    assert stats["comparisons"] == 1 and stats["keys_sent"] == 0 and stats["buckets"] == 0, \
        f"identical replicas should cost 1 comparison and 0 keys, got {stats}"
    # d differences, found cheaply
    worst_cmp, worst_ratio = 0, 0.0
    for s in seeds(range(100)):
        rng = random.Random(s)
        d = rng.randint(1, 12)
        a, b = make_pair(rng, 4000, d)
        total = len(a.data) + len(b.data)
        stats = mod.sync(a, b)
        assert a.data == b.data, f"seed {s}: after sync the replicas still differ ({len(set(a.data.items()) ^ set(b.data.items()))} entries)"
        for key, (value, version) in a.data.items():
            assert version >= 1
        levels = int(math.log2(mod.BUCKETS)) + 1
        differing = d + (1 if d >= 3 else 0)
        assert stats["buckets"] <= differing, f"seed {s}: {stats['buckets']} buckets differ but only {differing} keys do"
        assert stats["comparisons"] <= 1 + 2 * differing * (levels - 1), (f"seed {s}: {stats['comparisons']} hash comparisons for "
                                                                     f"{differing} differing keys is too many (limit {1 + 2 * differing * (levels - 1)})")
        assert stats["keys_sent"] <= 0.25 * total, (f"seed {s}: sent {stats['keys_sent']} keys of {total}; "
                                                    "only the differing buckets should travel")
        worst_cmp = max(worst_cmp, stats["comparisons"])
        worst_ratio = max(worst_ratio, stats["keys_sent"] / total)
    # newer versions win, in both directions
    a = mod.Replica({"k": ("old", 1), "only-a": ("A", 1)})
    b = mod.Replica({"k": ("new", 7), "only-b": ("B", 1)})
    mod.sync(a, b)
    assert a.data == b.data == {"k": ("new", 7), "only-a": ("A", 1), "only-b": ("B", 1)}, f"merge result wrong: {a.data} / {b.data}"
    out.append(f"100 scenarios, 4000 keys, up to 13 differences: replicas always converge; "
               f"at most {worst_cmp} hash comparisons and {100 * worst_ratio:.1f}% of the keys sent")
    return "\n".join(out)


print(f"Lab 1 checks against {target}.py\n")
check(1, "Milestone 1: push gossip and log n", m1)
check(2, "Milestone 2: heartbeat detector with a fixed timeout", m2)
check(3, "Milestone 3: SWIM probing, ping-req and suspicion", m3)
check(4, "Milestone 4: incarnations and piggybacked dissemination", m4)
check(5, "Milestone 5 (optional): Merkle-tree anti-entropy", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
