"""Self-check for Lab 4: Sketches, Count-Min, HyperLogLog and Top-K.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 3 7     # milestone 3, replaying ONLY seed 7

Everything is deterministic: hashes come from hashlib, every random draw comes from a seeded
random.Random, and nothing reads a clock. The check builds its own streams and its own exact counts, so a
bug in your code cannot hide a bug in the reference data. When a property fails it prints the failing
seed and the command that replays it. The whole check takes well under a minute.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time
from bisect import bisect_left
from collections import Counter
from itertools import accumulate

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


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def replay(n, seed):
    return f"(replay: python3 check.py {target} {n} {seed})"


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
        print(f"  ✘ {name}: crashed with {type(e).__name__}: {e}  [in {where}]")
        results.append(False)


# ---------------------------------------------------------------------------------------------
# Trusted helpers (the check's own; they do not use anything from your module except h64's contract)
# ---------------------------------------------------------------------------------------------
def zipf_events(rng, n_events, n_keys, s):
    """A list of key names 'k0'..'k{n-1}' drawn Zipf(s): P(rank r) proportional to 1 / (r + 1)^s."""
    cum = list(accumulate(1.0 / (r + 1) ** s for r in range(n_keys)))
    tot = cum[-1]
    names = [f"k{r}" for r in range(n_keys)]
    return [names[min(bisect_left(cum, rng.random() * tot), n_keys - 1)] for _ in range(n_events)]


def pct(x):
    return f"{x * 100:.1f}%"


# ---------------------------------------------------------------------------------------------
def m1():
    # the dimensions
    for eps, delta, wd in ((0.001, 0.01, (2719, 5)), (0.0001, 0.01, (27183, 5)), (0.01, 0.001, (272, 7)), (0.05, 0.5, (55, 1))):
        got = mod.cms_dims(eps, delta)
        assert tuple(got) == wd, f"cms_dims({eps}, {delta}) should be (ceil(e/eps), ceil(ln(1/delta))) = {wd}, got {tuple(got)}"
    eps, delta = 0.002, 0.05
    w, d = mod.cms_dims(eps, delta)
    # determinism and seeds
    a, b, c = mod.CountMin(eps, delta, seed=3), mod.CountMin(eps, delta, seed=3), mod.CountMin(eps, delta, seed=4)
    for key, cnt in (("x", 5), ("y", 1), ("z", 40)):
        for s in (a, b, c):
            s.add(key, cnt)
    assert a.table == b.table, "two sketches with the same (eps, delta, seed) and the same input must have identical tables (use hashlib, not hash())"
    assert a.table != c.table, "a different seed must give different hash functions, hence a different table"
    assert (len(a.table), len(a.table[0])) == (d, w) and a.n == 46, f"table should be {d} x {w} with n = 46, got {len(a.table)} x {len(a.table[0])}, n = {a.n}"
    assert a.estimate("z") >= 40 and a.estimate("never-seen") <= 46, "estimates must be >= the true count"
    # the guarantee: true <= estimate <= true + eps * N with probability >= 1 - delta
    N, keys, S = 60000, 15000, seeds(range(1, 7))
    viol = tot = 0
    worst = 0.0
    over_sum = 0.0
    for s in S:
        rng = random.Random(s)
        events = zipf_events(rng, N, keys, 1.0)
        exact = Counter(events)
        sk = mod.CountMin(eps, delta, seed=s)
        for key, cnt in exact.items():
            sk.add(key, cnt)
        assert sk.n == N, f"seed {s}: n should be the total weight {N}, got {sk.n} {replay(1, s)}"
        bound = eps * N
        for key, true in exact.items():
            est = sk.estimate(key)
            assert est >= true, f"seed {s}: UNDERCOUNT for {key!r}: estimate {est} < true {true}. Collisions only add; the minimum over rows can never be below the truth. {replay(1, s)}"
            e = est - true
            tot += 1
            viol += e > bound
            worst = max(worst, e / bound)
            over_sum += e
    rate = viol / tot
    assert rate <= delta, f"{pct(rate)} of (sketch, key) pairs were more than eps*N = {eps * N:.0f} too high; the promise is at most delta = {pct(delta)}"
    # the check has teeth: a sketch that is 12x too narrow and one row deep must break the bound
    rng = random.Random(99)
    exact = Counter(zipf_events(rng, N, keys, 1.0))
    bad = mod.CountMin(eps, delta, seed=1, width=w // 12, depth=1)
    for key, cnt in exact.items():
        bad.add(key, cnt)
    bad_rate = sum(bad.estimate(k) - t > eps * N for k, t in exact.items()) / len(exact)
    assert bad_rate > delta, "internal: the undersized sketch should violate the bound (width= / depth= arguments ignored?)"
    # the minimum over rows must actually be used: with 400 keys in 20 columns, d=6 rows beat d=1 clearly
    means = {}
    for dd in (1, 6):
        sk = mod.CountMin(0.1, 0.1, seed=5, width=20, depth=dd)
        for i in range(400):
            sk.add(f"key{i}")
        means[dd] = sum(sk.estimate(f"key{i}") for i in range(400)) / 400
    assert means[6] < 0.85 * means[1], f"estimate() should take the MINIMUM over the d rows: with 400 keys in 20 columns the mean estimate was {means[6]:.1f} with 6 rows against {means[1]:.1f} with 1 row (expected at least 15% lower)"
    return (f"eps={eps}, delta={delta} -> {d} x {w} counters ({d * w * 4 / 1024:.1f} KiB at 4 B each); stream of {N:,} Zipf events over {keys:,} keys, {len(S)} seeds, {tot:,} (sketch, key) pairs\n"
            f"never an undercount; {viol} keys over eps*N={eps * N:.0f} ({pct(rate)}, allowed {pct(delta)}); worst overcount {worst:.2f} x eps*N; mean overcount {over_sum / tot:.1f}\n"
            f"the same stream in a sketch 12x too narrow and 1 row deep: {pct(bad_rate)} of keys break the bound")


# ---------------------------------------------------------------------------------------------
def m2():
    eps, delta = 0.004, 0.02
    S = seeds(range(1, 9))
    for s in S:
        rng = random.Random(s)
        events = zipf_events(rng, 12000, 3000, 1.1)
        parts = rng.randrange(2, 7)
        buckets = [[] for _ in range(parts)]
        for ev in events:
            buckets[rng.randrange(parts)].append(ev)
        whole = mod.CountMin(eps, delta, seed=11)
        for ev in events:
            whole.add(ev)
        sketches = []
        for b in buckets:
            sk = mod.CountMin(eps, delta, seed=11)
            for ev in b:
                sk.add(ev)
            sketches.append(sk)
        before = [[row[:] for row in sk.table] for sk in sketches]
        merged = sketches[0]
        for sk in sketches[1:]:
            merged = merged.merge(sk)
        assert merged.table == whole.table, f"seed {s}: merging {parts} partition sketches should equal the sketch of the whole stream, cell for cell {replay(2, s)}"
        assert merged.n == whole.n == len(events), f"seed {s}: merged n should be {len(events)}, got {merged.n} {replay(2, s)}"
        assert [sk.table for sk in sketches] == before, f"seed {s}: merge must return a NEW sketch and leave its inputs untouched {replay(2, s)}"
        rev = sketches[-1]
        for sk in reversed(sketches[:-1]):
            rev = rev.merge(sk)
        assert rev.table == merged.table, f"seed {s}: merge order must not matter {replay(2, s)}"
        exact = Counter(events)
        for key in list(exact)[:300]:
            est = merged.estimate(key)
            assert exact[key] <= est <= exact[key] + eps * len(events), f"seed {s}: merged estimate for {key!r} is {est}, true {exact[key]}, bound +{eps * len(events):.0f} {replay(2, s)}"
    x, y = mod.CountMin(eps, delta, seed=1), mod.CountMin(eps, delta, seed=2)
    for other in (y, mod.CountMin(eps * 2, delta, seed=1), mod.CountMin(eps, delta * 0.0001, seed=1)):
        try:
            x.merge(other)
        except ValueError:
            continue
        raise AssertionError("merging sketches with a different seed, width or depth must raise ValueError: their cells mean different things")
    return (f"{len(S)} seeds x 2 to 6 partitions: merged table == table of the whole stream, in any merge order, inputs unchanged\n"
            "merging sketches with different seed / width / depth raises ValueError")


# ---------------------------------------------------------------------------------------------
def m3():
    N = 20000
    configs = [(0.8, 20), (1.2, 20), (0.8, 100), (1.2, 100)]
    S = seeds(range(1, 9))
    tracked_all = guaranteed_hits = guaranteed_total = 0
    worst_err = 0.0
    for s in S:
        for s_exp, m in configs:
            tag = f"seed {s}, s={s_exp}, m={m}"
            rng = random.Random(s * 1000 + m)
            events = zipf_events(rng, N, 2500, s_exp)
            exact = Counter(events)
            ss = mod.SpaceSaving(m)
            for ev in events:
                ss.update(ev)
            assert len(ss.count) <= m, f"{tag}: more than m={m} counters in use ({len(ss.count)}) {replay(3, s)}"
            assert sum(ss.count.values()) == N == ss.n, f"{tag}: the counters must always sum to N={N}; got {sum(ss.count.values())} (n={ss.n}) {replay(3, s)}"
            slack = N / m
            for key, c in ss.count.items():
                e = ss.err[key]
                assert c - e <= exact[key] <= c, f"{tag}: key {key!r}: need count-err <= true <= count, got {c - e} <= {exact[key]} <= {c} {replay(3, s)}"
                assert e <= slack, f"{tag}: key {key!r} has err {e} > N/m = {slack:.0f} {replay(3, s)}"
                worst_err = max(worst_err, e / slack)
            tracked_all += len(ss.count)
            floor = ss.min_count()
            assert floor <= slack, f"{tag}: min counter {floor} exceeds N/m = {slack:.0f} {replay(3, s)}"
            for key, true in exact.items():
                lo, hi = ss.bounds(key)
                assert lo <= true <= hi, f"{tag}: bounds({key!r}) = ({lo}, {hi}) but the truth is {true} {replay(3, s)}"
                if true > slack:
                    assert key in ss.count, f"{tag}: key {key!r} occurs {true} times > N/m = {slack:.0f} so it MUST be tracked {replay(3, s)}"
            for k in (3, 10):
                top = ss.top(k)
                assert [t[1] for t in top] == sorted((t[1] for t in top), reverse=True), f"{tag}: top({k}) not sorted by count {replay(3, s)}"
                ex_top = {key for key, _ in sorted(exact.items(), key=lambda kv: (-kv[1], kv[0]))[:k]}
                guaranteed_total += 1
                if ss.guaranteed(k):
                    guaranteed_hits += 1
                    assert {t[0] for t in top} == ex_top, f"{tag}: guaranteed({k}) said the top-{k} set is certain, but it differs from the exact one: {sorted({t[0] for t in top} ^ ex_top)} {replay(3, s)}"
    # the guarantee must actually fire when the stream is skewed and the table big enough
    rng = random.Random(5)
    skew = zipf_events(rng, 20000, 2500, 1.4)
    big = mod.SpaceSaving(200)
    for ev in skew:
        big.update(ev)
    assert big.guaranteed(5), "on a strongly skewed stream (s=1.4) with 200 counters the top-5 should be provably correct: guaranteed(5) returned False"
    tiny = mod.SpaceSaving(5)
    for ev in zipf_events(random.Random(6), 5000, 2500, 0.6):
        tiny.update(ev)
    assert not tiny.guaranteed(5), "on a flat stream with 5 counters nothing can be guaranteed, yet guaranteed(5) returned True"
    # exact while there is room
    few = mod.SpaceSaving(10)
    for ev in "aabacbbbd":
        few.update(ev)
    assert few.top(2) == [("b", 4, 0), ("a", 3, 0)] and few.guaranteed(2) and few.min_count() == 0, f"with room to spare the counts are exact: {few.top(2)}"
    full = mod.SpaceSaving(2)
    for ev in "aabc":
        full.update(ev)
    assert full.top(2) == [("a", 2, 0), ("c", 2, 1)], f"worked example: a a b c with m=2 evicts b and c inherits its count 1: expected [('a', 2, 0), ('c', 2, 1)], got {full.top(2)}"
    return (f"{len(S)} seeds x 4 configs (Zipf s = 0.8 and 1.2, m = 20 and 100, N = {N:,}): counters sum to N; count-err <= true <= count; err <= N/m (worst {worst_err:.2f} of it);\n"
            f"every key above N/m is tracked; untracked keys are bounded by the min counter; guaranteed(k) fired on {guaranteed_hits}/{guaranteed_total} queries and was never wrong")


# ---------------------------------------------------------------------------------------------
def m4():
    note = []
    rows = []
    in3 = total = 0
    worst = 0.0
    T = 120
    S = seeds(range(T))
    for p, ns in ((8, (10, 100, 1000, 6000)), (10, (10, 100, 1000, 6000)), (12, (10, 100, 1000, 6000))):
        m = 1 << p
        sigma = 1.04 / math.sqrt(m)
        for n in ns:
            errs = []
            for t in S:
                rng = random.Random(p * 100003 + n * 7919 + t)
                h = mod.HyperLogLog(p)
                for _ in range(n):
                    h.add_hash(rng.getrandbits(64))
                errs.append((h.count() - n) / max(n, 1))
            scale = max(sigma * n, 1.0) / n         # a count of ten can only be off by whole items: scale is at least 1 item
            zs = [e / scale for e in errs]
            ok = sum(abs(z) <= 3 for z in zs)
            in3 += ok
            total += len(zs)
            bad = [(S[i], zs[i]) for i in range(len(zs)) if abs(zs[i]) > 4.5]
            assert not bad, f"p={p}, n={n}: relative error beyond 4.5 standard errors (1.04/sqrt(m) = {pct(sigma)}): seeds {[(s_, round(z, 1)) for s_, z in bad[:3]]}; replay with seed t (rng = Random({p} * 100003 + {n} * 7919 + t))"
            mean_z = sum(zs) / len(zs)
            rms = math.sqrt(sum(z * z for z in zs) / len(zs))
            worst = max(worst, max(abs(z) for z in zs))
            assert abs(mean_z) <= 0.45, f"p={p}, n={n}: the estimator is biased: mean error {mean_z:+.2f} standard errors over {len(zs)} trials (a correct HLL is within +-0.45). Is the small-range correction applied for raw <= 2.5 m, and alpha = 0.7213 / (1 + 1.079 / m)?"
            assert rms <= 1.35, f"p={p}, n={n}: the spread of the error is {rms:.2f} standard errors; a correct HyperLogLog is at most about 1.35 (std error 1.04 / sqrt(m))"
            rows.append((p, n, sigma, rms, max(abs(z) for z in zs)))
    assert in3 / total >= 0.99, f"only {pct(in3 / total)} of {total} trials were within 3 standard errors; expected at least 99%"
    # merge: union of overlapping sets equals the sketch of the union, register for register
    for s in seeds(range(1, 9)):
        rng = random.Random(s)
        a, b, u = mod.HyperLogLog(10, seed=4), mod.HyperLogLog(10, seed=4), mod.HyperLogLog(10, seed=4)
        A = [f"u{rng.randrange(8000)}" for _ in range(3000)]
        B = [f"u{rng.randrange(8000)}" for _ in range(3000)]
        for x in A:
            a.add(x)
            u.add(x)
        for x in B:
            b.add(x)
            u.add(x)
        ab, ba = a.merge(b), b.merge(a)
        assert ab.reg == u.reg == ba.reg, f"seed {s}: merge must be the register-wise max: merged != sketch of the union {replay(4, s)}"
        assert ab.count() == u.count() and a.merge(a).reg == a.reg, f"seed {s}: merging with itself must change nothing {replay(4, s)}"
        before = a.reg[:]
        a.merge(b)
        assert a.reg == before, f"seed {s}: merge must return a new sketch and not mutate its input {replay(4, s)}"
        again = mod.HyperLogLog(10, seed=4)
        for x in A + A:
            again.add(x)
        once = mod.HyperLogLog(10, seed=4)
        for x in A:
            once.add(x)
        assert again.reg == once.reg, f"seed {s}: adding the same item twice must not change the registers {replay(4, s)}"
        true = len(set(A) | set(B))
        sigma = 1.04 / math.sqrt(1024)
        assert abs(ab.count() - true) / true <= 4.5 * sigma, f"seed {s}: union estimate {ab.count():.0f} vs true {true} {replay(4, s)}"
    for q in (mod.HyperLogLog(9, seed=4), mod.HyperLogLog(10, seed=5)):
        try:
            mod.HyperLogLog(10, seed=4).merge(q)
        except ValueError:
            continue
        raise AssertionError("merging HyperLogLogs with a different p or seed must raise ValueError")
    # the small range: ten distinct items in 1024 registers must read as ten
    for s in seeds(range(1, 21)):
        h = mod.HyperLogLog(10, seed=s)
        for i in range(10):
            h.add(f"item{i}")
        assert abs(h.count() - 10) <= 1.0, f"seed {s}: 10 distinct items read as {h.count():.2f}. Below about 2.5 m the raw harmonic-mean estimate is badly biased; use linear counting m * ln(m / V) there {replay(4, s)}"
    note.append(f"{T} trials per cell; error is (estimate - n) / n in units of the standard error 1.04/sqrt(m):  within 3 standard errors in {pct(in3 / total)} of {total} trials, worst {worst:.1f}")
    note.append("   p   m      std err   n=10 rms  n=100 rms  n=1000 rms  n=6000 rms")
    for p in (8, 10, 12):
        r = [x for x in rows if x[0] == p]
        note.append(f"  {p:>2} {1 << p:>5}   {pct(r[0][2]):>7}   " + "".join(f"{x[3]:>9.2f}   " for x in r))
    note.append("merge = register-wise max: equals the sketch of the union, is idempotent, ignores duplicates; 10 distinct items read as 10 +- 1")
    return "\n".join(note)


# ---------------------------------------------------------------------------------------------
KEYS, S_EXP, PER_WINDOW, WSEC = 3000, 1.1, 8000, 60


def make_stream(seed, windows, per_window=PER_WINDOW, extra=(), volume=None):
    """Background Zipf traffic, `per_window` events per 60 s window. `extra`: (window, key, n_events)
    triples of injected events. `volume`: {window: multiplier} scales ALL traffic of a window."""
    rng = random.Random(seed)
    cum = list(accumulate(1.0 / (r + 1) ** S_EXP for r in range(KEYS)))
    names = [f"k{r}" for r in range(KEYS)]
    events = []
    for w in range(windows):
        n = int(per_window * (volume or {}).get(w, 1))
        evs = [names[min(bisect_left(cum, rng.random() * cum[-1]), KEYS - 1)] for _ in range(n)]
        for key_w, key, cnt in extra:
            if key_w == w:
                evs += [key] * cnt
        rng.shuffle(evs)
        times = sorted(w * WSEC + rng.random() * WSEC for _ in evs)
        events += list(zip(times, evs))
    return events


def run_detector(events, **kw):
    det = mod.TrendingDetector(window_s=WSEC, **kw)
    for ts, key in events:
        det.observe(ts, key)
    det.flush()
    return det


def m5():
    assert abs(mod.trend_score(100, 20, 10) - 110 / 30) < 1e-9, "trend_score(cur, base, alpha) = (cur + alpha) / (base + alpha)"
    assert mod.trend_score(5, 0, 10) < 2, "a key going from 0 to 5 events must not score high: alpha smooths tiny baselines"
    W = 14
    # 1. background only: no alarms
    S = seeds(range(1, 7))
    alarms = 0
    for s in S:
        det = run_detector(make_stream(s, W))
        assert not det.alerts, f"seed {s}: false alarm(s) on pure background traffic: {[(w, k, round(sc, 1), c) for w, k, sc, c in det.alerts[:4]]} {replay(5, s)}"
        alarms += len(det.alerts)
    # 2. a flash crowd across ALL keys (6x volume for one window) is not a trend of any particular key
    for s in seeds(range(1, 4)):
        det = run_detector(make_stream(s + 40, W, volume={9: 6}))
        assert not det.alerts, f"seed {s}: a 6x surge of ALL traffic was reported as trends: {[(w, k, round(sc, 1)) for w, k, sc, c in det.alerts[:4]]}. Scale the baseline by this window's volume / mean baseline volume {replay(5, s)}"
    # 3. injected trends are detected in the window where they start
    detail = []
    for s in seeds(range(1, 7)):
        extra = [(8, "trend-new", 500), (9, "trend-new", 800), (10, "k12", 700)]
        det = run_detector(make_stream(s, W, extra=extra))
        found = {}
        for w, k, sc, c in det.alerts:
            found.setdefault(k, (w, sc, c))
        assert set(found) <= {"trend-new", "k12"}, f"seed {s}: false alarms for {sorted(set(found) - {'trend-new', 'k12'})}: {[(w, k, round(sc, 1), c) for w, k, sc, c in det.alerts if k not in ('trend-new', 'k12')][:3]} {replay(5, s)}"
        assert "trend-new" in found and found["trend-new"][0] == 8, f"seed {s}: the brand-new key (500 events in window 8, nothing before) should alarm in window 8; alerts: {[(w, k, round(sc, 1)) for w, k, sc, c in det.alerts][:6]} {replay(5, s)}"
        assert "k12" in found and found["k12"][0] == 10, f"seed {s}: the surge of an established key (k12, +700 events in window 10) should alarm in window 10; alerts: {[(w, k, round(sc, 1)) for w, k, sc, c in det.alerts][:6]} {replay(5, s)}"
        assert not [a for a in det.alerts if a[0] < 8], f"seed {s}: alarms before any trend started {replay(5, s)}"
        detail.append((found["trend-new"][1], found["k12"][1]))
    # 3b. a tiny blip is not a trend: min_count is the floor (use many candidates so the blip IS a candidate)
    det = run_detector(make_stream(2, W, extra=[(8, "blip", 60)]), candidates=400)
    assert not [a for a in det.alerts if a[1] == "blip"], f"a key that goes from 0 to 60 events (below min_count=100) must not alarm: {[(w, k, round(sc, 1), c) for w, k, sc, c in det.alerts if k == 'blip']}"
    det = run_detector(make_stream(2, W, extra=[(8, "blip", 60)]), candidates=400, min_count=20)
    assert [a for a in det.alerts if a[1] == "blip" and a[0] == 8], "with min_count=20 the same 60-event blip (score ~5) should alarm in window 8: min_count must be a parameter, not a constant"
    # 4. late events are counted and dropped; a gap of empty windows does not break anything
    det = mod.TrendingDetector(window_s=60, baseline_windows=5, min_count=1, ratio=1e9)
    for ts, key in ((1, "a"), (70, "a"), (65, "b"), (30, "a"), (250, "a")):
        det.observe(ts, key)
    det.flush()
    assert det.late == 1, f"events for a window that is already closed are late: expected 1 late event (ts=30 after window 1 opened), got {det.late}"
    assert sum(n for _, _, n in det.history) == 4, f"a late event must be dropped, not added to the current window: the closed windows hold {sum(n for _, _, n in det.history)} events, expected 4"
    avg_new = sum(d[0] for d in detail) / len(detail)
    avg_surge = sum(d[1] for d in detail) / len(detail)
    return (f"{len(S)} background-only streams of {W} windows x {PER_WINDOW:,} events: {alarms} alarms; a 6x all-traffic surge: none\n"
            f"injected trends found in the window they start, every seed: a brand-new key (score ~{avg_new:.0f}) and a 12th-ranked key surging 700 events (score ~{avg_surge:.0f}), nothing else flagged")


check(1, "Milestone 1: Count-Min sized from (eps, delta), checked on a Zipf stream", m1)
check(2, "Milestone 2: mergeability (partitions merge to the sketch of the union)", m2)
check(3, "Milestone 3: Space-Saving top-k with guarantees against exact counts", m3)
check(4, "Milestone 4: HyperLogLog (bias correction, merge, 3 standard errors)", m4)
check(5, "Milestone 5: windowed trending detector", m5)

print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - T0:.1f} s)")
sys.exit(0 if results and all(results) else 1)
