"""Self-check for Lab 4: Queues, Load Tests & Coordinated Omission.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 3     # milestone 4, replaying ONLY seed 3

Everything is simulated: time is a number, every random draw comes from a seeded
random.Random, nothing sleeps and nothing touches the network. Every run gives
identical numbers and the whole check finishes in well under a minute. Statistical
checks use fixed seeds and generous tolerances; when one fails it prints the seed.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
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


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


make_service, simulate = mod.make_service, mod.simulate


def mean(xs):
    return sum(xs) / len(xs)


# --------------------------------------------------------------------------------------
def m1():
    det = lambda x: make_service("det", x)
    # one job by hand: arrives at 1/lam, takes 2 s, alone in the system
    r = simulate(1.0, det(2.0), 1, 1, 1, "regular")
    j = r.jobs[0]
    assert near(j.arrival, 1.0) and near(j.start, 1.0) and near(j.finish, 3.0), \
        f"a lone job with regular arrivals (gap 1 s) and service 2 s: arrival 1, start 1, finish 3; got {j.arrival}, {j.start}, {j.finish}"
    assert near(r.area, 2.0) and near(r.horizon, 3.0), f"area under N(t) should be 2.0 (one job for 2 s) and horizon 3.0; got {r.area}, {r.horizon}"
    # one server, jobs arrive every 0.5 s but take 1 s: waits grow by 0.5 each
    r = simulate(2.0, det(1.0), 1, 20, 1, "regular")
    assert near(r.jobs[10].wait, 5.0, 1e-6), f"job 10 should have waited 10 x 0.5 = 5.0 s behind its predecessors; got {r.jobs[10].wait}"
    # two servers absorb exactly that load
    r = simulate(2.0, det(1.0), 2, 20, 1, "regular")
    assert all(j.wait < 1e-9 for j in r.jobs), "two servers, one arrival per 0.5 s, 1 s of work each: nobody waits"
    # invariants on a random run
    for s in seeds(range(1, 4)):
        for c in (1, 3):
            r = simulate(2.5 * c, make_service("exp", 0.35), c, 3000, s)
            assert len(r.jobs) == 3000, f"seed {s}: {len(r.jobs)} jobs simulated instead of 3000"
            prev = 0.0
            for i, j in enumerate(r.jobs):
                assert j.arrival >= prev, f"seed {s}: arrivals must be in increasing order (job {i})"
                prev = j.arrival
                assert j.start >= j.arrival - 1e-12, f"seed {s}: job {i} started before it arrived"
                assert near(j.finish, j.start + j.service), f"seed {s}: job {i} finish != start + service"
            starts = [j.start for j in r.jobs]
            assert starts == sorted(starts), f"seed {s}: FIFO violated: a later arrival started before an earlier one"
            ev = sorted([(j.start, 1) for j in r.jobs] + [(j.finish, -1) for j in r.jobs], key=lambda e: (e[0], e[1]))
            cur = peak = 0
            for _, d in ev:
                cur += d
                peak = max(peak, cur)
            assert peak <= c, f"seed {s}: {peak} jobs in service at once with only {c} servers"
    # arrival process
    r = simulate(50.0, det(0.001), 1, 40000, 7)
    gaps = [b.arrival - a.arrival for a, b in zip(r.jobs, r.jobs[1:])]
    m = mean(gaps)
    cv2 = mean([(g - m) ** 2 for g in gaps]) / m ** 2
    assert abs(m * 50.0 - 1.0) < 0.03, f"mean gap should be 1/lam = 0.02 s; got {m:.4f}"
    assert 0.9 < cv2 < 1.1, f"Poisson gaps are exponential: squared coefficient of variation should be about 1; got {cv2:.2f}"
    r = simulate(50.0, det(0.001), 1, 1000, 7, "regular")
    gaps = [b.arrival - a.arrival for a, b in zip(r.jobs, r.jobs[1:])]
    assert max(gaps) - min(gaps) < 1e-9 and near(gaps[0], 0.02), "regular arrivals have a constant gap of 1/lam"
    # determinism and common random numbers
    a = simulate(5.0, make_service("exp", 0.1), 2, 500, 11)
    b = simulate(5.0, make_service("exp", 0.1), 2, 500, 11)
    assert [j.finish for j in a.jobs] == [j.finish for j in b.jobs], "the same seed must give the same run"
    c = simulate(5.0, make_service("hyper4", 0.1), 2, 500, 11)
    assert [j.arrival for j in a.jobs] == [j.arrival for j in c.jobs], "arrivals must not depend on the service distribution (use separate random streams)"
    d = simulate(5.0, make_service("exp", 0.1), 2, 500, 12)
    assert [j.arrival for j in a.jobs] != [j.arrival for j in d.jobs], "a different seed must give different arrivals"
    return "the simulator conserves jobs, respects c servers and FIFO order, and is reproducible"


def m2():
    assert near(mod.mm1_sojourn(8.0, 10.0), 0.5), "M/M/1 with lam=8, mu=10: W = 1/(10-8) = 0.5"
    try:
        mod.mm1_sojourn(10.0, 10.0)
        raise AssertionError("an unstable queue (lam >= mu) has no steady state: raise ValueError")
    except ValueError:
        pass
    assert near(mod.erlang_c(1, 0.5), 0.5), "with one server the chance of waiting is rho: C(1, 0.5) = 0.5"
    assert near(mod.erlang_c(2, 1.0), 1.0 / 3.0), "C(2, 1) = 1/3"
    assert abs(mod.erlang_c(4, 3.2) - 0.59643247) < 1e-6, f"C(4, 3.2) = 0.596432; got {mod.erlang_c(4, 3.2)}"
    big = mod.erlang_c(500, 480.0)
    assert 0.0 < big < 1.0, f"c = 500 must not overflow (compute the terms iteratively); got {big}"
    assert near(mod.mmc_wait(8.0, 10.0, 1), 0.4), "M/M/1 wait in queue = rho/(mu - lam) = 0.8/2 = 0.4"
    assert abs(mod.mmc_wait(34.0, 10.0, 4) - 0.114886) < 1e-5, f"M/M/4, lam=34, mu=10: Wq = 0.114886; got {mod.mmc_wait(34.0, 10.0, 4)}"
    cases = [("M/M/1 rho=0.5", 5.0, 10.0, 1), ("M/M/1 rho=0.7", 7.0, 10.0, 1), ("M/M/2 rho=0.6", 12.0, 10.0, 2), ("M/M/4 rho=0.85", 34.0, 10.0, 4)]
    out = []
    for name, lam, mu, c in cases:
        per = []
        for s in seeds((1, 2, 3)):
            r = mod.simulate(lam, make_service("exp", 1.0 / mu), c, 150000, s)
            per.append(r.stats()[1])
            L, lw = mod.littles_law(r)
            assert abs(L - lw) / L < 0.001, f"{name} seed {s}: Little's law L = lambda*W: L={L:.4f} but lambda*W={lw:.4f}"
        theory = mod.mmc_wait(lam, mu, c) + 1.0 / mu
        got = mean(per)
        assert abs(got - theory) / theory < 0.05, (f"{name}: simulated mean time in system {got:.4f} vs formula {theory:.4f} "
                                                  f"(more than 5% apart); per seed {[round(x, 4) for x in per]}")
        out.append(f"{name:15} formula {theory:.4f}  simulated {got:.4f}  ({100 * (got / theory - 1):+.1f}%)")
    return "\n".join(out)


def m3():
    assert near(mod.kingman_wq(0.8, 1.0, 1.0, 1.0), 4.0), "M/M/1 at rho=0.8: Wq = 4 service times"
    assert near(mod.kingman_wq(0.5, 0.0, 0.0, 2.0), 0.0), "no variability anywhere: no waiting"
    assert near(mod.kingman_wq(0.9, 1.0, 4.0, 0.1), 9.0 * 2.5 * 0.1), "rho=0.9, ca2=1, cs2=4, tau=0.1: 9 * 2.5 * 0.1"
    kinds = ["det", "erlang2", "exp", "hyper4"]
    rows = mod.kingman_table(0.8, kinds, 1.0, 60000, tuple(seeds((1, 2, 3))), "poisson")
    assert [r[0] for r in rows] == kinds and all(len(r) == 4 for r in rows), "kingman_table returns (kind, cs2, simulated, predicted) per kind"
    waits = [r[2] for r in rows]
    assert waits == sorted(waits) and len(set(waits)) == 4, f"waiting time must grow with service variability at fixed utilisation: {[round(w, 2) for w in waits]}"
    for kind, cs2, got, want in rows:
        assert abs(got - want) / want < 0.12, f"{kind} (cs2={cs2}): simulated wait {got:.2f} vs Kingman {want:.2f} service times (more than 12% apart)"
    assert 4.0 < waits[3] / waits[0] < 6.5, f"hyper4 should wait about (1+4)/(1+0) = 5 times as long as det; got {waits[3] / waits[0]:.1f}"
    reg = mod.kingman_table(0.8, ["exp", "hyper4"], 1.0, 60000, tuple(seeds((1, 2, 3))), "regular")
    pois = {r[0]: r[2] for r in rows}
    for kind, cs2, got, want in reg:
        assert got < pois[kind], f"{kind}: smoothing the arrivals must reduce the wait (regular {got:.2f} vs Poisson {pois[kind]:.2f})"
        assert abs(got - want) / want < 0.25, f"{kind} with regular arrivals: simulated {got:.2f} vs Kingman {want:.2f} (more than 25% apart; Kingman is rougher here)"
    det_reg = mod.kingman_table(0.8, ["det"], 1.0, 20000, (1,), "regular")[0]
    assert det_reg[2] < 1e-6, f"regular arrivals and constant service at rho < 1: nobody ever waits; got {det_reg[2]}"
    out = [f"rho = 0.8, wait in queue (in service times), Poisson arrivals:"]
    for kind, cs2, got, want in rows:
        out.append(f"  {kind:8} cs2={cs2:<4}  simulated {got:6.2f}   Kingman {want:6.2f}")
    out.append("  regular arrivals: " + ", ".join(f"{k} {g:.2f} (Kingman {w:.2f})" for k, _, g, w in reg))
    return "\n".join(out)


def m4():
    P = mod.percentile
    xs = list(range(1, 101))
    assert P(xs, 50) == 50 and P(xs, 99) == 99 and P(xs, 100) == 100 and P(xs, 1) == 1, "nearest-rank percentiles of 1..100"
    assert P([4, 1, 3, 2], 50) == 2 and P([4, 1, 3, 2], 75) == 3, "sort first: p50 of [1,2,3,4] is rank ceil(0.5*4)=2 -> 2, p75 is rank 3 -> 3"
    assert P([7.5], 99) == 7.5, "one sample: every percentile is that sample"
    ys = [3, 1, 2]
    P(ys, 50)
    assert ys == [3, 1, 2], "percentile must not reorder the caller's list"
    # co_correct by hand
    got = mod.co_correct([1.0], 0.25)
    assert len(got) == 4 and all(any(near(g, w, 1e-9) for g in got) for w in (1.0, 0.75, 0.5, 0.25)), f"co_correct([1.0], 0.25) = [1.0, 0.75, 0.5, 0.25]; got {got}"
    assert mod.co_correct([0.1, 0.2], 0.25) == [0.1, 0.2], "latencies shorter than the interval omit nothing"
    got = sorted(mod.co_correct([0.9], 0.25))
    assert len(got) == 4 and near(got[0], 0.15, 1e-9), f"co_correct([0.9], 0.25) = [0.9, 0.65, 0.4, 0.15]; got {got}"
    orig = [1.0, 0.1]
    mod.co_correct(orig, 0.25)
    assert orig == [1.0, 0.1], "co_correct must return a new list"
    # open loop measures from the intended time: a stall of [1, 2) hits requests intended at 1.0 .. 1.9
    stalls = [(1.0, 2.0)]
    srv = mod.StallingServer(stalls, mean_service=1e-6, seed=1)
    lats = mod.run_open(srv, 10.0, 3.0)
    assert len(lats) == 30, f"3 s at 10 requests/s is 30 requests; got {len(lats)}"
    for i in range(10, 20):
        want = 2.0 - i / 10.0
        assert abs(lats[i] - want) < 0.01, (f"the request intended at t={i / 10:.1f} is stuck until the stall ends at t=2.0: "
                                           f"latency should be about {want:.1f} s, got {lats[i]:.3f}")
    assert max(lats[:10]) < 0.01 and max(lats[21:]) < 0.01, "requests outside the stall are fast"
    # closed loop: one user, a 10 s stall, 0.1 s think time: the user cannot send during the stall
    srv = mod.StallingServer([(10.0, 20.0)], mean_service=1e-6, seed=1)
    lats = mod.run_closed(srv, 1, 0.1, 40.0, 1)
    assert 230 < len(lats) < 340, (f"one user thinking 0.1 s sends about 10/s, but is blocked for the 10 s stall: expect about 300 "
                                  f"requests in 40 s, got {len(lats)} (an open-loop sender would make 400)")
    assert sum(1 for x in lats if x > 1.0) <= 2, "only the one request caught by the stall is slow"
    # the experiment
    rows = []
    for s in seeds((1, 2, 3, 4)):
        dur = 200.0
        stalls = mod.make_stalls(s, dur)
        closed = mod.run_closed(mod.StallingServer(stalls, 0.005, s), 5, 0.045, dur, s)
        opened = mod.run_open(mod.StallingServer(stalls, 0.005, s), 100.0, dur)
        fixed = mod.co_correct(closed, 0.05)
        pc, po, pf = P(closed, 99), P(opened, 99), P(fixed, 99)
        assert len(opened) == int(dur * 100), f"seed {s}: open loop should send exactly 100/s x 200 s = 20000 requests, sent {len(opened)}"
        assert len(closed) < 0.95 * len(opened), f"seed {s}: the closed loop should send fewer requests (it waits during stalls): {len(closed)} vs {len(opened)}"
        assert pc < 0.1, f"seed {s}: the closed loop's p99 hides the stalls: expected under 100 ms, got {pc * 1000:.0f} ms"
        assert po > 0.7, f"seed {s}: the open loop's p99 (from intended send times) should show the stalls: expected over 700 ms, got {po * 1000:.0f} ms"
        assert po > 10 * pc, f"seed {s}: closed p99 {pc * 1000:.0f} ms vs open p99 {po * 1000:.0f} ms: the gap should be more than 10x"
        assert 0.75 * po < pf < 1.25 * po, f"seed {s}: the corrected closed-loop p99 {pf * 1000:.0f} ms should land within 25% of the open loop's {po * 1000:.0f} ms"
        rows.append((s, pc, po, pf))
    out = ["p99 latency of the same stalling server (1 s stall every 10 s), in ms:"]
    out.append("seed   closed loop   open loop (intended time)   closed + correction")
    for s, a, b, c in rows:
        out.append(f"{s:>4}   {a * 1000:>11.0f}   {b * 1000:>25.0f}   {c * 1000:>19.0f}")
    return "\n".join(out)


def m5():
    S = make_service("exp", 0.01)             # one server, 10 ms jobs: capacity 100/s
    rates = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 95.0]
    pts = mod.sweep(rates, S, 1, 40000, 1)
    assert [p[0] for p in pts] == rates and all(len(p) == 3 for p in pts), "sweep returns (rate, p50, p99) for every rate"
    p99 = [p[2] for p in pts]
    assert p99 == sorted(p99) and len(set(p99)) == len(p99), f"p99 must rise with the arrival rate: {[round(x, 3) for x in p99]}"
    for r, p50, q99 in pts:
        want = math.log(100.0) / (100.0 - r)
        assert abs(q99 - want) / want < 0.2, f"rate {r:g}: simulated p99 {q99:.3f} s vs M/M/1 theory ln(100)/(mu - lam) = {want:.3f} s (more than 20% apart)"
    knee = mod.find_knee([(r, q) for r, _, q in pts])
    assert 55 <= knee <= 88, f"the knee of the M/M/1 p99 curve should sit at 55-88% of capacity; you report {knee}"
    assert mod.find_knee([(0, 0), (1, 1), (2, 2)]) in (0, 1, 2), "find_knee must return one of the rates"
    flat_then_up = [(r, 1.0 if r < 8 else 1.0 + 20 * (r - 7)) for r in range(11)]
    assert mod.find_knee(flat_then_up) in (7, 8), f"a curve that is flat until 7 and then climbs has its knee at 7 or 8; got {mod.find_knee(flat_then_up)}"
    out = []
    for slo, theory in ((0.2, 100 - math.log(100) / 0.2), (0.1, 100 - math.log(100) / 0.1)):
        for s in seeds((1, 2, 3)):
            got = mod.max_rate_under_slo(slo, S, 1, 5.0, 99.0, n_jobs=40000, seed=s)
            assert abs(got - theory) / theory < 0.06, (f"SLO p99 <= {slo * 1000:.0f} ms, seed {s}: max rate {got:.1f}/s vs M/M/1 theory "
                                                      f"{theory:.1f}/s (more than 6% apart)")
        out.append(f"p99 <= {slo * 1000:3.0f} ms: max rate {got:5.1f} req/s of a 100 req/s server (theory {theory:.1f}), i.e. {got:.0f}% utilisation")
    sat = mod.saturation_throughput(50, 0.005)
    assert abs(sat - 200.0) / 200.0 < 0.04, f"50 users with no think time keep a 5 ms server busy: throughput should be about 200/s; got {sat:.1f}"
    server = mod.StallingServer([], 0.005, 1)
    lats = mod.run_closed(server, 50, 0.0, 60.0, 1)
    X = len(lats) / 60.0
    N = X * mean(lats)
    assert abs(N - 50.0) / 50.0 < 0.03, f"Little's law for a closed loop: N = X * R; got {N:.1f} for 50 users"
    out.append(f"knee of the p99 curve at {knee:g} req/s; saturation (closed loop, 50 users) at {sat:.0f} req/s; X*R = {N:.1f} = N users")
    return "\n".join(out)


MILESTONES = [
    (1, "Milestone 1: a discrete-event queue simulator", m1),
    (2, "Milestone 2: validate against M/M/1, Erlang C and Little's law", m2),
    (3, "Milestone 3: Kingman, variability multiplies the wait", m3),
    (4, "Milestone 4: closed loop vs open loop, coordinated omission", m4),
    (5, "Milestone 5: saturation, the knee and the SLO", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 4 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
