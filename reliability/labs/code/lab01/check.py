"""Self-check for Lab 1: SLOs & Burn-Rate Alerts.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 5       # only milestone 5
    python3 check.py solution 5 2024  # milestone 5, replaying ONLY the scenario set of seed 2024

Everything is synthetic and seeded: the log, the incidents, the noise. There is no
real clock and no network, so every run gives identical numbers. The whole check
finishes in well under a minute.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
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


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


# =============================================================================
# Milestone 1: parse, valid, good
# =============================================================================
def oracle(lines, threshold=300):
    """An independent, deliberately plain SLI computation for the cross-check."""
    valid = ga = gl = skipped = 0
    for line in lines:
        f = line.split(" ")
        try:
            assert len(f) == 6
            ts, status, lat = int(f[0]), int(f[3]), int(f[4])
            assert ts >= 0 and lat >= 0 and 100 <= status <= 599
        except (AssertionError, ValueError):
            skipped += 1
            continue
        if not f[2].startswith("/api/") or f[2] == "/api/health" or f[5] == "loadtest":
            continue
        valid += 1
        ok = status < 500 and status != 429
        ga += ok
        gl += ok and lat <= threshold
    return valid, ga, gl, skipped


def m1():
    p = mod.parse_line("3601 GET /api/cart 200 84 web")
    assert p is not None and (p.ts, p.method, p.path, p.status, p.latency_ms, p.client) == \
        (3601, "GET", "/api/cart", 200, 84, "web"), f"a well-formed line must parse into its six fields; got {p!r}"
    bad_lines = ["", "-", "5 GET /api/cart 200", "5 GET /api/cart OK 80 web", "5 GET /api/cart 200 -5 web",
                 "5 GET /api/cart 99 10 web", "5 GET /api/cart 600 10 web", "-1 GET /api/cart 200 10 web",
                 "5 GET /api/cart 200 10 web extra", "x GET /api/cart 200 10 web"]
    for line in bad_lines:
        assert mod.parse_line(line) is None, f"parse_line({line!r}) must return None (malformed), got {mod.parse_line(line)!r}"

    R = mod.Request
    assert mod.is_valid(R(0, "GET", "/api/cart", 200, 10, "web")), "an ordinary /api request is valid"
    assert mod.is_valid(R(0, "GET", "/api/cart", 500, 10, "web")), "a 5xx stays valid: failures must stay in the denominator"
    assert mod.is_valid(R(0, "GET", "/api/cart", 404, 10, "partner")), "a 404 is valid"
    assert not mod.is_valid(R(0, "GET", "/api/health", 200, 1, "probe")), "health checks are excluded"
    assert not mod.is_valid(R(0, "GET", "/api/cart", 200, 10, "loadtest")), "the load-test client is excluded"
    assert not mod.is_valid(R(0, "GET", "/static/app.js", 200, 10, "web")), "only /api/* is in scope"
    for status, good in [(200, True), (201, True), (301, True), (400, True), (404, True), (499, True),
                         (429, False), (500, False), (502, False), (503, False), (599, False)]:
        got = mod.is_good_availability(R(0, "GET", "/api/cart", status, 10, "web"))
        assert got is good or got == good, f"status {status} should be {'good' if good else 'bad'} for availability"
    for status, lat, good in [(200, 300, True), (200, 301, False), (200, 0, True), (404, 120, True),
                              (500, 5, False), (429, 5, False), (200, 5000, False)]:
        got = mod.is_good_latency(R(0, "GET", "/api/cart", status, lat, "web"))
        assert bool(got) is good, (f"status {status} in {lat} ms should be {'good' if good else 'bad'} for latency "
                                   "(good means non-5xx, non-429 AND latency_ms <= 300; a fast error is not a fast success)")
    assert mod.is_good_latency(R(0, "GET", "/api/cart", 200, 450, "web"), 500), "the threshold is a parameter"

    crafted = [
        "1 GET /api/cart 200 80 web",            # valid, good, fast
        "2 GET /api/cart 200 300 web",           # valid, good, fast (boundary)
        "3 GET /api/cart 200 301 web",           # valid, good, slow
        "4 GET /api/cart 404 20 app",            # valid, good, fast
        "5 GET /api/cart 429 2 app",             # valid, bad
        "6 GET /api/cart 500 5 web",             # valid, bad
        "7 GET /api/health 200 1 probe",         # excluded
        "8 GET /api/cart 200 10 loadtest",       # excluded
        "9 GET /static/x.css 200 10 web",        # excluded
        "garbage",                               # skipped
        "10 GET /api/search 503 900 partner",    # valid, bad
    ]
    r = mod.compute_slis(crafted)
    got = (r.valid, r.good_availability, r.good_latency, r.skipped)
    assert got == (7, 4, 3, 1), (f"crafted log: expected valid=7 good_availability=4 good_latency=3 skipped=1, got "
                                 f"valid={got[0]} good_availability={got[1]} good_latency={got[2]} skipped={got[3]}")
    assert near(r.availability, 4 / 7) and near(r.latency, 3 / 7), "availability and latency are good/valid"
    assert mod.compute_slis([]).availability == 1.0, "no valid events: nothing went wrong, availability 1.0"
    assert mod.compute_slis(crafted, 80).good_latency == 2, "the latency threshold is a parameter of compute_slis"

    note = ""
    for s in seeds(range(1, 7)):
        lines = mod.generate_log(s)
        r = mod.compute_slis(lines)
        v, ga, gl, sk = oracle(lines)
        assert (r.valid, r.good_availability, r.good_latency, r.skipped) == (v, ga, gl, sk), (
            f"seed {s}: your counts valid={r.valid} good_availability={r.good_availability} good_latency={r.good_latency} "
            f"skipped={r.skipped} differ from the independent oracle {v}, {ga}, {gl}, {sk}")
        assert r.good_latency <= r.good_availability <= r.valid
        if s == 1:
            note = (f"seed 1: {len(lines)} lines, {r.valid} valid, {r.skipped} unparseable; "
                    f"availability {100 * r.availability:.2f}%, latency SLI (<= 300 ms) {100 * r.latency:.2f}%")
    return note


# =============================================================================
# Milestone 2: the error budget
# =============================================================================
def m2():
    assert near(mod.error_budget(0.999), 0.001, 1e-12) and near(mod.error_budget(0.99), 0.01, 1e-12)
    for slo, mins in [(0.999, 43.2), (0.99, 432.0), (0.9999, 4.32), (0.995, 216.0)]:
        got = mod.budget_minutes(slo)
        assert near(got, mins, 1e-6), f"a {slo} SLO over 30 days allows {mins} minutes of full outage, got {got}"
    assert near(mod.budget_minutes(0.999, 7 * 1440), 10.08, 1e-6), "the window is a parameter (in minutes)"
    for burn, hours in [(1, 720.0), (14.4, 50.0), (6, 120.0), (720, 1.0), (2, 360.0)]:
        got = mod.exhaustion_hours(burn)
        assert near(got, hours, 1e-9), f"at burn rate {burn} a 30-day budget lasts {hours} h, got {got}"

    D, W = mod.DAY, mod.WINDOW
    start = 5 * D + 600
    s = mod.constant_series(40 * D, errors={t: 1000 for t in range(start, start + 30)})     # a 30-minute total outage
    v, b = s.valid, s.bad
    r = mod.budget_remaining(v, b, 4 * D, 0.999)
    assert r == 1.0, "no bad requests in the window: the whole budget remains (1.0)"
    r = mod.budget_remaining(v, b, 20 * D, 0.999)
    want = 1 - 30000 / (0.001 * 1000 * (20 * D + 1))
    assert near(r, want, 1e-9), f"day 20: the window is clipped at minute 0; expected {want:.6f}, got {r:.6f}"
    r = mod.budget_remaining(v, b, 30 * D - 1, 0.999)
    want = 1 - 30000 / 43200.0
    assert near(r, want, 1e-9), (f"a 30-minute outage inside a full 30-day window uses 30/43.2 = 69.4% of the budget, "
                                 f"leaving {want:.4f}; got {r:.4f}")
    end_in = start + 29 + W - 1                    # the window still contains the last bad minute
    r_in = mod.budget_remaining(v, b, end_in, 0.999)
    assert near(r_in, 1 - 1000 / 43200.0, 1e-9), f"one bad minute left in the window: expected {1 - 1000 / 43200.0:.6f}, got {r_in:.6f}"
    r_out = mod.budget_remaining(v, b, start + 29 + W, 0.999)
    assert r_out == 1.0 or near(r_out, 1.0, 1e-12), \
        f"one minute later the outage has aged out of the rolling window and the budget is back to 1.0; got {r_out}"
    s2 = mod.constant_series(35 * D, errors={t: 1000 for t in range(10 * D, 10 * D + 60)})
    r = mod.budget_remaining(s2.valid, s2.bad, 34 * D, 0.999)
    assert r < 0 and near(r, 1 - 60000 / 43200.0, 1e-9), f"a 60-minute outage overspends a 43.2-minute budget: expected {1 - 60000 / 43200.0:.4f}, got {r}"
    assert near(mod.budget_remaining(v, b, 30 * D - 1, 0.99), 1 - 30000 / 432000.0, 1e-9), "a looser SLO has a bigger budget"
    assert mod.budget_remaining([0] * 10, [0] * 10, 9, 0.999, window=10) == 1.0, "no valid requests: 1.0"
    assert near(mod.budget_remaining([100] * 10, [5] * 10, 9, 0.9, window=4), 1 - 20 / 40.0, 1e-12), "window is a parameter"

    rng = random.Random(1)
    for _ in range(50):
        n = rng.randint(1, 200)
        vv = [rng.randint(0, 50) for _ in range(n)]
        bb = [rng.randint(0, x) for x in vv]
        end, w = rng.randrange(n), rng.randint(1, 120)
        lo = max(0, end - w + 1)
        vs, bs = sum(vv[lo:end + 1]), sum(bb[lo:end + 1])
        want = 1.0 if vs == 0 else 1 - bs / (0.001 * vs)
        assert near(mod.budget_remaining(vv, bb, end, 0.999, window=w), want, 1e-9), f"random case n={n} end={end} w={w}"
    return ("30-minute total outage at 99.9%: 69.4% of the budget spent, 30.6% left, and it comes back to 100% "
            "exactly 30 days after the last bad minute")


# =============================================================================
# Milestone 3: prefix sums
# =============================================================================
class CountingList(list):
    """A list that counts how many elements anybody reads from it."""
    reads = 0

    def __getitem__(self, k):
        CountingList.reads += len(range(*k.indices(len(self)))) if isinstance(k, slice) else 1
        return list.__getitem__(self, k)

    def __iter__(self):
        CountingList.reads += len(self)
        return list.__iter__(self)


def m3():
    rng = random.Random(3)
    for trial in range(40):
        n = rng.randint(1, 400)
        vv = [rng.randint(0, 60) for _ in range(n)]
        bb = [rng.randint(0, x) for x in vv]
        p = mod.Prefix(mod.Series(vv, bb))
        for _ in range(40):
            end, w = rng.randrange(n), rng.choice([1, 2, 5, 30, 60, 360, 1000])
            lo = max(0, end - w + 1)
            wv, wb = sum(vv[lo:end + 1]), sum(bb[lo:end + 1])
            assert tuple(p.window(end, w)) == (wv, wb), f"trial {trial}: window({end}, {w}) = {p.window(end, w)}, expected {(wv, wb)}"
            assert near(p.error_ratio(end, w), wb / wv if wv else 0.0), f"error_ratio({end}, {w})"
            assert near(p.burn_rate(end, w, 0.999), (wb / wv if wv else 0.0) / 0.001, 1e-6), f"burn_rate({end}, {w})"
            assert near(p.remaining(end, 0.999, w), mod.budget_remaining(vv, bb, end, 0.999, w), 1e-9), f"remaining({end}, ...)"
    p = mod.Prefix(mod.Series([0, 0, 10, 10], [0, 0, 1, 0]))
    assert p.error_ratio(1, 2) == 0.0 and p.burn_rate(1, 2, 0.999) == 0.0, "a window with no valid requests has ratio 0.0"
    assert tuple(p.window(3, 100)) == (20, 1), "a window longer than the history is clipped at minute 0"

    # The point of the milestone: after construction, queries must not touch the minute lists at all.
    minutes = 90 * mod.DAY
    big = mod.Series(CountingList([1000] * minutes), CountingList([(i % 7 == 0) * 3 for i in range(minutes)]))
    t0 = time.time()
    pf = mod.Prefix(big)
    CountingList.reads = 0
    acc = 0.0
    for i in range(30000):
        t = (i * 4363) % minutes
        acc += pf.burn_rate(t, 3 * mod.DAY, 0.999) + pf.remaining(t, 0.999)
        pf.window(t, 5)
    elapsed = time.time() - t0
    assert CountingList.reads == 0, (f"90,000 queries read {CountingList.reads:,} elements of the original lists. "
                                     "After __init__, every query must be answered from the prefix arrays alone: two subtractions")
    assert elapsed < 30, f"90,000 queries took {elapsed:.0f} s: too slow for O(1) queries"
    return (f"90,000 window queries over a {minutes:,}-minute series read 0 original elements "
            f"(brute force would read about {30000 * (3 * mod.DAY + 30 * mod.DAY + 5):,.0f})")


# =============================================================================
# Milestone 4: multi-window, multi-burn-rate rules
# =============================================================================
def m4():
    iv = [(10, 20), (50, 60)]
    assert mod.detection_time(iv, 5) == 5 and mod.detection_time(iv, 10) == 0, "detection time counts from the incident start"
    assert mod.detection_time(iv, 12) == 0, "already firing when the incident starts: detection time 0"
    assert mod.detection_time(iv, 30) == 20 and mod.detection_time(iv, 61) is None and mod.detection_time([], 0) is None
    assert mod.reset_time(iv, 15) == 6, "firing through minute 20, incident over at 15: 15..20 is 6 minutes"
    assert mod.reset_time(iv, 20) == 1 and mod.reset_time(iv, 21) == 0 and mod.reset_time(iv, 40) == 0 and mod.reset_time([], 3) == 0

    # strictness and the two windows, on a hand-built series
    rule = mod.Rule("t", "page", 60, 5, 14.4)

    def series_with(bad_by_minute):
        bad = [0] * 120
        for t, n in bad_by_minute.items():
            bad[t] = n
        return mod.Series([1000] * 120, bad)

    def fires(bad_by_minute, t=100, use_short=True):
        return bool(mod.rule_fires(mod.Prefix(series_with(bad_by_minute)), t, rule, 0.999, use_short))

    hot_recent = {t: 173 for t in range(96, 101)}               # 865 bad in the last 5 minutes
    assert fires(hot_recent), "865 bad of 60,000 is a 14.4167 burn rate in the long window and far above it in the short one: fire"
    assert not fires({t: 172 for t in range(96, 101)}) , "860 bad of 60,000 is a burn rate of 14.33: below 14.4, do not fire"
    old_burst = {t: 289 for t in range(40, 43)}                  # 867 bad, but 60 minutes before t=100: not in the last 5
    assert not fires(old_burst, 100), "the long window is hot but nothing is failing NOW: the short window must veto the alert"
    old2 = {t: 289 for t in range(60, 63)}                       # inside the 60-minute window, outside the last 5 minutes
    assert not fires(old2, 100), "long window hot, short window cold: not firing"
    assert fires(old2, 100, use_short=False), "with use_short=False the long window alone decides: firing"
    edge = mod.Prefix(mod.Series([1000, 1000], [0, 1000]))
    one = mod.Rule("edge", "page", 2, 1, 1.0)
    assert not mod.rule_fires(edge, 1, one, 0.5), ("long-window burn rate exactly equal to the threshold (1.0 here, with the short "
                                                   "window far above it) does NOT fire: strictly above")
    assert mod.rule_fires(mod.Prefix(mod.Series([1000, 1000], [2, 1000])), 1, one, 0.5), "1002 bad of 2000 is just above: fire"
    edge2 = mod.Prefix(mod.Series([1000, 1000], [1000, 0]))
    assert not mod.rule_fires(edge2, 1, mod.Rule("e2", "page", 2, 1, 1.0), 0.5), "short window cold: no fire"
    ivs = mod.firing_intervals(mod.Prefix(series_with({t: 1000 for t in range(10, 12)})), mod.Rule("x", "page", 2, 1, 10.0), 0.999)
    assert [tuple(x) for x in ivs] == [(10, 11)] or [tuple(x) for x in ivs] == [(10, 12)], \
        f"a rule with a 2-minute and 1-minute window over a 2-minute total outage: got {ivs}"
    gaps = mod.firing_intervals(mod.Prefix(series_with({10: 1000, 30: 1000})), mod.Rule("x", "page", 1, 1, 10.0), 0.999)
    assert [tuple(x) for x in gaps] == [(10, 10), (30, 30)], f"two separate bursts must give two intervals, got {gaps}"
    allhot = mod.firing_intervals(mod.Prefix(mod.Series([10, 10, 10], [10, 10, 10])), mod.Rule("x", "page", 1, 1, 10.0), 0.999)
    assert [tuple(x) for x in allhot] == [(0, 2)], f"a run that lasts to the last minute must be closed: got {allhot}"

    # the chapter-7 incidents, with their published numbers
    sc = mod.chapter_scenarios()
    expect = {
        "A outage": {"2% in 1h": 0, "5% in 6h": 2, "10% in 3d": 4},
        "B blip": {},
        "C bad deploy": {"5% in 6h": 216, "10% in 3d": 432},
        "D slow leak": {"10% in 3d": 2160},
    }
    lines = []
    for name, (series, start, end) in sc.items():
        out = mod.evaluate(series)
        got = {r: mod.detection_time(iv, start) for r, iv in out.items() if iv}
        assert got == expect[name], f"incident '{name}': detection times {got}, but chapter 7 reports {expect[name]}"
        lines.append(f"{name:13s} " + (", ".join(f"{r}: {t} min" for r, t in got.items()) or "nothing fires"))
    series, start, end = sc["A outage"]
    both = mod.evaluate(series, use_short=True)["2% in 1h"]
    long_only = mod.evaluate(series, use_short=False)["2% in 1h"]
    r_both, r_long = mod.reset_time(both, end), mod.reset_time(long_only, end)
    assert (r_both, r_long) == (4, 59), f"reset time after the 30-minute outage: expected 4 (both windows) and 59 (long only), got {r_both} and {r_long}"
    lines.append(f"reset after A: {r_long} min with the long window alone, {r_both} min with the 5-minute window as well")

    # noisy seeded incidents: severe pages fast, brief spikes never page, slow leaks only ticket
    paging = {"2% in 1h", "5% in 6h"}
    for fam, must in [("outage", "page"), ("partial", "page"), ("bad_deploy", "page"), ("slow_leak", "ticket"),
                      ("blip", "none"), ("spike_train", "none"), ("quiet", "none"), ("mild", "none")]:
        for s in seeds((11, 12)):
            sc1 = mod.make_scenario(random.Random(s), fam)
            out = mod.evaluate(sc1.series)
            fired_page = [r for r in paging if out[r]]
            fired_ticket = bool(out["10% in 3d"])
            got = "page" if fired_page else "ticket" if fired_ticket else "none"
            assert got == must, (f"seed {s}, family {fam}: expected '{must}', got '{got}' "
                                 f"(fired: {[r for r, i in out.items() if i]})")
            if fam == "outage":
                d = min(mod.detection_time(out[r], sc1.start) for r in fired_page)
                assert d <= 3, f"seed {s}: a total outage should page within 3 minutes, took {d}"
    return "\n".join(lines)


# =============================================================================
# Milestone 5: against a naive threshold
# =============================================================================
def m5():
    R = mod.RULES
    assert mod.verdict({"2% in 1h": [(1, 2)], "5% in 6h": [], "10% in 3d": []}, R) == "page"
    assert mod.verdict({"2% in 1h": [], "5% in 6h": [(4, 9)], "10% in 3d": [(4, 9)]}, R) == "page"
    assert mod.verdict({"2% in 1h": [], "5% in 6h": [], "10% in 3d": [(4, 9)]}, R) == "ticket"
    assert mod.verdict({"2% in 1h": [], "5% in 6h": [], "10% in 3d": []}, R) == "none"
    assert tuple(mod.confusion(["page", "none", "ticket", "page", "none"], ["page", "page", "page", "none", "none"], "page")) == (1, 2, 1, 1), \
        "confusion(labels, verdicts, 'page') = (tp, fp, fn, tn): predicted page & labelled page is a tp; predicted page & labelled anything else is a fp"
    assert tuple(mod.confusion(["ticket", "none"], ["ticket", "ticket"], "ticket")) == (1, 1, 0, 0)
    assert mod.precision_recall(3, 1, 1) == (0.75, 0.75) and mod.precision_recall(0, 0, 0) == (1.0, 1.0)
    assert mod.precision_recall(0, 0, 4) == (1.0, 0.0) and mod.precision_recall(0, 5, 0) == (0.0, 1.0)

    ivs = [(0, 3), (2, 6), (10, 12), (13, 14), (20, 25)]
    assert mod.merge_intervals(ivs) == [(0, 6), (10, 14), (20, 25)], "merge_intervals is given: touching intervals join"

    note = []
    for s in seeds((2024, 7, 99)):
        scs = mod.make_scenarios(s, 48)
        multi = mod.score_policy(scs, mod.RULES)
        naive = mod.score_policy(scs, mod.NAIVE)
        hour = mod.score_policy(scs, mod.ONE_HOUR)
        six = mod.score_policy(scs, mod.SIX_HOURS)
        longonly = mod.score_policy(scs, mod.RULES, use_short=False)
        fams = {}
        for sc, v in zip(scs, naive["verdicts"]):
            if v == "page" and sc.label != "page":
                fams[sc.family] = fams.get(sc.family, 0) + 1
        assert multi["fp"] == 0 and multi["precision"] == 1.0, (
            f"seed {s}: the burn-rate rules paged {multi['fp']} times for events that were not page-worthy "
            f"({[(i, sc.family) for i, (sc, v) in enumerate(zip(scs, multi['verdicts'])) if v == 'page' and sc.label != 'page']})")
        assert multi["recall"] >= 0.95, f"seed {s}: the burn-rate rules missed {multi['fn']} of {multi['tp'] + multi['fn']} page-worthy incidents"
        assert naive["precision"] < 0.85, (f"seed {s}: expected the naive 1%-over-5-minutes alert to page on brief spikes "
                                            f"(precision < 0.85); got {naive['precision']:.2f}")
        assert naive["recall"] < 0.95, f"seed {s}: expected the naive alert to miss the moderate, steady burns; recall {naive['recall']:.2f}"
        assert multi["precision"] > naive["precision"] and multi["recall"] > naive["recall"], f"seed {s}: the burn-rate rules must beat the naive alert on both"
        assert hour["recall"] < multi["recall"], f"seed {s}: a single 10x-over-1h window should miss the moderate burns (recall {hour['recall']:.2f})"
        assert six["precision"] >= 0.95 and six["recall"] >= 0.95, f"seed {s}: a single 5x-over-6h window should be precise and complete: {six['precision']:.2f}/{six['recall']:.2f}"
        # ...but it is slow to detect and very slow to reset: that is what the multi-window rules fix
        assert six["reset_median"] > 120 and six["reset_median"] > 5 * multi["reset_median"], (
            f"seed {s}: the single 6-hour window should keep paging for hours after the incident (median reset {six['reset_median']}) "
            f"while the multi-window rules clear in tens of minutes ({multi['reset_median']})")
        assert six["detect_median"] > multi["detect_median"], f"seed {s}: the single 6-hour window should detect later than the multi-window rules"
        # the short window buys fast resets without changing what is caught
        assert longonly["tp"] == multi["tp"] and longonly["fp"] == multi["fp"], f"seed {s}: the short window must not change which incidents page"
        assert longonly["reset_median"] > 4 * multi["reset_median"], f"seed {s}: without the short window the alert should stay on far longer (reset {longonly['reset_median']} vs {multi['reset_median']})"
        assert set(multi["detect"]) >= {"outage", "partial", "bad_deploy"}, f"seed {s}: detection times were not recorded for every caught family"
        med = {f: mod.median(v) for f, v in multi["detect"].items()}
        assert med["outage"] <= 3 and med["partial"] < med["bad_deploy"], f"seed {s}: median detection times look wrong: {med}"
        row = lambda name, r: f"{name:22s} precision {r['precision']:.2f}  recall {r['recall']:.2f}  detect {r['detect_median']:>5.1f} min  reset {r['reset_median']:>5.1f} min"
        note.append(f"seed {s}  (naive false pages: {', '.join(f'{k} x{v}' for k, v in sorted(fams.items()))})")
        note += ["  " + row(n, r) for n, r in (("multi-window, multi-burn", multi), ("naive 1% over 5m", naive),
                                              ("10x over 1h", hour), ("5x over 6h", six), ("long windows only", longonly))]
    return "\n".join(note)


MILESTONES = [
    (1, "Milestone 1: SLIs from a request log", m1),
    (2, "Milestone 2: the error budget over a rolling window", m2),
    (3, "Milestone 3: burn rate over any window, in O(1)", m3),
    (4, "Milestone 4: multi-window, multi-burn-rate alerts", m4),
    (5, "Milestone 5: burn-rate rules vs a naive threshold", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
