"""Self-check for Lab 1: Estimation Drills.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 2 17    # milestone 2, replaying ONLY seed 17

Each milestone has (a) exact checks of your helpers on hand-computed values, (b) property
checks over many seeded random inputs (a failure prints the seed), and, from milestone 2
on, (c) scenario problems: a short prompt, a known answer, and a tolerance band
(within 10%, or within 2x when the prompt is loose). A wrong answer prints the reasoning
that leads to the right one, plus a guess at which classic mistake you made.

Nothing here is random at run time and nothing sleeps: the whole check takes well under a second.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import sys
import time

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

SEEDS = range(1, 61)


def seeds(default=SEEDS):
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


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def fmt(x):
    return mod.human(x) if x == x and abs(x) < 1e18 else str(x)


# ------------------------------------------------------------------------------------
# Scenario machinery
# ------------------------------------------------------------------------------------
# Classic mistakes, as (ratio of your answer to the truth, what it usually means).
MISTAKES = [
    (8, "off by 8x: bits and bytes mixed up (bandwidth is bits, storage is bytes)"),
    (1 / 8, "off by 1/8: you divided by 8 where bandwidth should be in bits"),
    (86_400, "off by 86,400: per day used where per second was meant"),
    (1 / 86_400, "off by 1/86,400: divided by seconds-per-day twice"),
    (365, "off by 365: a per-day figure used as per-year (or the reverse)"),
    (1 / 365, "off by 1/365: a per-year figure used as per-day"),
    (1000, "off by 1,000: a KB/MB/GB slip"),
    (1 / 1000, "off by 1/1,000: a KB/MB/GB slip"),
    (3, "off by 3x: the replication factor (or peak factor) applied twice, or not at all"),
    (1 / 3, "off by 1/3: the replication factor (or peak factor) left out"),
    (5, "off by 5x: the 80/20 fraction or the years forgotten"),
    (1 / 5, "off by 1/5: the 80/20 fraction applied when it should not be"),
    (2, "off by 2x: a missing headroom (utilisation) factor or a forgotten spare"),
    (1 / 2, "off by 1/2: headroom applied the wrong way round"),
    (1.5, "off by 1.5x: the zone-loss factor zones/(zones-1), or the index overhead"),
    (1 / 1.5, "off by 1/1.5: the zone-loss factor zones/(zones-1) left out"),
]


def diagnose(ratio):
    best = min(MISTAKES, key=lambda m: abs(math.log(ratio / m[0])) if ratio > 0 else 99)
    if ratio > 0 and abs(math.log(ratio / best[0])) < 0.12:
        return best[1]
    return None


class Scenario:
    def __init__(self, sid, title, prompt, solve, truth, tol, steps, unit=""):
        self.sid, self.title, self.prompt, self.solve = sid, title, prompt, solve
        self.truth, self.tol, self.steps, self.unit = truth, tol, steps, unit

    def ok(self, got):
        kind, v = self.tol
        if got is None or not isinstance(got, (int, float)) or got != got or got <= 0:
            return False
        if kind == "rel":
            return abs(got - self.truth) <= v * self.truth
        return self.truth / v <= got <= self.truth * v

    def band(self):
        kind, v = self.tol
        return f"within {v:.0%}" if kind == "rel" else f"within {v:g}x"


def run_scenarios(scs):
    """Returns (lines for the summary, list of failure texts)."""
    lines, fails = [], []
    for s in scs:
        got = s.solve(mod)
        ratio = got / s.truth if isinstance(got, (int, float)) and got > 0 else float("nan")
        if s.ok(got):
            lines.append(f"{s.sid:<3} {s.title:<34} you {fmt(got):>10}  truth {fmt(s.truth):>10}  ({ratio:.2f}x, {s.band()})")
        else:
            msg = [f"scenario {s.sid} ({s.title}) is out of band: you {fmt(got) if isinstance(got, (int, float)) else repr(got)}{s.unit}, expected {fmt(s.truth)}{s.unit}, {s.band()}",
                   f"  prompt: {s.prompt}"]
            if ratio == ratio:
                msg.append(f"  your answer is {ratio:.3g}x the truth")
                d = diagnose(ratio)
                if d:
                    msg.append(f"  likely mistake: {d}")
            msg.append("  reasoning:")
            msg += [f"    {i + 1}. {t}" for i, t in enumerate(s.steps)]
            fails.append("\n".join(msg))
    return lines, fails


def finish(lines, fails, extra=""):
    assert not fails, "\n".join(fails)
    return (extra + "\n" if extra else "") + "\n".join(lines)


# ====================================================================================
# Milestone 1: the toolkit
# ====================================================================================
def m1():
    assert mod.KB == 1_000 and mod.MB == 10 ** 6 and mod.GB == 10 ** 9 and mod.TB == 10 ** 12 and mod.PB == 10 ** 15, \
        "KB..PB must be powers of TEN (1 KB = 1,000 bytes) for this course"
    assert mod.SECONDS_PER_DAY == 86_400, "SECONDS_PER_DAY must be 86,400"
    assert near(mod.per_day_to_per_sec(86_400_000), 1000.0), "86.4M per day is 1,000 per second"
    assert near(mod.per_day_to_per_sec(1e9), 11574.074074074075, 1e-6), "a billion a day is about 11.6k/s"
    assert near(mod.per_sec_to_per_day(2.0), 172_800.0), "2/s is 172,800 per day"
    assert mod.bytes_to_bits(125_000_000) == 1_000_000_000, "125 MB/s is 1 Gbit/s"
    for x, e in ((1, 0), (9.99, 0), (10, 1), (999, 2), (1000, 3), (1e6, 6), (0.02, -2), (0.1, -1), (86_400, 4), (1e-3, -3)):
        got = mod.order_of_magnitude(x)
        assert got == e, f"order_of_magnitude({x}) should be {e} (floor of log10), got {got}"
    try:
        mod.order_of_magnitude(0)
        raise AssertionError("order_of_magnitude(0) should raise ValueError")
    except ValueError:
        pass
    cases = [((54_750_000_000_000, "B"), "54.8 TB"), ((12,), "12"), ((0.5,), "0.5"), ((1_500,), "1.5 k"),
             ((231.48148,), "231"), ((2_000_000_000, "B"), "2 GB"), ((438e12, "B"), "438 TB"),
             ((55.6e6, "bit/s"), "55.6 Mbit/s"), ((231.48, "req/s"), "231 req/s"), ((12, "B"), "12 B"), ((999,), "999"), ((1e15, "B"), "1 PB")]
    for a, want in cases:
        got = mod.human(*a)
        assert got == want, f"human{a!r} should print {want!r}, got {got!r}"
    assert mod.within_factor(300, 100, 3) and mod.within_factor(34, 100, 3) and not mod.within_factor(301, 100, 3) \
        and not mod.within_factor(33, 100, 3), "within_factor(e, t, 3) allows t/3 <= e <= 3t"
    assert not mod.within_factor(0, 5, 2), "an estimate of zero is never within a factor"
    # properties over seeded inputs
    for seed in seeds():
        rng = random.Random(seed)
        x = 10 ** rng.uniform(-3, 12)
        back = mod.per_sec_to_per_day(mod.per_day_to_per_sec(x))
        assert near(back, x, 1e-9), f"seed {seed}: per_sec_to_per_day(per_day_to_per_sec({x})) = {back}, not {x}"
        e = mod.order_of_magnitude(x)
        assert 10.0 ** e <= x * (1 + 1e-12) and x < 10.0 ** (e + 1) * (1 + 1e-12), \
            f"seed {seed}: order_of_magnitude({x}) = {e} but 10^{e} <= x < 10^{e + 1} fails"
        f = rng.choice([1.5, 2, 3, 10])
        t = 10 ** rng.uniform(0, 6)
        assert mod.within_factor(t * f * 0.999, t, f) and not mod.within_factor(t * f * 1.01, t, f), \
            f"seed {seed}: within_factor boundary wrong for truth={t}, factor={f}"
        h = mod.human(x)
        assert h.split()[0][0].isdigit(), f"seed {seed}: human({x}) = {h!r} should start with a number"
    return "units, order_of_magnitude, human and within_factor agree with hand values and 60 random inputs"


# ====================================================================================
# Milestone 2: QPS
# ====================================================================================
def sc_m2():
    return [
        Scenario("Q1", "microblog, 100M DAU", "100 million DAU each open the app 5 times a day. Peak is 3x the daily average. Peak QPS?",
                 lambda m: m.qps_from_dau(100e6, 5, 3)[1], 17_361, ("rel", 0.10),
                 ["100M x 5 = 500M requests/day", "500M / 86,400 = about 5,800/s on average", "x 3 for the peak = about 17,400/s"], "/s"),
        Scenario("Q2", "photo app reads", "20M DAU view 30 photos a day each. The evening peak is 4x the average. Peak read QPS?",
                 lambda m: m.qps_from_dau(20e6, 30, 4)[1], 27_778, ("rel", 0.10),
                 ["20M x 30 = 600M views/day", "600M / 86,400 = about 6,900/s", "x 4 = about 27,800/s"], "/s"),
        Scenario("Q3", "writes only", "50M DAU make 10 requests a day, 9 reads for every write. Peak factor 3. Peak WRITE QPS?",
                 lambda m: m.split_read_write(m.qps_from_dau(50e6, 10, 3)[1], 9)[1], 1_736, ("rel", 0.10),
                 ["50M x 10 = 500M requests/day, so 5,787/s on average, 17,361/s at peak",
                  "9 reads : 1 write means writes are 1/(9+1) = 10% of the total", "10% of 17,361 = about 1,740 writes/s"], "/s"),
        Scenario("Q4", "loose: a billion a month", "About 1 billion page views a month (take 30 days). Assume peak is 3x average. Peak QPS?",
                 lambda m: m.peak_qps(m.per_day_to_per_sec(1e9 / 30), 3), 1_157, ("factor", 2),
                 ["1B / 30 = 33M views/day", "33M / 86,400 = about 386/s on average", "x 3 = about 1,160/s (anything from 600 to 2,300 is a fair estimate)"], "/s"),
    ]


def m2():
    a, p = mod.qps_from_dau(86_400, 1000, 2.0)
    assert near(a, 1000.0) and near(p, 2000.0), f"86,400 DAU x 1000 actions is 1,000/s average, 2,000/s at peak 2x; got {a}, {p}"
    assert near(mod.avg_qps(10_000_000, 20), 2314.8148148148148, 1e-6), "10M DAU x 20 actions/day is about 2,315/s"
    assert near(mod.peak_qps(100.0), 300.0), "peak_qps defaults to a 3x peak factor"
    r, w = mod.split_read_write(1000.0, 9)
    assert near(r, 900.0) and near(w, 100.0), f"a 9:1 read:write split of 1000/s is 900 reads, 100 writes; got {r}, {w}"
    r, w = mod.split_read_write(1000.0, 1)
    assert near(r, 500.0) and near(w, 500.0), "1:1 is half and half"
    for seed in seeds():
        rng = random.Random(seed)
        dau, act, pf = 10 ** rng.uniform(4, 9), rng.uniform(0.1, 100), rng.uniform(1, 10)
        a1, p1 = mod.qps_from_dau(dau, act, pf)
        a2, _ = mod.qps_from_dau(2 * dau, act, pf)
        assert near(a2, 2 * a1, 1e-9), f"seed {seed}: doubling DAU must double QPS ({a1} -> {a2})"
        assert p1 >= a1 * 0.999999 and near(p1, a1 * pf, 1e-9), f"seed {seed}: peak must be average x peak factor ({a1} x {pf} != {p1})"
        rw = rng.uniform(0.1, 200)
        total = 10 ** rng.uniform(1, 6)
        rr, ww = mod.split_read_write(total, rw)
        assert near(rr + ww, total, 1e-9) and near(rr / ww, rw, 1e-9), f"seed {seed}: split_read_write({total}, {rw}) -> {rr}, {ww}"
    lines, fails = run_scenarios(sc_m2())
    return finish(lines, fails)


# ====================================================================================
# Milestone 3: storage
# ====================================================================================
def sc_m3():
    return [
        Scenario("S1", "pastebin, 5 years", "1M pastes a day, 10 KB each, kept 5 years, 3 replicas, no index overhead. Total fleet storage?",
                 lambda m: m.storage_bytes(1e6, 10 * m.KB, 5, 3), 54.75e12, ("rel", 0.10),
                 ["1M x 10 KB = 10 GB/day", "x 365 = 3.65 TB/year raw", "x 5 years x 3 replicas = 54.75 TB"], "B"),
        Scenario("S2", "chat with indexes", "50M DAU send 40 messages a day, 200 B each. Keep 1 year, 3 replicas, indexes and metadata add 30%. Fleet storage?",
                 lambda m: m.storage_bytes(50e6 * 40, 200, 1, 3, 0.3), 569.4e12, ("rel", 0.10),
                 ["50M x 40 = 2B messages/day; x 200 B = 400 GB/day", "x 365 = 146 TB/year raw", "x 1.3 for indexes = 190 TB", "x 3 replicas = 569 TB"], "B"),
        Scenario("S3", "photos, erasure coded", "50M uploads a day of 2 MB, 3 years, stored with erasure coding at 1.5x (not 3 copies). Total storage?",
                 lambda m: m.storage_bytes(50e6, 2 * m.MB, 3, 1.5), 164.25e15, ("rel", 0.10),
                 ["50M x 2 MB = 100 TB/day", "x 365 x 3 = 109.5 PB raw", "x 1.5 = 164 PB"], "B"),
        Scenario("S4", "how many disks", "That 164 PB sits on 16 TB nodes that you will fill to at most 70%. How many nodes?",
                 lambda m: m.nodes_for_storage(164.25e15, 16 * m.TB, 0.7), 14_665, ("rel", 0.10),
                 ["usable per node = 16 TB x 0.7 = 11.2 TB", "164.25 PB / 11.2 TB = about 14,700 nodes"]),
        Scenario("S5", "loose: logs", "20 billion log lines a day of about 1 KB each, 30 days online, 2 copies. Roughly how much disk? (be within 2x)",
                 lambda m: m.storage_bytes(20e9, 1000, 30 / 365, 2), 1.2e15, ("factor", 2),
                 ["20B x 1 KB = 20 TB/day, x 30 days = 600 TB", "x 2 copies = 1.2 PB"], "B"),
    ]


def m3():
    assert near(mod.raw_bytes_per_year(1e6, 10_000), 3.65e12), "1M writes/day x 10 KB x 365 = 3.65 TB"
    assert near(mod.storage_bytes(1e6, 10_000, 5, 3), 54.75e12), "pastebin: 54.75 TB"
    assert near(mod.storage_bytes(1000, 1000, 1, 1, 0.0), 365e6), "1000 x 1 KB x 365 = 365 MB"
    assert near(mod.storage_bytes(1000, 1000, 1, 2, 0.5), 365e6 * 3), "replication 2 and 50% index overhead multiply: x3"
    assert mod.nodes_for_storage(100 * mod.TB, 10 * mod.TB, 0.5) == 20, "100 TB on 10 TB nodes filled to 50% is 20 nodes"
    assert mod.nodes_for_storage(101 * mod.TB, 10 * mod.TB, 1.0) == 11, "round UP: 10.1 nodes need 11"
    for seed in seeds():
        rng = random.Random(seed)
        w, b = 10 ** rng.uniform(3, 9), 10 ** rng.uniform(1, 6)
        yrs, rep, idx = rng.uniform(0.5, 10), rng.choice([1, 2, 3, 1.5]), rng.uniform(0, 1)
        s = mod.storage_bytes(w, b, yrs, rep, idx)
        assert near(mod.storage_bytes(w, b, 2 * yrs, rep, idx), 2 * s, 1e-9), f"seed {seed}: storage must be linear in years"
        assert near(mod.storage_bytes(w, b, yrs, 2 * rep, idx), 2 * s, 1e-9), f"seed {seed}: storage must be linear in replication"
        assert near(s, mod.raw_bytes_per_year(w, b) * yrs * rep * (1 + idx), 1e-9), \
            f"seed {seed}: storage = raw/year x years x replication x (1 + overhead); got {s}"
        n = mod.nodes_for_storage(s, 10 ** rng.uniform(11, 14), 0.7)
        assert isinstance(n, int) and n >= 1, f"seed {seed}: node counts are whole numbers, got {n!r}"
    lines, fails = run_scenarios(sc_m3())
    return finish(lines, fails)


# ====================================================================================
# Milestone 4: bandwidth and caches
# ====================================================================================
def sc_m4():
    return [
        Scenario("B1", "image egress", "20,000 requests/s at peak, each returns a 500 KB image. Egress in bits per second?",
                 lambda m: m.bandwidth_bps(20_000, 500 * m.KB), 80e9, ("rel", 0.10),
                 ["20,000 x 500 KB = 10 GB/s", "x 8 bits per byte = 80 Gbit/s"], "bit/s"),
        Scenario("B2", "behind a CDN", "That 80 Gbit/s sits behind a CDN with a 95% hit ratio. Bit/s reaching the origin?",
                 lambda m: m.bandwidth_bps(m.origin_qps(20_000, 0.95), 500 * m.KB), 4e9, ("rel", 0.10),
                 ["95% hits means 5% of requests miss", "5% of 20,000 = 1,000 req/s to the origin", "1,000 x 500 KB x 8 = 4 Gbit/s"], "bit/s"),
        Scenario("B3", "pastebin cache", "1M new pastes a day of 10 KB. Reads cluster on recent pastes: cache the hottest 20% of the last 30 days. Cache size?",
                 lambda m: m.cache_bytes(1e6 * 10 * m.KB, 30, 0.2), 60e9, ("rel", 0.10),
                 ["new data = 1M x 10 KB = 10 GB/day", "30 days = 300 GB", "20% of that = 60 GB (fits in one node's RAM)"], "B"),
        Scenario("B4", "how good must the cache be", "55,556 feed loads/s at peak; the database behind the cache can take 5,000/s. What hit ratio is required?",
                 lambda m: m.required_hit_ratio(55_556, 5_000), 0.91, ("rel", 0.10),
                 ["the origin may see 5,000 of 55,556 requests", "that is 9% misses, so 91% must hit"]),
        Scenario("B5", "network cards", "80 Gbit/s of egress, 10 Gbit/s cards that you run at no more than 50%. How many cards?",
                 lambda m: m.nics_needed(80e9, 10e9, 0.5), 16, ("rel", 0.10),
                 ["usable per card = 10 x 0.5 = 5 Gbit/s", "80 / 5 = 16 cards"]),
        Scenario("B6", "loose: hit ratio gain", "Going from a 90% to a 99% hit ratio cuts the origin load by roughly what factor?",
                 lambda m: m.origin_qps(1000, 0.90) / m.origin_qps(1000, 0.99), 10, ("factor", 2),
                 ["misses go from 10% to 1%", "10% / 1% = 10x less origin traffic"]),
    ]


def m4():
    assert near(mod.bandwidth_bps(1000, 1000), 8e6), "1,000 req/s x 1 KB is 8 Mbit/s"
    assert near(mod.origin_qps(1000, 0.9), 100.0) and near(mod.origin_qps(1000, 0.0), 1000.0), "origin_qps = qps x (1 - hit)"
    assert near(mod.required_hit_ratio(1000, 100), 0.9) and mod.required_hit_ratio(100, 1000) == 0.0, \
        "required_hit_ratio(1000, 100) = 0.9, and 0 when no cache is needed"
    assert near(mod.cache_bytes(10e9, 30, 0.2), 60e9) and near(mod.cache_bytes(10e9, 30), 60e9), "hot_fraction defaults to 0.2"
    assert mod.nics_needed(10e9, 10e9, 0.5) == 2 and mod.nics_needed(11e9, 10e9, 1.0) == 2, "nics_needed rounds up"
    for seed in seeds():
        rng = random.Random(seed)
        q, b = 10 ** rng.uniform(1, 6), 10 ** rng.uniform(2, 7)
        h = rng.uniform(0, 0.999)
        assert near(mod.bandwidth_bps(q, b), q * b * 8, 1e-9), f"seed {seed}: bandwidth_bps({q}, {b}) must be q x b x 8"
        o = mod.origin_qps(q, h)
        assert 0 <= o <= q + 1e-9, f"seed {seed}: the origin cannot see more than the total ({o} > {q})"
        cap = q * rng.uniform(0.01, 2)
        need = mod.required_hit_ratio(q, cap)
        assert 0 <= need < 1 and mod.origin_qps(q, need) <= cap * (1 + 1e-9), \
            f"seed {seed}: with hit ratio {need}, origin sees {mod.origin_qps(q, need)} but may only take {cap}"
        assert mod.cache_bytes(b, 10, 0.1) < mod.cache_bytes(b, 10, 0.4), f"seed {seed}: a hotter fraction needs a bigger cache"
    lines, fails = run_scenarios(sc_m4())
    return finish(lines, fails)


# ====================================================================================
# Milestone 5: machines
# ====================================================================================
def sc_m5():
    return [
        Scenario("M1", "app servers", "Peak 17,361 req/s; one box does 2,000 req/s; run boxes at 50% of that. How many boxes?",
                 lambda m: m.machines(17_361, 2000, 0.5), 18, ("rel", 0.10),
                 ["usable per box = 2,000 x 0.5 = 1,000 req/s", "17,361 / 1,000 = 17.4, round up to 18"]),
        Scenario("M2", "survive a zone", "Same load, but the fleet is spread over 3 zones and must carry the peak with one zone gone. How many boxes?",
                 lambda m: m.machines(17_361, 2000, 0.5, zones=3), 27, ("rel", 0.10),
                 ["base need is 18 boxes", "with 3 zones, the 2 survivors carry everything, so each zone must hold 9 and the total is 18 x 3/2 = 27"]),
        Scenario("M3", "Little's law", "5,000 requests/s with 40 ms average latency. How many requests are in flight at once?",
                 lambda m: m.in_flight(5000, 0.040), 200, ("rel", 0.10),
                 ["L = lambda x W", "5,000/s x 0.040 s = 200 in flight (a hint for thread or connection pool sizes)"]),
        Scenario("M4", "latency budget sets utilisation", "A single-queue server may take at most 4x its bare service time on average (M/M/1: 1/(1 - rho)). Highest utilisation?",
                 lambda m: m.max_utilisation_for(4), 0.75, ("rel", 0.10),
                 ["latency inflation = 1 / (1 - rho) <= 4", "1 - rho >= 1/4, so rho <= 0.75"]),
        Scenario("M5", "feed fan-out workers", "Chapter 9's feed: 200M DAU, each post goes to 200 followers (100 timeline inserts per DAU per day at 0.5 posts), peak 3x. A node does 100,000 inserts/s; run at 50%. Nodes?",
                 lambda m: m.machines(m.qps_from_dau(200e6, 100, 3)[1], 100_000, 0.5), 14, ("factor", 2),
                 ["200M x 100 = 20B inserts/day = 231k/s average", "x 3 = 694k/s at peak", "694k / (100k x 0.5) = 13.9, round up to 14"]),
    ]


def m5():
    assert mod.machines(1000, 100, 1.0) == 10 and mod.machines(1001, 100, 1.0) == 11, "machines rounds up"
    assert mod.machines(1000, 100, 0.5) == 20, "at 50% utilisation you need twice as many boxes"
    assert mod.machines(1000, 100, 0.5, spares=2) == 22, "spares are added on top"
    assert mod.machines(1000, 100, 0.5, zones=2) == 40, "losing 1 of 2 zones doubles the fleet"
    assert mod.machines(1000, 100, 0.5, zones=4) == 27, "4 zones: x 4/3 on top of 20 is 26.7, round up to 27"
    assert near(mod.in_flight(1000, 0.2), 200.0), "Little's law"
    assert near(mod.latency_inflation(0.5), 2.0) and near(mod.latency_inflation(0.9), 10.0), "1/(1-rho): 2x at 50%, 10x at 90%"
    for bad in (1.0, 1.5, -0.1):
        try:
            mod.latency_inflation(bad)
            raise AssertionError(f"latency_inflation({bad}) should raise ValueError")
        except ValueError:
            pass
    assert near(mod.max_utilisation_for(2), 0.5) and near(mod.max_utilisation_for(10), 0.9), "inverse of latency_inflation"
    try:
        mod.max_utilisation_for(0.5)
        raise AssertionError("a budget below 1x is impossible: raise ValueError")
    except ValueError:
        pass
    for seed in seeds():
        rng = random.Random(seed)
        peak, per, u = 10 ** rng.uniform(1, 7), 10 ** rng.uniform(1, 5), rng.uniform(0.2, 0.9)
        z = rng.choice([1, 2, 3, 4])
        n = mod.machines(peak, per, u, zones=z)
        assert n * per * u >= peak * (1 - 1e-9), f"seed {seed}: {n} boxes x {per} x {u} cannot carry the peak {peak}"
        if z > 1:
            assert (n * (z - 1) / z) * per * u >= peak * (1 - 1e-9), \
                f"seed {seed}: after losing one of {z} zones the remaining capacity cannot carry the peak"
        assert mod.machines(peak * 2, per, u, zones=z) >= n, f"seed {seed}: more load must never need fewer machines"
        assert mod.machines(peak, per, u, zones=z, spares=3) == n + 3, f"seed {seed}: spares are added on top"
        rho = rng.uniform(0, 0.95)
        assert near(mod.max_utilisation_for(mod.latency_inflation(rho)), rho, 1e-9), f"seed {seed}: max_utilisation_for must invert latency_inflation"
    lines, fails = run_scenarios(sc_m5())
    # one cross-check that ties the milestones together: the whole chapter-2 pastebin
    m = mod
    w_avg = m.per_day_to_per_sec(1e6)
    peak_total = m.qps_from_dau(10e6, 0.1 + 0.1 * 20, 3)[1]
    boxes = m.machines(peak_total, 2000, 0.5, spares=1)
    store = m.storage_bytes(1e6, 10 * m.KB, 5, 3)
    cache = m.cache_bytes(1e6 * 10 * m.KB, 30)
    assert 2 <= boxes <= 4, f"pastebin (chapter 2): expected about 2-3 app servers, got {boxes}"
    assert near(store, 54.75e12) and near(cache, 60e9), "pastebin: 54.8 TB over 5 years, 60 GB hot set"
    lines.append(f"E2E pastebin (chapter 2): {w_avg:.0f} writes/s avg, {boxes} app boxes, {fmt(store)}B stored, {fmt(cache)}B cache")
    return finish(lines, fails)


check(1, "Milestone 1: the toolkit, units and human()", m1)
check(2, "Milestone 2: QPS from DAU, actions and a peak factor", m2)
check(3, "Milestone 3: storage over N years with replication and indexes", m3)
check(4, "Milestone 4: bandwidth and cache sizing (80/20)", m4)
check(5, "Milestone 5: machine counts with headroom", m5)

print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - T0:.1f} s)")
sys.exit(0 if results and all(results) else 1)
