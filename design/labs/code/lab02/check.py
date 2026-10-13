"""Self-check for Lab 2: Rate Limiters.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 4 7     # milestone 4, replaying ONLY seed 7

Everything is simulated: time is a number that the tests move by hand or that the event loop
advances, every random draw comes from a seeded random.Random, nothing sleeps and nothing
touches the network. Every run gives identical numbers and the whole check takes a few
seconds. Property checks run many seeds; when one fails it prints the seed so you can replay it.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time
from collections import deque

T0 = time.time()
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
D = 20.0          # simulated seconds per global/local run
W = 1.0           # window length used throughout


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
        print(f"  ✘ {name}: " + str(e).replace("\n", "\n      "))
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


# ------------------------------------------------------------------------------------
# Trusted helpers: the check never relies on YOUR milestone-3 helpers for its own verdicts
# ------------------------------------------------------------------------------------
Q = 1.0 / 1024.0


def trace(kind, seed, duration, rate):
    """Our own trace generator (same kinds as make_trace), on the 1/1024 s grid so arithmetic is exact."""
    rng = random.Random(seed)
    snap = lambda t: math.floor(t / Q) * Q
    out = []
    if kind == "steady":
        n = int(rate * duration)
        out = [snap(i * duration / n) for i in range(n)]
    elif kind == "poisson":
        t = rng.expovariate(rate)
        while t < duration:
            out.append(snap(t))
            t += rng.expovariate(rate)
    elif kind == "bursty":
        size = max(1, int(rate / 4))
        t = rng.expovariate(4.0)
        while t < duration:
            out += [snap(t + rng.uniform(0, 0.05)) for _ in range(size)]
            t += rng.expovariate(4.0)
    elif kind == "edges":
        half = max(1, int(rate / 2))
        for k in range(1, int(duration)):
            for _ in range(half):
                out.append(snap(k - rng.uniform(0.001, 0.1)))
                out.append(snap(k + rng.uniform(0.0, 0.1)))
    return sorted(t for t in out if 0 <= t < duration)


def peak(times, window):
    """Most points in any half-open interval of length `window` (trusted)."""
    best, i = 0, 0
    for j, t in enumerate(times):
        while t - times[i] >= window:
            i += 1
        best = max(best, j - i + 1)
    return best


class RefLog:
    def __init__(self, limit, window, clock):
        self.limit, self.window, self.clock, self.log = limit, window, clock, deque()

    def allow(self):
        now = self.clock.now()
        while self.log and self.log[0] <= now - self.window:
            self.log.popleft()
        if len(self.log) < self.limit:
            self.log.append(now)
            return True
        return False


class RefBucket:
    def __init__(self, rate, cap, clock):
        self.rate, self.cap, self.clock, self.tok, self.last = rate, cap, clock, float(cap), clock.now()

    def allow(self):
        now = self.clock.now()
        self.tok = min(self.cap, self.tok + (now - self.last) * self.rate)
        self.last = now
        if self.tok >= 1.0 - 1e-9:
            self.tok -= 1.0
            return True
        return False


def drive(limiter, clock, times):
    """Trusted replay: returns the list of decisions."""
    out = []
    for t in times:
        clock.set(t)
        out.append(bool(limiter.allow()))
    return out


def admitted(times, decisions):
    return [t for t, ok in zip(times, decisions) if ok]


def replay_cmd(n, seed):
    return f"(replay: python3 check.py {target} {n} {seed})"


# ====================================================================================
# Milestone 1: token bucket
# ====================================================================================
def m1():
    c = mod.ManualClock()
    b = mod.TokenBucket(rate=10, capacity=10, clock=c)
    assert abs(b.tokens() - 10) < 1e-9, f"a new bucket starts full: tokens() should be 10, got {b.tokens()}"
    got = sum(b.allow() for _ in range(25))
    assert got == 10, f"a burst of 25 at the same instant should admit exactly the capacity (10), admitted {got}"
    assert abs(b.retry_after() - 0.1) < 1e-6, f"empty bucket at 10 tokens/s: the next token is 0.1 s away, retry_after() = {b.retry_after()}"
    assert abs(b.retry_after(5) - 0.5) < 1e-6, f"5 tokens at 10/s take 0.5 s, retry_after(5) = {b.retry_after(5)}"
    c.advance(0.5)
    assert abs(b.tokens() - 5) < 1e-6, f"after 0.5 s at 10/s there should be 5 tokens, got {b.tokens()}"
    assert b.allow(cost=5) and not b.allow(), "cost=5 should spend five tokens at once, leaving nothing"
    assert b.retry_after(0) == 0.0 or abs(b.retry_after(0)) < 1e-9, "retry_after for cost 0 is 0"
    c.advance(1000.0)
    assert abs(b.tokens() - 10) < 1e-9, f"idle time must not bank more than the capacity (10), tokens() = {b.tokens()}"
    before = b.tokens()
    assert not b.allow(cost=11), "a request bigger than the capacity can never be admitted"
    assert abs(b.tokens() - before) < 1e-9, "a rejected request must not spend tokens"
    c.set(500.0)    # the clock steps BACK by 500 s: no free tokens, and no freeze afterwards
    for _ in range(10):
        b.allow()
    assert not b.allow(), "stepping the clock backwards must not mint tokens"
    c.advance(0.2)
    assert b.allow(), "after a backwards step the bucket must keep refilling from the new time (0.2 s -> 2 tokens)"
    # decisions equal the reference bucket on random traces; bounds hold in every window
    trials = 0
    for seed in seeds(range(1, 41)):
        rng = random.Random(seed)
        rate, cap = rng.choice([5, 10, 20, 50]), rng.choice([1, 5, 10, 20])
        kind = rng.choice(["poisson", "bursty", "edges", "steady"])
        tr = trace(kind, seed, D, rng.choice([8, 15, 40, 90]))
        c1, c2 = mod.ManualClock(), mod.ManualClock()
        got = drive(mod.TokenBucket(rate, cap, c1), c1, tr)
        want = drive(RefBucket(rate, cap, c2), c2, tr)
        if got != want:
            i = next(i for i, (a, b2) in enumerate(zip(got, want)) if a != b2)
            raise AssertionError(f"seed {seed}: rate={rate} capacity={cap} on a {kind} trace, request #{i} at t={tr[i]:.4f}: "
                                 f"you said {got[i]}, the reference bucket says {want[i]} {replay_cmd(1, seed)}")
        adm = admitted(tr, got)
        for w in (0.25, 1.0, 3.0):
            assert peak(adm, w) <= cap + rate * w + 1e-9, \
                f"seed {seed}: {peak(adm, w)} admitted in a {w}s window, more than capacity + rate x window = {cap + rate * w}"
        trials += 1
    return f"burst = capacity, refill = rate, retry_after, clock stepping back; matched a reference bucket on {trials} random traces"


# ====================================================================================
# Milestone 2: sliding windows
# ====================================================================================
def m2():
    c = mod.ManualClock()
    lg = mod.SlidingWindowLog(3, 1.0, c)
    seq = [(0.0, True), (0.25, True), (0.5, True), (0.75, False), (1.0, True), (1.0, False), (1.25, True), (1.5, True), (1.5, False)]
    for t, want in seq:
        c.set(t)
        got = lg.allow()
        assert got == want, f"SlidingWindowLog(limit 3, window 1): request at t={t} should be {want}, you said {got} (a request at t counts requests in (t-1, t])"
    c = mod.ManualClock()
    ct = mod.SlidingWindowCounter(10, 1.0, c)
    c.set(0.0)
    n0 = sum(ct.allow() for _ in range(15))
    assert n0 == 10, f"SlidingWindowCounter(limit 10): 15 requests at t=0 should admit 10, admitted {n0}"
    c.set(1.5)
    est = ct.estimate()
    assert abs(est - 5.0) < 1e-9, f"at t=1.5 the previous window (10) is half-weighted: estimate() should be 5.0, got {est}"
    n1 = sum(ct.allow() for _ in range(15))
    assert n1 == 5, f"at t=1.5 only 5 of 15 should fit (5 weighted + 5 new = 10), admitted {n1}"
    c.set(5.0)
    assert abs(ct.estimate()) < 1e-9, f"after a gap of several windows nothing is remembered: estimate() = {ct.estimate()}"
    assert ct.allow(), "after a long gap the counter must admit again"
    # the fixed window (given) lets 2x through at a boundary; the log never does
    fw_c, lg_c = mod.ManualClock(), mod.ManualClock()
    tr = [0.9 + 0.001 * i for i in range(0)] + [round(0.9 + i * Q * 4, 6) for i in range(20)] + [round(1.0 + i * Q * 4, 6) for i in range(20)]
    tr = sorted(set(tr))
    fw = drive(mod.FixedWindow(10, 1.0, fw_c), fw_c, tr)
    lg2 = drive(mod.SlidingWindowLog(10, 1.0, lg_c), lg_c, tr)
    assert peak(admitted(tr, fw), 1.0) > 10 >= peak(admitted(tr, lg2), 1.0), \
        "the given FixedWindow should admit more than the limit around a boundary and your log never"
    # the log is exact: identical to the reference on random traces
    n = 0
    for seed in seeds(range(1, 31)):
        rng = random.Random(seed)
        limit = rng.choice([3, 10, 25, 60])
        kind = rng.choice(["poisson", "bursty", "edges", "steady"])
        tr = trace(kind, seed, D, rng.choice([5, 12, 40, 100]))
        c1, c2 = mod.ManualClock(), mod.ManualClock()
        got = drive(mod.SlidingWindowLog(limit, 1.0, c1), c1, tr)
        want = drive(RefLog(limit, 1.0, c2), c2, tr)
        if got != want:
            i = next(i for i, (a, b2) in enumerate(zip(got, want)) if a != b2)
            raise AssertionError(f"seed {seed}: SlidingWindowLog(limit {limit}) on a {kind} trace, request #{i} at t={tr[i]}: "
                                 f"you said {got[i]}, an exact log says {want[i]} {replay_cmd(2, seed)}")
        n += 1
    return f"log matched an exact reference on {n} random traces; counter estimate and weighting match the hand values"


# ====================================================================================
# Milestone 3: property tests
# ====================================================================================
def m3():
    # --- your helpers, by hand
    assert mod.max_in_window([], 1.0) == 0, "max_in_window([]) is 0"
    assert mod.max_in_window([0.0, 0.5, 1.0], 1.0) == 2, "half-open windows: 0.0 and 1.0 are NOT in the same window of length 1"
    assert mod.max_in_window([0.0, 0.25, 0.5, 0.75], 1.0) == 4, "four points inside one second"
    assert mod.max_in_window([0.0, 0.9, 1.0, 1.8, 2.5], 1.0) == 3, "0.9, 1.0 and 1.8 fit in [0.9, 1.9)"
    assert mod.max_in_window([5.0] * 7, 0.5) == 7, "simultaneous points all count"
    c = mod.ManualClock()

    class Every2:
        n = 0

        def allow(self):
            Every2.n += 1
            return Every2.n % 2 == 0
    got = mod.replay(Every2(), c, [0.5, 1.0, 1.5, 2.0])
    assert list(got) == [1.0, 2.0] and c.now() == 2.0, f"replay should set the clock to each time, return the times that were admitted ([1.0, 2.0]); got {got}, clock {c.now()}"
    for kind in ("steady", "poisson", "bursty", "edges"):
        a = mod.make_trace(kind, 7, 10.0, 40)
        b = mod.make_trace(kind, 7, 10.0, 40)
        d = mod.make_trace(kind, 8, 10.0, 40)
        assert a == b, f"make_trace('{kind}', seed, ...) must be deterministic"
        assert list(a) == sorted(a) and all(0 <= t < 10.0 for t in a), f"make_trace('{kind}') must be sorted and inside [0, duration)"
        assert 0.5 * 400 <= len(a) <= 1.6 * 400, f"make_trace('{kind}', duration 10, rate 40) should have about 400 requests, has {len(a)}"
        if kind != "steady":
            assert a != d, f"make_trace('{kind}') should differ between seeds"
        assert all(abs(t / Q - round(t / Q)) < 1e-6 for t in a), f"make_trace('{kind}') times must be multiples of 1/1024 s"
    try:
        mod.make_trace("nonsense", 1, 5.0, 10)
        raise AssertionError("make_trace of an unknown kind should raise ValueError")
    except ValueError:
        pass
    # the adversarial trace must actually hurt the fixed window
    worst = 0.0
    for seed in seeds(range(1, 6)):
        tr = mod.make_trace("edges", seed, 20.0, 120)
        c = mod.ManualClock()
        adm = mod.replay(mod.FixedWindow(50, 1.0, c), c, tr)
        worst = max(worst, peak(adm, 1.0) / 50)
    assert worst >= 1.6, f"your 'edges' trace should push the fixed window to >= 1.6x its limit in some window; best was {worst:.2f}x"
    # --- the properties, on OUR traces and OUR measurement
    log_worst = ctr_worst = tb_worst = 0.0
    ratios = []
    runs = 0
    for seed in seeds(range(1, 41)):
        rng = random.Random(seed)
        limit = rng.choice([10, 20, 50])
        rate = limit * rng.choice([1.2, 1.5, 3, 6])
        for kind in ("steady", "poisson", "bursty", "edges"):
            tr = trace(kind, seed, D, rate)
            if len(tr) < 5:
                continue
            c = mod.ManualClock()
            a_log = admitted(tr, drive(mod.SlidingWindowLog(limit, W, c), c, tr))
            p = peak(a_log, W)
            assert p <= limit, f"seed {seed}: SlidingWindowLog(limit {limit}) admitted {p} in one window on a {kind} trace; exact means never more than the limit {replay_cmd(3, seed)}"
            log_worst = max(log_worst, p / limit)
            c = mod.ManualClock()
            a_ctr = admitted(tr, drive(mod.SlidingWindowCounter(limit, W, c), c, tr))
            p = peak(a_ctr, W)
            assert p < 2 * limit, f"seed {seed}: SlidingWindowCounter(limit {limit}) admitted {p} (>= 2x) in one window on a {kind} trace; the weighted estimate is bounded by 2x {replay_cmd(3, seed)}"
            ctr_worst = max(ctr_worst, p / limit)
            if kind in ("poisson", "steady"):
                ratios.append((seed, kind, len(a_ctr) / max(1, len(a_log))))
            cap = rng.choice([1, 5, limit])
            c = mod.ManualClock()
            a_tb = admitted(tr, drive(mod.TokenBucket(limit, cap, c), c, tr))
            for w in (0.1, 1.0):
                p = peak(a_tb, w)
                assert p <= cap + limit * w + 1e-9, f"seed {seed}: TokenBucket(rate {limit}, capacity {cap}) admitted {p} in a {w}s window on a {kind} trace; the bound is capacity + rate x window = {cap + limit * w} {replay_cmd(3, seed)}"
            tb_worst = max(tb_worst, p / limit)
            runs += 1
        # a burst after a long idle period: exactly the capacity
        cap = rng.choice([3, 8, 15])
        c = mod.ManualClock()
        tb = mod.TokenBucket(rate=limit, capacity=cap, clock=c)
        c.set(100.0 + rng.random())
        n = sum(tb.allow() for _ in range(cap * 3))
        assert n == cap, f"seed {seed}: a burst of {cap * 3} after a long idle period should admit exactly the capacity {cap}, admitted {n} {replay_cmd(3, seed)}"
    for seed, kind, r in ratios:
        assert 0.85 <= r <= 1.15, f"seed {seed}: on a {kind} trace the counter admitted {r:.0%} of what the exact log did; smooth traffic should be within 15% {replay_cmd(3, seed)}"
    mean_ratio = sum(r for _, _, r in ratios) / len(ratios)
    return (f"{runs} (seed, trace) runs.  worst admitted in any 1 s window / limit:  log {log_worst:.2f}x (exact),  "
            f"counter {ctr_worst:.2f}x (bound < 2x),  fixed window on the 'edges' trace {worst:.2f}x\n"
            f"on smooth traffic the counter admits {mean_ratio:.0%} of what the exact log admits")


# ====================================================================================
# Milestone 4: a global limiter over a shared store
# ====================================================================================
def m4():
    sim = mod.Sim()
    st = mod.Store(sim)
    assert st.get("k") == 0, "get of a missing key is 0"
    assert [st.incr("k", ttl=1.0) for _ in range(3)] == [1, 2, 3], "incr creates the key at 1 and then counts up"
    assert st.get("k") == 3, "get returns the current value"
    assert st.incr("j", ttl=1.0, by=5) == 5 and st.incr("j", ttl=1.0, by=2) == 7, "incr(by=n) adds n"
    sim.now = 0.9
    assert st.incr("k", ttl=1.0) == 4, "the key is still alive at t=0.9"
    sim.now = 1.0
    assert st.get("k") == 0, "the key was created at t=0 with ttl 1.0, so it is gone at t=1.0 (the TTL is NOT extended by later incrs)"
    assert st.incr("k", ttl=1.0) == 1, "after expiry incr starts again at 1, with a fresh TTL"
    sim.now = 1.9
    assert st.get("k") == 1, "the new key lives until t=2.0"
    sim.now = 2.0
    assert st.get("k") == 0, "...and expires then"
    # the atomic limiter: never over the limit, exactly the limit when saturated
    rows = []
    for seed in seeds(range(1, 13)):
        nodes = 2 + seed % 3 * 3
        log = mod.run_global(seed, nodes=nodes, limit=100, rate=400.0, duration=D)
        counts = mod.window_counts(mod.admitted_times(log, by="arrive"), W, D)
        arrivals = len(log)
        assert arrivals > 6000, f"seed {seed}: expected about 8,000 requests, the harness produced {arrivals}"
        assert max(counts) <= 100, f"seed {seed}: {nodes} nodes admitted {max(counts)} in one window (limit 100): per-window counts {counts} {replay_cmd(4, seed)}"
        assert all(c == 100 for c in counts[1:-1]), f"seed {seed}: with 4x overload every full window (counted by the time the request arrived, which is when its window is chosen) should admit exactly 100: {counts} {replay_cmd(4, seed)}"
        lat = max(d.t_decide - d.t_arrive for d in log)
        assert lat <= 0.0101, f"seed {seed}: a decision takes one round trip (<= 10 ms here), the slowest took {lat * 1000:.1f} ms {replay_cmd(4, seed)}"
        rows.append((seed, nodes, counts[1]))
    low = mod.run_global(3, nodes=4, limit=100, rate=30.0, duration=D)
    assert all(d.allowed for d in low), "at 30 requests/s against a limit of 100/s nothing should be rejected"
    a = mod.run_global(5, nodes=4)
    b = mod.run_global(5, nodes=4)
    assert a == b, "same seed, same run: the simulation must be deterministic"
    # why atomic matters: the given read-then-write limiter
    racy = []
    for seed in seeds(range(1, 6)):
        counts = mod.window_counts(mod.admitted_times(mod.run_global(seed, nodes=4, limiter="racy")), W, D)
        racy.append(sum(counts[1:-1]) / len(counts[1:-1]) / 100)
    assert min(racy) >= 1.5, f"(harness check) the read-then-write limiter should over-admit badly under network delay; got {racy}"
    return (f"atomic INCR + TTL: exactly 100 admitted in every saturated window, for 2 to 8 nodes, {len(rows)} seeds, 1 round trip per decision\n"
            f"the given read-then-write limiter admits {sum(racy) / len(racy):.1f}x the limit under the same delays")


# ====================================================================================
# Milestone 5: local limiters with sync, failure policy, clock skew
# ====================================================================================
def pct(x):
    return f"{x + 0.0:+.0%}".replace("-0%", "+0%")


def avg(f, seed_list):
    v = [f(s) for s in seed_list]
    return sum(v) / len(v)


def m5():
    S = seeds(range(1, 6))
    note = []
    # 5a. over-admission vs sync interval
    Ts = (0.01, 0.1, 0.5, 2.0)
    opt, con, skw = {}, {}, {}
    for T in Ts:
        opt[T] = avg(lambda s: mod.over_admission(mod.admitted_times(mod.run_local(s, sync_interval=T)), 100, W, D), S)
        con[T] = avg(lambda s: mod.over_admission(mod.admitted_times(mod.run_local(s, sync_interval=T, mode="conservative")), 100, W, D), S)
        skw[T] = avg(lambda s: mod.over_admission(mod.admitted_times(mod.run_local(s, sync_interval=T, mode="conservative", weights=[1] + [0] * 7)), 100, W, D), S)
    for a, b in zip(Ts, Ts[1:]):
        assert opt[b] > opt[a] - 0.02, f"over-admission should grow with the sync interval: T={a}: {opt[a]:+.2f}, T={b}: {opt[b]:+.2f} (seeds {S[0]}..{S[-1]})"
    assert opt[0.01] < 0.15, f"syncing every 10 ms should keep over-admission under 15% (8 nodes, 4x overload), got {opt[0.01]:+.0%}"
    assert opt[2.0] > 1.5, f"syncing every 2 s (less than once per window) should admit far more than the limit (> +150%), got {opt[2.0]:+.0%}"
    for T in Ts:
        assert con[T] <= opt[T] + 0.02, f"the conservative mode should never over-admit more than the optimistic one: T={T}: {con[T]:+.2f} vs {opt[T]:+.2f}"
    assert con[2.0] < 0.6, f"conservative mode keeps over-admission bounded even with no useful sync (< +60%), got {con[2.0]:+.0%}"
    assert skw[0.5] < -0.3, f"conservative mode under-admits when ALL traffic lands on one node of 8 (should be below -30% at T=0.5 s), got {skw[0.5]:+.0%}"
    skew_opt = avg(lambda s: mod.over_admission(mod.admitted_times(mod.run_local(s, sync_interval=0.5, weights=[1] + [0] * 7)), 100, W, D), S)
    assert abs(skew_opt) < 0.1, f"optimistic mode with all traffic on one node should sit near the limit (+-10%), got {skew_opt:+.0%}"
    note.append("8 nodes, 400 req/s offered against a limit of 100/s (over-admission = admitted / limit - 1, mean over 5 seeds):")
    note.append("  sync every   optimistic   conservative   conservative, all traffic on one node")
    for T in Ts:
        note.append(f"  {T * 1000:>6.0f} ms   {opt[T]:>+9.0%}   {con[T]:>+11.0%}   {skw[T]:>+14.0%}")
    # 5b. the store goes down for 5 s (t = 5..10)
    outage = (5.0, 10.0)
    modes = {}
    for oe in ("open", "closed", "local"):
        per = []
        for s in S:
            log = mod.run_global(s, nodes=4, rate=400.0, on_error=oe, outage=outage)
            c = mod.window_counts(mod.admitted_times(log, by="arrive"), W, D)
            per.append((c, log))
        modes[oe] = per
    for s_i, s in enumerate(S):
        c_open, c_closed, c_local = modes["open"][s_i][0], modes["closed"][s_i][0], modes["local"][s_i][0]
        assert all(c >= 300 for c in c_open[6:9]), f"seed {s}: fail-open should admit (nearly) everything during the outage (~400/window), got {c_open[6:9]} {replay_cmd(5, s)}"
        assert all(c == 0 for c in c_closed[6:9]), f"seed {s}: fail-closed should admit nothing during the outage, got {c_closed[6:9]} {replay_cmd(5, s)}"
        assert all(60 <= c <= 135 for c in c_local[6:9]), f"seed {s}: the local fallback should admit about the limit (60..135 per window), got {c_local[6:9]} {replay_cmd(5, s)}"
        for oe, c in (("open", c_open), ("closed", c_closed), ("local", c_local)):
            assert all(x == 100 for x in c[12:19]), f"seed {s}: after the outage ({oe}) windows should be back to exactly 100: {c[12:19]} {replay_cmd(5, s)}"
        lat = max(d.t_decide - d.t_arrive for d in modes["closed"][s_i][1])
        assert 0.049 <= lat <= 0.0511, f"seed {s}: while the store is down a decision costs the timeout (50 ms), slowest was {lat * 1000:.1f} ms {replay_cmd(5, s)}"
    mean = lambda oe: sum(sum(c[6:9]) / 3 for c, _ in modes[oe]) / len(S)
    note.append(f"store down for 5 s, 400 req/s offered, limit 100/s: admitted per second during the outage: "
                f"fail-open {mean('open'):.0f}, fail-closed {mean('closed'):.0f}, local fallback {mean('local'):.0f}")
    # 5c. clock skew between nodes
    rows = []
    for sk in (0.0, 0.25, 0.5):
        sks = [0.0, sk / 3, 2 * sk / 3, sk]
        res = {}
        for ts in ("local", "store"):
            logs = [mod.admitted_times(mod.run_global(s, nodes=4, rate=400.0, time_source=ts, skews=sks)) for s in S]
            res[ts] = (sum(mod.over_admission(t, 100, W, D) for t in logs) / len(logs),
                       sum(mod.peak_over_limit(t, 100, W) for t in logs) / len(logs))
        rows.append((sk, res))
    r0, r5 = rows[0][1], rows[-1][1]
    assert abs(r0["local"][0]) < 0.02, f"with no skew the mean over-admission is 0, got {r0['local'][0]:+.2f}"
    assert r5["local"][1] > 1.7, f"nodes whose clocks differ by up to 0.5 s that name windows by their OWN clock should let nearly 2x the limit through in some sliding window (> 1.7x); got {r5['local'][1]:.2f}x"
    assert abs(r5["store"][0]) < 0.03 and r5["store"][1] < 1.5, \
        f"time_source='store' (the store names the window) should be immune to skew: got mean {r5['store'][0]:+.0%}, peak {r5['store'][1]:.2f}x"
    assert r5["local"][1] > r5["store"][1] + 0.4, f"skew should raise the worst sliding-window peak (local {r5['local'][1]:.2f}x vs store {r5['store'][1]:.2f}x)"
    note.append("clock skew across 4 nodes (spread of node clocks), 400 req/s, limit 100/s:  mean over-admission / worst 1 s sliding-window peak")
    for sk, res in rows:
        note.append(f"  skew {sk:>4.2f} s   window named by node clock {pct(res['local'][0]):>5} / {res['local'][1]:.2f}x    "
                    f"named by the store {pct(res['store'][0]):>5} / {res['store'][1]:.2f}x")
    return "\n".join(note)


check(1, "Milestone 1: a token bucket on an injected clock", m1)
check(2, "Milestone 2: sliding-window log and sliding-window counter", m2)
check(3, "Milestone 3: property tests (exact, bounded, burst)", m3)
check(4, "Milestone 4: a global limiter over a shared store", m4)
check(5, "Milestone 5: local limiters + sync, failure policy, clock skew", m5)

print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - T0:.1f} s)")
sys.exit(0 if results and all(results) else 1)
