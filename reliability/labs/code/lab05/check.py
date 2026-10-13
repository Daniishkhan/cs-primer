"""Self-check for Lab 5: Adaptive Concurrency & Load Shedding.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 4     # milestone 3, replaying ONLY seed 4

Everything is simulated: time is a number, every random draw comes from a seeded
random.Random, nothing sleeps and nothing touches the network. Every run gives
identical numbers and the whole check finishes in well under a minute. When a
check fails it prints the seed, so you can replay exactly that run.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


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


Config, Protections, simulate = mod.Config, mod.Protections, mod.simulate
BASE = 70.0


def run(seed, prot, **kw):
    return simulate(Config(**kw), prot, seed)


def post(res):
    """Goodput from 30 s after the trigger ended until the end of the run."""
    s = int(res.cfg.trigger_end + 30)
    return sum(res.succ[s:int(res.cfg.duration)]) / (int(res.cfg.duration) - s)


def gp(res, t0, t1):
    return sum(res.succ[int(t0):int(t1)]) / (int(t1) - int(t0))


# --------------------------------------------------------------------------------------
def m1():
    # A: one worker, 0.1 s jobs, 0.25 s timeout, room for two in the queue, four requests at t=0.
    cfg = Config(workers=1, service_mean=0.1, service_fixed=True, timeout=0.25, max_retries=0,
                 queue_limit=2, duration=5.0, trigger="none")
    r = simulate(cfg, Protections.none(), 1, arrivals=[0.0, 0.0, 0.0, 0.0])
    assert sum(r.succ) == 2, f"requests 1 and 2 finish at 0.1 and 0.2, inside the deadline: expected 2 successes, got {sum(r.succ)}"
    assert sum(r.wasted) == 1, (f"request 3 starts at 0.2 and finishes at 0.3, but its client left at 0.25: the work is wasted. "
                                f"expected 1 wasted job, got {sum(r.wasted)}")
    assert sum(r.rejected) == 1, f"request 4 finds the queue full (limit 2): expected 1 rejection, got {sum(r.rejected)}"
    assert r.ok == 2 and r.failed == 2 and r.n_orig == 4, f"outcomes should be 2 ok and 2 failed of 4, got ok={r.ok} failed={r.failed}"
    # B: one retry that works.
    cfg = Config(workers=1, service_mean=0.1, service_fixed=True, timeout=0.15, max_retries=2,
                 retry_backoff=0.01, queue_limit=10, duration=5.0, trigger="none")
    r = simulate(cfg, Protections.none(), 1, arrivals=[0.0, 0.0])
    assert sum(r.attempts) == 3, f"expected 3 attempts (2 first tries + 1 retry), got {sum(r.attempts)}"
    assert r.ok == 2 and r.failed == 0, f"the retry of request 2 should succeed at about 0.3 s: ok={r.ok} failed={r.failed}"
    assert sum(r.wasted) == 1, f"the first attempt of request 2 is still worked on after its client left: expected 1 wasted job, got {sum(r.wasted)}"
    # C: retries stop at max_retries.
    cfg = Config(workers=1, service_mean=1.0, service_fixed=True, timeout=0.1, max_retries=2,
                 retry_backoff=0.01, queue_limit=10, duration=10.0, trigger="none")
    r = simulate(cfg, Protections.none(), 1, arrivals=[0.0, 0.0])
    assert sum(r.attempts) == 6, f"2 requests x (1 try + 2 retries) = 6 attempts, got {sum(r.attempts)}"
    assert r.failed == 2 and r.ok == 0, f"both requests should give up: failed={r.failed} ok={r.ok}"
    # D: FIFO order
    q = mod.FifoQueue()
    items = [mod.Req(mod.Orig(i, 0.0)) for i in range(5)]
    for x in items:
        q.push(x, 0.0)
    assert len(q) == 5, "len(queue) should count the waiting requests"
    out = [q.pop(0.0)[0] for _ in range(5)]
    assert out == items, "FifoQueue must serve in arrival order"
    assert q.pop(0.0)[0] is None and len(q) == 0, "an empty queue pops None"
    # E: invariants over seeds
    for s in seeds(range(1, 9)):
        r = run(s, Protections.none(), duration=60.0, trigger_start=10.0, trigger_end=20.0, queue_limit=300)
        assert r.max_busy <= 10, f"seed {s}: {r.max_busy} jobs ran at once with only 10 workers"
        assert r.max_queue <= 300, f"seed {s}: queue reached {r.max_queue}, over the limit of 300"
        assert sum(r.succ) == r.ok, f"seed {s}: {sum(r.succ)} successful responses but {r.ok} requests marked ok (a request succeeds at most once)"
        assert r.ok + r.failed <= r.n_orig, f"seed {s}: more outcomes than requests"
    for s in seeds(range(1, 6)):
        r = run(s, Protections.none(), trigger="none", duration=60.0)
        g = gp(r, 10, 60)
        assert abs(g - BASE) < 0.1 * BASE, f"seed {s}: at 70% load with no trigger goodput should be about {BASE:.0f}/s, got {g:.1f}"
        assert r.failed <= 0.01 * r.n_orig, f"seed {s}: {r.failed} of {r.n_orig} requests failed at 70% load"
        assert sum(r.wasted) <= 0.01 * sum(r.succ), f"seed {s}: wasted work at normal load: {sum(r.wasted)}"
    return "a 70%-loaded service serves about 70 req/s and wastes almost nothing"


def m2():
    c = Config()
    R = mod.Result
    # unit tests of the measurements on a hand-made result
    r = R(c)
    for t in range(0, 20):
        r.succ[t] = 70
    for t in range(60, 140):
        r.succ[t] = 5
        r.wasted[t] = 95
    assert abs(mod.goodput(r, 5, 20) - 70) < 1e-9, "goodput over [5,20) should be 70"
    assert abs(mod.goodput(r, 60, 140) - 5) < 1e-9, "goodput over [60,140) should be 5"
    assert abs(mod.wasted_share(r, 60, 140) - 0.95) < 1e-9, f"wasted share should be 95/(95+5), got {mod.wasted_share(r, 60, 140)}"
    assert mod.wasted_share(r, 25, 30) == 0.0, "no completions -> wasted share 0, not a division by zero"
    assert mod.is_metastable(r), "healthy before, 5/s long after the trigger: metastable"
    for t in range(60, 140):
        r.succ[t] = 69
        r.wasted[t] = 0
    assert not mod.is_metastable(r), "recovered to 69/s: not metastable"
    assert not mod.is_metastable(R(c)), "never healthy: that is just an outage, not a metastable failure"
    gps = []
    for s in seeds(range(1, 7)):
        base = run(s, Protections.none(), trigger="none")
        assert not mod.is_metastable(base), f"seed {s}: no trigger, but the run was flagged metastable"
        assert post(base) > 0.9 * BASE, f"seed {s}: no trigger: goodput {post(base):.1f}, expected about 70"
        dip = run(s, Protections.none())
        assert gp(dip, 5, 20) > 0.9 * BASE, f"seed {s}: before the trigger the service must be healthy"
        assert mod.is_metastable(dip), (f"seed {s}: a 10 s capacity dip (10 -> 4 workers) should leave goodput collapsed "
                                        f"long after capacity returned; goodput after = {post(dip):.1f}/s")
        ws = mod.wasted_share(dip, 60, 140)
        assert ws > 0.9, f"seed {s}: after the trigger nearly every finished job should be wasted work for clients that left; wasted share = {ws:.2f}"
        spike = run(s, Protections.none(), trigger="spike")
        assert mod.is_metastable(spike), f"seed {s}: a 10 s load spike (3x) should also trigger it; goodput after = {post(spike):.1f}/s"
        tiny = run(s, Protections.none(), trigger_end=21.0)
        assert not mod.is_metastable(tiny), f"seed {s}: a 1-second dip should be absorbed; goodput after = {post(tiny):.1f}/s"
        gps.append((post(dip), post(spike)))
    return ("trigger: 10 workers -> 4 for 10 s (or load x3 for 10 s); load is then back to 70 req/s. Goodput 30+ s later, one per seed:\n"
            "dip   " + " ".join(f"{a:4.1f}" for a, _ in gps) + "     spike " + " ".join(f"{b:4.1f}" for _, b in gps) + "   (req/s)")


def mkreq(i, enq, deadline):
    q = mod.Req(mod.Orig(i, enq))
    q.enq, q.sent, q.deadline = enq, enq, deadline
    return q


def m3():
    Q = mod.ShedQueue
    # expiry at pop time
    q = Q(expire=True, lifo_over=None, min_useful=0.1)
    a, b, c = mkreq(1, 0.0, 1.0), mkreq(2, 0.5, 1.5), mkreq(3, 0.9, 1.9)
    for x in (a, b, c):
        q.push(x, x.enq)
    req, dropped = q.pop(0.95)       # a: 0.95 + 0.1 > 1.0 -> expired
    assert req is b, "the head (deadline 1.0) cannot finish by 0.95 + 0.1: drop it and serve the next one"
    assert a in dropped, "the expired request must be returned in the dropped list"
    assert len(q) == 1, "the dropped request must leave the queue"
    # nothing expired -> FIFO
    q = Q(expire=True, lifo_over=None, min_useful=0.1)
    xs = [mkreq(i, 0.0, 10.0) for i in range(4)]
    for x in xs:
        q.push(x, 0.0)
    assert [q.pop(0.1)[0] for _ in range(4)] == xs, "with no overload and no expired requests the order is FIFO"
    # LIFO over threshold
    q = Q(expire=True, lifo_over=3, min_useful=0.0)
    xs = [mkreq(i, 0.0, 100.0) for i in range(6)]
    for x in xs:
        q.push(x, 0.0)
    assert q.pop(1.0)[0] is xs[5], "queue length 6 > 3: serve the NEWEST first"
    assert q.pop(1.0)[0] is xs[4], "length 5 > 3: newest again"
    assert q.pop(1.0)[0] is xs[3], "length 4 > 3: newest again"
    assert q.pop(1.0)[0] is xs[0], "length 3 is not over 3: back to FIFO, the oldest"
    # expired requests at the head are purged on push (the waiting room never fills with dead requests)
    q = Q(expire=True, lifo_over=None, min_useful=0.0)
    for i in range(5):
        q.push(mkreq(i, 0.0, 1.0), 0.0)
    q.push(mkreq(9, 5.0, 6.0), 5.0)
    assert len(q) == 1, f"pushing at t=5 should purge the five requests whose deadline was 1.0; length is {len(q)}"
    req, dropped = q.pop(5.0)
    assert req.orig.oid == 9 and len(dropped) == 5, f"the purged requests must be reported as dropped by the next pop; got {len(dropped)}"
    q = Q(expire=False, lifo_over=None)
    q.push(mkreq(1, 0.0, 1.0), 0.0)
    assert q.pop(50.0)[0] is not None, "with expire=False even a hopeless request is served"
    # in the full simulation
    rows = []
    for s in seeds(range(1, 7)):
        for trig in ("dip", "spike"):
            off = run(s, Protections.none(), trigger=trig)
            on = run(s, Protections.shedding(), trigger=trig)
            assert mod.is_metastable(off), f"seed {s} {trig}: the unprotected run should be metastable"
            assert post(on) > 0.9 * BASE, (f"seed {s} {trig}: with deadline-aware shedding + LIFO goodput after the trigger should be back near "
                                          f"{BASE:.0f}/s, got {post(on):.1f}/s (unprotected: {post(off):.1f})")
            ws = mod.wasted_share(on, 60, 140)
            assert ws < 0.05, f"seed {s} {trig}: wasted share {ws:.2f}; shedding should avoid useless work"
            if trig == "dip":
                during = gp(on, 22, 30)
                assert during > 30, f"seed {s}: during the dip 4 workers can do 40/s of useful work; goodput was {during:.1f}"
            rows.append((s, trig, post(off), post(on)))
    out = ["goodput 30+ s after the trigger (req/s), unprotected -> deadline shedding + LIFO:"]
    for trig in ("dip", "spike"):
        xs = [r for r in rows if r[1] == trig]
        out.append(f"{trig:5} " + "   ".join(f"{a:4.1f} -> {b:4.1f}" for _, _, a, b in xs[:3]) + "   ...")
    return "\n".join(out)


def m4():
    L = mod.AIMDLimiter
    lim = L(initial=10.0, target=0.05, backoff=0.9, cooldown=0.2)
    assert lim.try_acquire(9) and not lim.try_acquire(10), "limit 10: 9 in flight may admit one more, 10 may not"
    for i in range(100):
        lim.on_sample(0.0, float(i))
    assert 10.0 < lim.limit < 20.0, f"100 fast responses should raise the limit slowly (+1/limit each, about +9); got {lim.limit:.2f}"
    before = lim.limit
    lim.on_sample(0.5, 1000.0)
    assert abs(lim.limit - before * 0.9) < 1e-9, f"a slow response should cut the limit to 90%: {before:.2f} -> {lim.limit:.2f}"
    lim.on_sample(0.5, 1000.05)
    assert abs(lim.limit - before * 0.9) < 1e-9, "a second slow response within the 0.2 s cooldown must not cut again"
    lim.on_sample(0.5, 1000.3)
    assert abs(lim.limit - before * 0.81) < 1e-9, "after the cooldown the next slow response cuts again"
    lim.on_drop(2000.0)
    assert abs(lim.limit - before * 0.729) < 1e-9, "a drop is a congestion signal too"
    small = L(initial=2.5, min_limit=2.0, max_limit=3.0)
    for i in range(50):
        small.on_drop(float(i))
    assert small.limit == 2.0, "the limit never goes below min_limit"
    for i in range(500):
        small.on_sample(0.0, 100.0 + i)
    assert small.limit == 3.0, "the limit never goes above max_limit"
    # a service far over capacity, no retries: 300 req/s offered, 100/s possible
    note = []
    star = 10.0           # optimal concurrency: capacity (100/s) x service time (0.1 s) = 10, by Little's law
    for s in seeds(range(1, 6)):
        off = run(s, Protections.none(), trigger="none", base_rate=300.0, max_retries=0, duration=120.0)
        on = run(s, Protections(limiter=True), trigger="none", base_rate=300.0, max_retries=0, duration=120.0)
        g_off, g_on = gp(off, 40, 120), gp(on, 40, 120)
        assert g_off < 20, f"seed {s}: a FIFO queue of 2000 under 3x overload serves late answers only; unprotected goodput {g_off:.1f}"
        assert g_on > 90, f"seed {s}: with the AIMD limit goodput should stay near capacity (100/s); got {g_on:.1f}"
        lims = on.limit[40:120]
        mean_lim = sum(lims) / len(lims)
        assert star <= mean_lim <= 2.2 * star, (f"seed {s}: the limit should settle near the optimal concurrency {star:.0f} "
                                                f"(between {star:.0f} and {2.2 * star:.0f}); it averaged {mean_lim:.1f}")
        lat = sorted(on.latencies)
        p99 = lat[len(lat) * 99 // 100]
        assert p99 < 1.0, f"seed {s}: latency of successful requests should be bounded; p99 = {p99:.2f} s"
        Lavg = on.area / on.cfg.duration
        X = on.sojourn_n / on.cfg.duration
        W = on.sojourn_sum / on.sojourn_n
        assert abs(Lavg - X * W) / Lavg < 0.06, f"seed {s}: Little's law L = X*W is off: L={Lavg:.2f}, X*W={X * W:.2f}"
        if not note:
            note.append(f"300 req/s offered, capacity 100/s: unprotected goodput {g_off:.1f}/s; with AIMD {g_on:.1f}/s, p99 {p99 * 1000:.0f} ms")
            note.append(f"the limit settled at about {mean_lim:.1f} (optimum {star:.0f} = 100/s x 0.1 s)")
            note.append(f"Little's law: L = {Lavg:.2f} requests in the server; X*W = {X:.1f}/s x {W * 1000:.0f} ms = {X * W:.2f}")
    for s in seeds(range(1, 5)):
        for trig in ("dip", "spike"):
            r = run(s, Protections.server_side(), trigger=trig)
            assert post(r) > 0.9 * BASE, f"seed {s} {trig}: shedding + AIMD should recover from the trigger; goodput after {post(r):.1f}/s"
    return "\n".join(note)


def m5():
    B, T = mod.RetryBudget, mod.ClientThrottle
    b = B(ratio=0.1, max_tokens=10.0)
    assert not b.try_retry(), "a fresh budget has no tokens"
    allowed = 0
    for i in range(100):
        b.on_request()
        if b.try_retry():
            allowed += 1
    assert allowed == 10, f"100 requests at a 10% budget allow 10 retries, got {allowed}"
    b = B(ratio=0.1, max_tokens=10.0)
    for i in range(1000):
        b.on_request()
    burst = sum(1 for _ in range(100) if b.try_retry())
    assert burst == 10, f"the bucket holds at most max_tokens=10: a burst of retries after quiet traffic gets {burst}"
    t = T(k=2.0, window=30.0)
    for i in range(100):
        t.record(float(i) * 0.1, True)
    assert t.reject_probability(10.0) == 0.0, "all requests accepted -> never throttle"
    t = T(k=2.0, window=30.0)
    for i in range(100):
        t.record(float(i) * 0.1, False)
    p = t.reject_probability(10.0)
    assert 0.98 < p < 1.0, f"100 requests, none accepted: probability (100 - 0)/(100 + 1) = 0.99, got {p:.3f}"
    t = T(k=2.0, window=30.0)
    for i in range(100):
        t.record(float(i) * 0.1, i % 2 == 0)
    assert t.reject_probability(10.0) == 0.0, "50% accepted with k=2: (100 - 2*50)/101 = 0, no throttling yet"
    t = T(k=2.0, window=30.0)
    for i in range(100):
        t.record(float(i) * 0.1, i % 4 == 0)
    p = t.reject_probability(10.0)
    assert abs(p - (100 - 2 * 25) / 101) < 1e-9, f"25% accepted: expected {(100 - 50) / 101:.3f}, got {p:.3f}"
    assert t.reject_probability(100.0) == 0.0, "after the window passes, the old events are forgotten"
    rng = random.Random(5)
    sent = 0
    for _ in range(1000):
        t = T(k=2.0, window=30.0)
        for i in range(100):
            t.record(float(i) * 0.1, i % 4 == 0)
        sent += 1 if t.allow(10.0, rng) else 0
    assert 0.40 < sent / 1000 < 0.60, f"a throttle with p = 0.495 should let about half of fresh attempts through; it let {sent / 1000:.2f}"
    for s in seeds(range(1, 6)):
        for trig in ("dip", "spike"):
            off = run(s, Protections.none(), trigger=trig)
            full = run(s, Protections.full(), trigger=trig)
            assert mod.is_metastable(off), f"seed {s} {trig}: the unprotected run should be metastable"
            assert post(full) > 0.9 * BASE, f"seed {s} {trig}: with every protection goodput after the trigger should recover; got {post(full):.1f}/s"
            assert post(full) > 5 * max(post(off), 1.0), f"seed {s} {trig}: protections must beat the unprotected run by a wide margin"
        for trig in ("dip", "spike"):
            cl = run(s, Protections.client_side(), trigger=trig)
            assert post(cl) > 0.8 * BASE, f"seed {s} {trig}: retry budget + throttle alone should recover from the trigger; goodput after {post(cl):.1f}/s"
        cl = run(s, Protections.client_side(), trigger="dip")
        retries = sum(cl.attempts) - cl.n_orig
        assert retries <= 0.12 * cl.n_orig + 15, f"seed {s}: the retry budget must cap retries near 10% of requests; made {retries} retries for {cl.n_orig} requests"
        calm = run(s, Protections.full(), trigger="none")
        assert post(calm) > 0.93 * BASE, f"seed {s}: protections must not cost goodput when nothing is wrong: {post(calm):.1f}/s"
    s = seeds([1])[0]
    note = [f"seed {s}: goodput 30+ s after the trigger (req/s) and seconds until goodput is back to 80% of normal:"]
    for name, prot in (("none", Protections.none()), ("shedding + LIFO", Protections.shedding()), ("+ AIMD limit", Protections.server_side()),
                       ("retry budget + throttle", Protections.client_side()), ("everything", Protections.full())):
        cells = []
        for trig in ("dip", "spike"):
            r = run(s, prot, trigger=trig)
            rt = mod.recovery_time(r)
            cells.append(f"{trig} {post(r):5.1f}/s ({'never' if rt is None else str(rt) + ' s':>6})")
        note.append(f"{name:24} " + "   ".join(cells))
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: a service with a queue, timeouts and retries", m1),
    (2, "Milestone 2: a metastable failure", m2),
    (3, "Milestone 3: deadline-aware shedding and LIFO", m3),
    (4, "Milestone 4: an AIMD concurrency limit", m4),
    (5, "Milestone 5: retry budget, client throttle, recovery", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 5 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
