"""Self-check for Lab 6: Automated Canary Analysis.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 2     # milestone 4, replaying ONLY seed 2

Everything is synthetic and seeded: the samples, the regressions, the daily traffic
curve. There is no real clock and no network, so every run gives identical numbers
and the whole check finishes in well under a minute. Statistical checks use fixed
seeds and generous tolerances; when one fails it prints the seed.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import dataclasses
import importlib
import itertools
import math
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


Regression, Policy = mod.Regression, mod.Policy


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def mean(xs):
    return sum(xs) / len(xs)


def med(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


# --------------------------------------------------------------------------------------
def m1():
    r = random.Random(1)
    lat = mod.gen_latency(r, 20000)
    assert len(lat) == 20000 and min(lat) > 0, "gen_latency returns n positive samples"
    assert abs(med(lat) / 100.0 - 1.0) < 0.03, f"median latency should be about 100 ms; got {med(lat):.1f}"
    logs = [math.log(x) for x in lat]
    m = mean(logs)
    sd = math.sqrt(mean([(v - m) ** 2 for v in logs]))
    assert abs(sd - 0.3) < 0.015, f"the log of the latencies should have spread 0.3; got {sd:.3f}"
    assert abs(med(mod.gen_latency(random.Random(2), 20000, shift=0.2)) / 120.0 - 1.0) < 0.03, "shift=0.2 makes the median 120 ms"
    assert abs(med(mod.gen_latency(random.Random(3), 20000, load=1.5)) / 130.0 - 1.0) < 0.03, "load 1.5 makes things 30% slower (0.6 x 0.5): median 130 ms"
    e = mod.gen_errors(random.Random(4), 20000)
    assert min(e) >= 0.0, "an error rate is never negative"
    assert abs(mean(e) / 0.001 - 1.0) < 0.05, f"the mean error rate should be 0.1%; got {mean(e):.5f}"
    assert abs(mean(mod.gen_errors(random.Random(5), 20000, extra=0.002)) / 0.003 - 1.0) < 0.05, "extra=0.002 gives 0.3% errors"
    assert abs(mean(mod.gen_errors(random.Random(6), 20000, load=1.5)) / 0.0015 - 1.0) < 0.05, "load 1.5 gives 1.5x the errors"
    mem = mod.gen_memory(random.Random(7), 30, 3, leak=0.0)
    assert len(mem) == 90, f"30 minutes x 3 instances = 90 samples; got {len(mem)}"
    assert abs(mean(mem) - 800.0) < 6.0, f"memory without a leak averages 800 MB; got {mean(mem):.1f}"
    mem = mod.gen_memory(random.Random(8), 30, 3, leak=3.0)
    first, last = mean(mem[:3]), mean(mem[-3:])
    assert 60.0 < last - first < 115.0, f"a 3 MB/min leak over 30 minutes: the last minute should be about 87 MB above the first; got {last - first:.0f}"
    assert abs(mean(mem) - (800.0 + 3.0 * 14.5)) < 10.0, "samples are ordered by minute, each minute has one sample per instance"
    for s in seeds((1, 2, 3)):
        d = mod.generate(random.Random(s), Regression(latency=0.3, errors=0.002, leak=3.0))
        assert set(d) == {"latency_ms", "error_rate", "memory_mb"}, f"seed {s}: generate returns one entry per metric"
        assert all(len(b) == 90 and len(c) == 90 for b, c in d.values()), f"seed {s}: 30 min x 3 instances = 90 samples per group"
        clean = mod.generate(random.Random(s), Regression())
        for k in d:
            assert d[k][0] == clean[k][0], f"seed {s}: the baseline must not depend on the regression ({k}); draw it first, in the same order"
        assert med(d["latency_ms"][1]) > med(d["latency_ms"][0]), f"seed {s}: the regressed canary should be slower"
        assert mean(d["error_rate"][1]) > mean(d["error_rate"][0]), f"seed {s}: the regressed canary should have more errors"
        assert mean(d["memory_mb"][1]) > mean(d["memory_mb"][0]) + 20, f"seed {s}: the leaking canary should use more memory"
    a = mod.generate(random.Random(9), Regression(latency=0.1))
    b = mod.generate(random.Random(9), Regression(latency=0.1))
    assert a == b, "the same seed must give the same samples"
    d = mod.generate(random.Random(10), Regression(), 60, 10, load=1.5, baseline_load=0.5)
    assert med(d["latency_ms"][1]) > 1.5 * med(d["latency_ms"][0]), "baseline_load=0.5 vs load=1.5: the baseline is much faster (0.7 vs 1.3)"
    return "seeded latency, error-rate and memory samples, with a latency shift, extra errors and a slow leak"


def pair_count_u(x, y):
    """An independent U: count the pairs, ties as half."""
    return sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in x for b in y)


def tie_free_exact_p(x, y):
    """Exact two-sided p for small samples without ties, by enumerating every split."""
    allv = list(x) + list(y)
    n, nx = len(allv), len(x)
    u_obs = pair_count_u(x, y)
    mean_u = nx * len(y) / 2
    count = total = 0
    for idx in itertools.combinations(range(n), nx):
        xs = [allv[i] for i in idx]
        ys = [allv[i] for i in range(n) if i not in idx]
        u = pair_count_u(xs, ys)
        total += 1
        if abs(u - mean_u) >= abs(u_obs - mean_u) - 1e-9:
            count += 1
    return count / total


def m2():
    ranks, ties = mod.ranks_with_ties([10, 20, 20, 30, 20])
    assert ranks == [1.0, 3.0, 3.0, 5.0, 3.0], f"tied values share the average rank: expected [1, 3, 3, 5, 3], got {ranks}"
    assert sorted(ties) == [1, 1, 3], f"tie group sizes [1, 3, 1]; got {ties}"
    ranks, ties = mod.ranks_with_ties([3.0, 1.0, 2.0])
    assert ranks == [3.0, 1.0, 2.0] and ties == [1, 1, 1], "no ties: ranks follow the sorted order"
    u, z, p = mod.mann_whitney_u([1, 2, 3, 4, 5], [6, 7, 8, 9, 10])
    assert near(u, 0.0) and abs(z - (-2.50672)) < 1e-4 and abs(p - 0.012186) < 1e-5, \
        f"x entirely below y (5 and 5): U = 0, z = (0 - 12.5 + 0.5)/4.787 = -2.507, p = 0.01219; got U={u}, z={z:.5f}, p={p:.6f}"
    u, z, p = mod.mann_whitney_u([19, 22, 16, 29, 24], [20, 11, 17, 12])
    assert near(u, 17.0) and abs(z - 1.5922) < 1e-3 and abs(p - 0.1114) < 1e-3, f"textbook example (U_x = 17, U_y = 3): z = 1.592, p = 0.1114; got U={u}, z={z:.4f}, p={p:.4f}"
    u, z, p = mod.mann_whitney_u([1, 2, 2, 3], [2, 3, 3, 4])
    assert near(u, 3.0) and abs(z - (-1.3657)) < 1e-3 and abs(p - 0.17203) < 1e-3, \
        f"with ties: U = 3, z = -1.3657, p = 0.1720 (the variance needs the tie correction); got U={u}, z={z:.4f}, p={p:.5f}"
    u, z, p = mod.mann_whitney_u([5, 5, 5], [5, 5, 5])
    assert z == 0.0 and p == 1.0, f"all values equal: no evidence, z = 0 and p = 1 (not a division by zero); got z={z}, p={p}"
    u, z, p = mod.mann_whitney_u([3, 1, 2], [6, 5, 4])
    u2, z2, p2 = mod.mann_whitney_u([6, 5, 4], [3, 1, 2])
    assert near(u + u2, 9.0) and near(z, -z2) and near(p, p2), "swapping the groups: U_x + U_y = n_x n_y, z flips sign, p is unchanged"
    # against an independent pair-counting U on random data with many ties
    for s in seeds(range(1, 11)):
        r = random.Random(s)
        x = [round(r.gauss(0, 1), 1) for _ in range(r.randint(5, 40))]
        y = [round(r.gauss(0.3, 1), 1) for _ in range(r.randint(5, 40))]
        u, z, p = mod.mann_whitney_u(x, y)
        assert near(u, pair_count_u(x, y)), f"seed {s}: U = {u} but counting pairs gives {pair_count_u(x, y)}"
        n, nx, ny = len(x) + len(y), len(x), len(y)
        groups = {}
        for v in x + y:
            groups[v] = groups.get(v, 0) + 1
        var = nx * ny / 12.0 * ((n + 1) - sum(t ** 3 - t for t in groups.values()) / (n * (n - 1)))
        diff = u - nx * ny / 2.0
        want_z = 0.0 if diff == 0 else (diff - math.copysign(0.5, diff)) / math.sqrt(var)
        assert abs(z - want_z) < 1e-9, f"seed {s}: z = {z:.6f}, expected {want_z:.6f} (tie-corrected variance, continuity correction)"
    # monotone transforms do not matter: it is a rank test
    r = random.Random(3)
    x = [r.gauss(0, 1) for _ in range(30)]
    y = [r.gauss(0.5, 1) for _ in range(30)]
    a = mod.mann_whitney_u(x, y)
    b = mod.mann_whitney_u([math.exp(3 * v) for v in x], [math.exp(3 * v) for v in y])
    assert abs(a[2] - b[2]) < 1e-12, "applying exp() to every value must not change the result"
    c = mod.mann_whitney_u(x + [1e9], y)
    assert abs(c[2] - mod.mann_whitney_u(x + [1e3], y)[2]) < 1e-12, "an outlier counts as 'the largest', whatever its size"
    # the normal approximation against the exact p-value on small samples
    for s in seeds((1, 2, 3)):
        r = random.Random(s)
        x = [r.random() for _ in range(6)]
        y = [r.random() + 0.5 for _ in range(6)]
        exact = tie_free_exact_p(x, y)
        approx = mod.mann_whitney_u(x, y)[2]
        assert abs(exact - approx) < 0.03, f"seed {s}: exact p {exact:.4f} vs normal approximation {approx:.4f} (n = 6, 6)"
    # calibration: with no difference, p < 0.05 about 5% of the time
    rej = 0
    for s in seeds(range(400)):
        r = random.Random(s)
        x = [round(r.gauss(0, 1), 1) for _ in range(30)]
        y = [round(r.gauss(0, 1), 1) for _ in range(30)]
        rej += mod.mann_whitney_u(x, y)[2] < 0.05
    rate = rej / (1 if ONLY_SEED is not None else 400)
    if ONLY_SEED is None:
        assert 0.03 <= rate <= 0.08, f"under the null, p < 0.05 should happen about 5% of the time over 400 seeds; it happened {rate:.3f}"
    # power: a 0.8-sigma shift with n = 30 is usually detected
    hit = 0
    for s in range(100):
        r = random.Random(1000 + s)
        hit += mod.mann_whitney_u([r.gauss(0.8, 1) for _ in range(30)], [r.gauss(0, 1) for _ in range(30)])[2] < 0.05
    assert hit >= 70, f"a shift of 0.8 sigma with 30 samples per side should be detected at least 70% of the time; got {hit}%"
    return f"U, z and p match hand-worked examples and an independent pair count; null rejection rate {rate:.3f}; power {hit}%"


def m3():
    assert mod.median([3, 1, 2]) == 2 and mod.median([4, 1, 3, 2]) == 2.5 and mod.median([7]) == 7, "median of odd and even lists"
    assert near(mod.effect_size([10, 10, 10], [12, 12, 12], 1e-9), 0.2), "(12 - 10) / 10 = +0.2"
    assert near(mod.effect_size([10, 10, 10], [5, 5, 5], 1e-9), -0.5), "halving is -0.5"
    assert near(mod.effect_size([0, 0, 0], [0.01, 0.01, 0.01], 1e-4), 100.0), "baseline median 0: divide by the floor, not by zero"
    C = mod.classify
    outcomes = []
    for s in seeds(range(1, 21)):
        r = random.Random(s)
        base = [r.lognormvariate(math.log(100), 0.3) for _ in range(90)]
        same = [r.lognormvariate(math.log(100), 0.3) for _ in range(90)]
        slow = [r.lognormvariate(math.log(130), 0.3) for _ in range(90)]
        fast = [r.lognormvariate(math.log(70), 0.3) for _ in range(90)]
        outcomes.append(C(base, same, 0.01, 0.1, 1.0))
        assert C(base, slow, 0.01, 0.1, 1.0) == "high", f"seed {s}: +30% latency must be 'high'"
        assert C(base, fast, 0.01, 0.1, 1.0) == "low", f"seed {s}: -30% latency must be 'low'"
    bad = [o for o in outcomes if o != "pass"]
    assert len(bad) <= (1 if ONLY_SEED is None else 1), f"identical distributions should almost always 'pass'; {len(bad)} of {len(outcomes)} did not"
    # significant but tiny
    r = random.Random(99)
    base = [r.lognormvariate(math.log(100), 0.3) for _ in range(6000)]
    tiny = [r.lognormvariate(math.log(103), 0.3) for _ in range(6000)]
    _, _, p = mod.mann_whitney_u(tiny, base)
    assert p < 1e-3, f"test setup: +3% with 6000 samples per side should be very significant; p = {p}"
    assert C(base, tiny, 0.01, 0.10, 1.0) == "pass", "p < 0.001 but the effect is 3% and the tolerance is 10%: a tiny real difference must not fail the deploy"
    assert C(base, tiny, 0.01, 0.0, 1.0) == "high", "with no effect-size threshold the same data is 'high'"
    # a real effect with too few samples is not significant
    small = [100, 130, 90, 120]
    assert C([100, 95, 105, 110], small, 0.01, 0.0, 1.0) == "pass", "four samples per side cannot reach p < 0.01"
    # error rates with a zero median
    assert C([0.0] * 40, [0.01] * 40, 0.01, 0.5, 1e-4) == "high", "from 0 to 1% errors is a big effect (the floor keeps the ratio finite)"
    return "pass / high / low with a p-value AND an effect-size threshold; a 3% shift at p < 0.001 still passes"


def m4():
    M = mod.METRICS
    P = Policy()
    ok = {m.name: "pass" for m in M}
    assert near(mod.score(ok, M), 100.0), "all pass: 100"
    assert near(mod.score(dict(ok, latency_ms="high"), M), 100.0 * 4 / 7), "latency (weight 3 of 7) bad: score 57.1"
    assert near(mod.score(dict(ok, latency_ms="low"), M), 100.0), "latency significantly LOWER is an improvement, not a failure"
    assert near(mod.score(dict(ok, memory_mb="high"), M), 100.0 * 6 / 7), "memory (weight 1 of 7) bad: score 85.7"
    assert mod.decide  # exists
    # decide needs data: build clean data and a leaking canary
    r = random.Random(5)
    clean = mod.generate(r, Regression())
    promote, sc, labels = mod.decide(clean, P)
    assert promote and near(sc, 100.0), f"a healthy build with clean data should be promoted at score 100; got {promote}, {sc}, {labels}"
    leaky = mod.generate(random.Random(5), Regression(leak=3.0))
    promote, sc, labels = mod.decide(leaky, P)
    assert labels["memory_mb"] == "high" and near(sc, 100.0 * 6 / 7), f"a 3 MB/min leak over 30 minutes should flag memory only; labels {labels}"
    assert not promote, "score 85.7 is below the pass score of 90: roll back, even though memory is not critical"
    promote, _, _ = mod.decide(leaky, Policy(alpha=0.01, pass_score=80.0))
    assert promote, "with a pass score of 80 a non-critical memory problem alone does not fail the deploy"
    slow = mod.generate(random.Random(6), Regression(latency=0.3))
    promote, sc, labels = mod.decide(slow, Policy(alpha=0.01, pass_score=0.0))
    assert labels["latency_ms"] == "high" and not promote, "a critical metric that is bad fails the canary whatever the score"
    # many deploys
    n = 300
    rows = []
    for s in seeds((1, 2, 3)):
        fr = mod.rollback_rate(Regression(), n, s)
        assert fr <= 0.03, f"seed {s}: false-rollback rate on {n} healthy deploys is {fr:.3f}, expected at most 0.03"
        for name, reg, need in (("latency +30%", Regression(latency=0.30), 0.97), ("errors +0.2 pt", Regression(errors=0.002), 0.97),
                                ("leak 3 MB/min", Regression(leak=3.0), 0.97)):
            rb = mod.rollback_rate(reg, n, s)
            assert rb >= need, f"seed {s}: {name}: the regression was rolled back in only {rb:.3f} of {n} deploys (missed {1 - rb:.3f}); need at least {need}"
        short = mod.rollback_rate(Regression(leak=3.0), n, s, minutes=10)
        assert short <= 0.1, f"seed {s}: a 3 MB/min leak has grown only 15 MB after 10 minutes; a 10-minute window should miss it, got rollback rate {short:.3f}"
        rows.append((s, fr, mod.rollback_rate(Regression(latency=0.30), n, s), mod.rollback_rate(Regression(leak=3.0), n, s), short))
    # effect-size threshold on big windows
    tiny = Regression(latency=0.03)
    no_gate = [dataclasses.replace(m, min_effect=0.0) for m in M]
    for s in seeds((1, 2)):
        gated = mod.rollback_rate(tiny, 60, s, minutes=60, instances=50)
        ungated = mod.rollback_rate(tiny, 60, s, minutes=60, instances=50, metrics=no_gate)
        assert gated <= 0.05, f"seed {s}: a +3% latency shift is below the 10% tolerance and must not fail the deploy; it was rolled back in {gated:.2f} of deploys"
        assert ungated >= 0.8, f"seed {s}: without an effect-size threshold a significant +3% shift (3000 samples per side) fails most deploys; got {ungated:.2f}"
    out = ["rolled-back share of 300 deploys:   healthy   latency +30%   leak 3 MB/min (30 min)   same leak, 10-min window"]
    for s, a, b, c, d in rows:
        out.append(f"seed {s}                              {a:7.3f}   {b:12.3f}   {c:21.3f}   {d:24.3f}")
    out.append(f"+3% latency on 3000-sample windows: rolled back {gated:.2f} with the effect-size threshold, {ungated:.2f} without")
    return "\n".join(out)


def m5():
    waves = mod.WAVES
    # one halt, by hand
    halted0 = 0
    for s in seeds(range(1, 11)):
        r = mod.rollout(random.Random(s), Regression(latency=0.4), 12.0, "concurrent")
        if r.halted_at == 0:
            halted0 += 1
            assert not r.promoted and abs(r.exposure - 0.015) < 1e-9 and r.waves_judged == 1, \
                f"seed {s}: halting at wave 0 means exposure 1.5% and one wave judged; got {r}"
        assert not r.promoted, f"seed {s}: a 40% latency regression must never be promoted when compared with a concurrent baseline"
    assert halted0 >= 9, f"a 40% regression should be caught by the first (smallest) wave in at least 9 of 10 seeds; got {halted0}"
    good_ok = 0
    for s in seeds(range(1, 11)):
        r = mod.rollout(random.Random(s), Regression(), 12.0, "concurrent")
        if r.promoted:
            good_ok += 1
            assert r.halted_at is None and r.exposure == 1.0 and r.waves_judged == len(waves), f"seed {s}: a promoted rollout judged every wave and reached 100%; got {r}"
    assert good_ok >= 9, f"a healthy build should pass all four waves in at least 9 of 10 seeds; got {good_ok}"
    # the daily pattern against yesterday's data
    peak_false = trough_missed = 0
    for s in seeds(range(1, 11)):
        r = mod.rollout(random.Random(s), Regression(), 14.0, "yesterday")      # waves at about 14:15 .. 15:45, peak traffic
        peak_false += 0 if r.promoted else 1
        r = mod.rollout(random.Random(s), Regression(latency=0.2), 2.0, "yesterday")   # waves around 3:00, the traffic trough
        trough_missed += 1 if r.promoted else 0
    assert peak_false >= 9, f"a HEALTHY build rolled out at the afternoon peak looks slow against yesterday's average: expected a halt in at least 9 of 10 seeds, got {peak_false}"
    assert trough_missed >= 8, f"a build that is 20% SLOWER rolled out at 3 a.m. looks fine against yesterday's average: expected it to be promoted in at least 8 of 10 seeds, got {trough_missed}"
    # many deploys over the whole day
    out = []
    for s in seeds((1, 2)):
        res = mod.compare_baselines(200, s)
        c, y = res["concurrent"], res["yesterday"]
        assert c["false_rollback"] <= 0.04, f"seed {s}: concurrent baseline: false-rollback rate {c['false_rollback']:.3f}, expected at most 0.04"
        assert c["missed"] <= 0.02, f"seed {s}: concurrent baseline: missed-regression rate {c['missed']:.3f}, expected at most 0.02"
        assert c["exposure"] <= 0.04, f"seed {s}: a bad build should be stopped in the first or second wave: mean exposure {c['exposure']:.3f}"
        assert y["false_rollback"] >= 0.25 and y["false_rollback"] > 5 * max(c["false_rollback"], 0.01), \
            f"seed {s}: against yesterday's data the daily swing should cause many false rollbacks; got {y['false_rollback']:.3f}"
        assert y["missed"] >= 0.15 and y["missed"] > 5 * max(c["missed"], 0.01), \
            f"seed {s}: against yesterday's data the daily swing should hide real regressions; got a missed rate of {y['missed']:.3f}"
        out.append(f"seed {s}: concurrent baseline  false rollbacks {c['false_rollback']:.3f}  missed {c['missed']:.3f}  mean exposure of a bad build {c['exposure']:.3f}")
        out.append(f"        vs yesterday         false rollbacks {y['false_rollback']:.3f}  missed {y['missed']:.3f}  mean exposure of a bad build {y['exposure']:.3f}")
    return "\n".join(out)


MILESTONES = [
    (1, "Milestone 1: seeded baseline and canary samples", m1),
    (2, "Milestone 2: the Mann-Whitney U test", m2),
    (3, "Milestone 3: classify a metric: pass, high or low", m3),
    (4, "Milestone 4: score, decision and error rates", m4),
    (5, "Milestone 5: waves, and a baseline that moves with the traffic", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 6 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
