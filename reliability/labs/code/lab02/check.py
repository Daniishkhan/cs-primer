"""Self-check for Lab 2: A Metrics Library.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 2     # milestone 4, replaying ONLY fleet seed 2

No network, no threads, no clock: every number is computed from seeded random
generators, so every run is identical. The exposition checks use a validator written
for this file that knows the format's rules independently of your code.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import math
import os
import random
import re
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


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception as e:
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    return False


# =============================================================================
# Milestone 1: counters, gauges, labels, cardinality
# =============================================================================
def m1():
    reg = mod.Registry(max_series=50)
    c = mod.Counter("http_requests_total", "Requests.", ("route", "status"), reg)
    c.labels(route="/cart", status=200).inc()
    c.labels(status="200", route="/cart").inc(2)
    assert c.labels(route="/cart", status=200).value == 3, "label order and value type must not matter: status=200 and status='200' are one series"
    assert len(c.children) == 1 and ("/cart", "200") in c.children, \
        f"children are keyed by the label VALUES as str, in declared order; got {list(c.children)}"
    assert raises(ValueError, c.labels, route="/cart"), "a missing label must raise ValueError"
    assert raises(ValueError, c.labels, route="/cart", status=200, user="u1"), "an extra label must raise ValueError"
    assert raises(ValueError, c.labels), "no labels at all, on a metric that declares two, must raise ValueError"
    assert len(c.children) == 1, "a refused call must not leave a child behind"
    assert raises(ValueError, c.labels(route="/cart", status=200).inc, -1), "a counter cannot go down"
    assert c.labels(route="/cart", status=200).value == 3, "a refused decrement must change nothing"
    c.labels(route="/cart", status=200).inc(0)

    g = mod.Gauge("queue_depth", "Depth.", (), reg)
    g.set(5); g.inc(); g.inc(2.5); g.dec(); g.dec(10)
    assert near(g.labels().value, -2.5), f"a gauge goes up and down (and below zero): expected -2.5, got {g.labels().value}"
    solo = mod.Counter("jobs_done_total", "Jobs.", (), reg)
    solo.inc(); solo.inc(4)
    assert solo.labels().value == 5, "an unlabelled counter has exactly one child, reachable as labels()"

    assert raises(ValueError, mod.Counter, "requests", "no _total suffix")
    assert raises(ValueError, mod.Gauge, "9lives", "bad name")
    assert raises(ValueError, mod.Gauge, "ok_name", "bad label", ("bad-label",))
    assert raises(ValueError, mod.Gauge, "ok_name", "reserved label", ("__x",))
    assert raises(ValueError, mod.Gauge, "ok_name", "dup labels", ("a", "a"))
    assert raises(ValueError, mod.Gauge, "queue_depth", "same name again", (), reg), "registering a name twice must raise ValueError"
    assert "queue_depth" in reg.metrics and len(reg.metrics) == 3

    # cardinality: the limit is per metric, counted in series, and revisiting is free
    reg = mod.Registry(max_series=50)
    c = mod.Counter("http_requests_total", "Requests.", ("route", "status"), reg)
    for i in range(50):
        c.labels(route=f"/r{i}", status=200).inc()
    assert len(c.children) == 50 and reg.series_count() == 50, "50 series are exactly at the limit: all admitted"
    for i in range(50):
        c.labels(route=f"/r{i}", status=200).inc()          # revisits must be free
    assert c.labels(route="/r7", status=200).value == 2, "revisiting an existing combination keeps counting"
    try:
        c.labels(route="/r50", status=200)
    except mod.CardinalityError as e:
        assert "http_requests_total" in str(e) and "50" in str(e), f"the message should name the metric and the limit; got: {e}"
    else:
        raise AssertionError("the 51st label combination should raise CardinalityError")
    assert len(c.children) == 50 and reg.rejected.get("http_requests_total") == 1, \
        "a refusal creates nothing and is counted in registry.rejected[name]"
    other = mod.Counter("other_total", "Another metric.", ("k",), reg)
    other.labels(k="a").inc()
    assert len(other.children) == 1, "the limit is per metric: a full metric must not block a different one"
    c.labels(route="/r3", status=200).inc()

    # the classic mistake: a user id as a label
    reg = mod.Registry(max_series=1000)
    c = mod.Counter("http_requests_total", "Requests.", ("route", "status", "user_id"), reg)
    routes = [f"/api/r{i}" for i in range(20)]
    admitted = refused = 0
    rng = random.Random(1)
    for _ in range(20000):
        try:
            c.labels(route=rng.choice(routes), status=rng.choice([200, 200, 200, 404, 500]), user_id=f"u{rng.randrange(5000)}").inc()
            admitted += 1
        except mod.CardinalityError:
            refused += 1
    assert len(c.children) == 1000 and reg.series_count() == 1000, f"series must stop at the limit, got {len(c.children)}"
    assert refused > 0 and reg.rejected["http_requests_total"] == refused
    return (f"20 routes x 5 statuses is 100 series and fits; add user_id (5,000 values) and the registry stops at "
            f"{len(c.children)} series, refusing {refused:,} of 20,000 increments")


# =============================================================================
# Milestone 2: histograms
# =============================================================================
def m2():
    assert mod.check_bounds([1, 2, 5]) == (1.0, 2.0, 5.0)
    assert mod.check_bounds([1, 2, float("inf")]) == (1.0, 2.0), "a trailing +Inf is accepted and dropped (it is implicit)"
    for bad in ([], [float("inf")], [2, 1], [1, 1], [1, float("nan")], [float("-inf"), 1], [1, float("inf"), 2]):
        assert raises(ValueError, mod.check_bounds, bad), f"check_bounds({bad}) must raise ValueError"
    eb = mod.exponential_buckets(5, 2, 4)
    assert [float(x) for x in eb] == [5.0, 10.0, 20.0, 40.0], f"exponential_buckets(5, 2, 4) -> [5, 10, 20, 40]; got {eb}"
    assert len(mod.exponential_buckets(1, 1.25, 40)) == 40
    for a in ((0, 2, 3), (1, 1, 3), (1, 2, 0), (-1, 2, 3)):
        assert raises(ValueError, mod.exponential_buckets, *a), f"exponential_buckets{a} must raise ValueError"

    reg = mod.Registry()
    h = mod.Histogram("lat_seconds", "Latency.", [0.1, 0.5, 1.0], ("route",), reg)
    ch = h.labels(route="/a")
    assert ch.cumulative() == [0, 0, 0, 0] and ch.count == 0 and ch.sum == 0, "a new histogram is all zeros (3 bounds + the +Inf bucket)"
    for v in (0.05, 0.1, 0.1000001, 0.5, 0.7, 5.0, 100):
        ch.observe(v)
    assert ch.cumulative() == [2, 4, 5, 7], (f"0.1 belongs to le=0.1 (le means <=), 0.5 to le=0.5; "
                                              f"cumulative should be [2, 4, 5, 7], got {ch.cumulative()}")
    assert ch.count == 7 and near(ch.sum, 0.05 + 0.1 + 0.1000001 + 0.5 + 0.7 + 5.0 + 100), "count and sum are kept alongside the buckets"
    assert ch.cumulative()[-1] == ch.count, "the +Inf bucket always equals the count"
    assert all(a <= b for a, b in zip(ch.cumulative(), ch.cumulative()[1:])), "cumulative counts never decrease"
    assert raises(ValueError, ch.observe, float("nan")), "NaN must be refused"
    assert ch.count == 7, "a refused observation changes nothing"
    ch.observe(-3)
    assert ch.cumulative()[0] == 3, "values below the first bound (even negative ones) land in the first bucket"
    ch.observe(float("inf"))
    assert ch.cumulative() == [3, 5, 6, 9] or ch.cumulative()[-1] == 9, "+Inf lands in the +Inf bucket"
    assert raises(ValueError, mod.Histogram, "x_seconds", "bad", [2, 1])
    assert raises(ValueError, mod.Histogram, "x_seconds", "le is reserved", [1], ("le",))
    assert h.series_per_child() == 3 + 1 + 2, "each child costs a series per bucket (incl. +Inf) plus _sum and _count"

    # many random observations: cumulative counts must match brute-force counting
    for s in seeds(range(1, 6)):
        rng = random.Random(s)
        bounds = sorted(rng.sample(range(1, 500), rng.randint(3, 12)))
        hh = mod.Histogram(f"h{s}_seconds", "x", bounds)
        xs = [rng.lognormvariate(4, 1) for _ in range(3000)]
        for x in xs:
            hh.observe(x)
        want = [sum(1 for x in xs if x <= b) for b in bounds] + [len(xs)]
        got = hh.labels().cumulative()
        assert got == want, f"seed {s}: cumulative counts differ from brute force: got {got}, expected {want}"
        assert near(hh.labels().sum, sum(xs), 1e-6) and hh.labels().count == len(xs)

    # cardinality accounts for buckets
    reg = mod.Registry(max_series=20)
    hv = mod.Histogram("req_seconds", "x", [0.1, 0.2, 0.5, 1, 2], ("route",), reg)     # 5 + 1 + 2 = 8 series per child
    hv.labels(route="a"); hv.labels(route="b")
    assert raises(mod.CardinalityError, hv.labels, route="c"), "3 children x 8 series = 24 > 20: the third must be refused"
    return "cumulative counts match brute force over 5 seeds x 3,000 values; a histogram child costs buckets + 3 series"


# =============================================================================
# Milestone 3: quantiles from buckets
# =============================================================================
def bucket_of(bounds, v):
    i = 0
    while i < len(bounds) and v > bounds[i]:
        i += 1
    lo = bounds[i - 1] if i else 0.0
    hi = bounds[i] if i < len(bounds) else float("inf")
    return lo, hi


def m3():
    b = (0.1, 0.2, 0.5, 1.0)
    cum = (10, 60, 90, 100, 100)
    for q, want in [(0.05, 0.05), (0.5, 0.18), (0.1, 0.1), (0.95, 0.75), (0.999, 0.995), (1.0, 1.0), (0.0, 0.0)]:
        got = mod.quantile(q, b, cum)
        assert near(got, want, 1e-9), f"quantile({q}) on bounds {b}, cumulative {cum}: expected {want}, got {got}"
    cum_inf = (10, 60, 90, 95, 100)
    assert near(mod.quantile(0.5, b, cum_inf), 0.18) and near(mod.quantile(0.9, b, cum_inf), 0.5)
    assert near(mod.quantile(0.99, b, cum_inf), 1.0), "a rank in the +Inf bucket has no upper bound: return the largest finite bound"
    assert math.isnan(mod.quantile(0.5, b, (0, 0, 0, 0, 0))), "no observations: NaN"
    assert mod.quantile(-0.1, b, cum) == float("-inf") and mod.quantile(1.1, b, cum) == float("inf")
    assert near(mod.quantile(0.5, (10, 20, 30), (0, 0, 8, 8)), 25.0), "empty buckets are skipped: all 8 values in (20, 30] -> median 25"
    assert near(mod.quantile(0.0, (10, 20, 30), (0, 0, 8, 8)), 20.0), "q=0 returns the lower bound of the first non-empty bucket"
    assert near(mod.quantile(0.5, (10,), (4, 4)), 5.0), "the first bucket starts at 0"
    # the honest worst case: every value is exactly 51 in the bucket (50, 100]
    h = mod.Histogram("w_ms", "x", [50, 100, 200])
    for _ in range(1000):
        h.observe(51)
    est = h.labels().quantile(0.5)
    assert near(est, 75.0), f"all values are 51 in (50, 100]: the estimate assumes an even spread and says 75; got {est}"
    assert abs(est - 51) <= 50, "...an error of 24, bounded by the bucket width of 50"

    # error bounds against exact quantiles, on three layouts
    qs = (0.5, 0.9, 0.99, 0.999)
    layouts = {
        "exponential x1.25": (mod.exponential_buckets(1, 1.25, 40), 0.25),
        "exponential x2": (mod.exponential_buckets(1, 2, 14), 1.0),
        "linear 50 ms": ([50.0 * i for i in range(1, 41)], None),
    }
    lines = []
    for s in seeds((1, 2, 3)):
        rng = random.Random(s)
        xs = [rng.lognormvariate(math.log(40), 0.6) + (rng.uniform(100, 600) if rng.random() < 0.02 else 0) for _ in range(30000)]
        assert max(xs) < 1800, "test data should fit inside the finite buckets"
        for lname, (bounds, rel) in layouts.items():
            h = mod.Histogram(f"lat{s}_ms", "x", bounds)
            for x in xs:
                h.observe(x)
            ch = h.labels()
            row = []
            for q in qs:
                exact = mod.exact_quantile(xs, q)
                est = ch.quantile(q)
                lo, hi = bucket_of(ch.bounds, exact)
                assert lo - 1e-9 <= est <= hi + 1e-9, (f"seed {s}, {lname}, q={q}: the estimate {est:.2f} left the bucket "
                                                       f"({lo:.2f}, {hi:.2f}] that holds the exact quantile {exact:.2f}")
                assert abs(est - exact) <= hi - lo + 1e-9, f"seed {s}, {lname}, q={q}: error {abs(est - exact):.2f} exceeds the bucket width {hi - lo:.2f}"
                if rel is not None and lo >= bounds[0]:
                    assert abs(est - exact) / exact <= rel + 1e-9, (f"seed {s}, {lname}, q={q}: relative error "
                                                                     f"{abs(est - exact) / exact:.3f} exceeds {rel}")
                row.append(f"p{q * 100:g} {100 * (est - exact) / exact:+5.1f}%")
            if s == seeds((1,))[0]:
                lines.append(f"{lname:18s} error vs exact: " + "  ".join(row))
    return "seed " + str(seeds((1,))[0]) + ", 30,000 values; the estimate always stays inside the exact value's bucket:\n" + "\n".join(lines)


# =============================================================================
# Milestone 4: merging
# =============================================================================
def build_hosts(bounds, hosts, name):
    snaps = []
    for i, xs in enumerate(hosts):
        h = mod.Histogram(f"{name}{i}_ms", "x", bounds)
        for x in xs:
            h.observe(x)
        snaps.append(h.labels().snapshot())
    return snaps


def m4():
    bounds = [10, 50, 100, 500]
    rng = random.Random(0)
    parts = [[rng.uniform(0, 600) for _ in range(rng.randint(1, 200))] for _ in range(5)]
    snaps = build_hosts(bounds, parts, "p")
    whole = build_hosts(bounds, [[x for p in parts for x in p]], "w")[0]
    m = mod.merge(snaps)
    assert m.bounds == whole.bounds and tuple(m.cumulative) == tuple(whole.cumulative), "merging per-host histograms must equal one histogram of all observations"
    assert m.count == whole.count and near(m.sum, whole.sum, 1e-6)
    keep = [tuple(s.cumulative) for s in snaps]
    mod.merge(snaps)
    assert [tuple(s.cumulative) for s in snaps] == keep, "merge must not modify its inputs"
    for order in ([4, 3, 2, 1, 0], [2, 0, 4, 1, 3]):
        mo = mod.merge([snaps[i] for i in order])
        assert tuple(mo.cumulative) == tuple(m.cumulative), "merge order must not matter (addition is commutative)"
    left = mod.merge([mod.merge(snaps[:2]), mod.merge(snaps[2:])])
    assert tuple(left.cumulative) == tuple(m.cumulative), "regrouping must not matter (addition is associative): merge hosts, then time slices, or the reverse"
    assert mod.merge(snaps[:1]).cumulative == snaps[0].cumulative
    other = build_hosts([10, 50, 200], parts[:1], "q")[0]
    assert raises(ValueError, mod.merge, [snaps[0], other]), "different bucket bounds cannot be merged"
    assert raises(ValueError, mod.merge, []), "an empty merge is an error"

    # the fleets
    layout = mod.exponential_buckets(1, 1.25, 40)
    lines = []
    for s in seeds((42, 7, 2024)):
        for kind in ("sick-small", "sick-large"):
            hosts = mod.fleet(s, kind)
            allx = [x for xs in hosts for x in xs]
            truth = mod.exact_quantile(allx, 0.99)
            snaps = build_hosts(layout, hosts, "f")
            merged = mod.merge(snaps)
            est = merged.quantile(0.99)
            avg = mod.average_of_quantiles(snaps, 0.99)
            lo, hi = bucket_of(merged.bounds, truth)
            assert lo - 1e-9 <= est <= hi + 1e-9 and abs(est - truth) / truth <= 0.25 + 1e-9, (
                f"seed {s} {kind}: the merged-histogram p99 {est:.1f} ms should lie in the bucket ({lo:.1f}, {hi:.1f}] "
                f"of the true p99 {truth:.1f} ms")
            assert abs(avg - truth) / truth > 0.5, (f"seed {s} {kind}: expected the average of per-host p99s ({avg:.1f}) to be badly wrong "
                                                    f"against the true p99 ({truth:.1f})")
            if kind == "sick-small":
                assert avg > 2 * truth, f"seed {s}: with a small sick host the average of p99s should OVERSTATE the truth several times over"
            else:
                assert avg < 0.8 * truth, f"seed {s}: with a sick host holding a quarter of the traffic the average of p99s should UNDERSTATE the truth"
            if s == seeds((42,))[0]:
                lines.append(f"{kind:10s} true p99 {truth:6.1f} ms | merged histogram {est:6.1f} ms ({100 * (est - truth) / truth:+5.1f}%) "
                             f"| average of per-host p99s {avg:6.1f} ms ({100 * (avg - truth) / truth:+6.1f}%)")
    return "\n".join(lines)


# =============================================================================
# Milestone 5: the exposition format, checked against its rules
# =============================================================================
NAME = r"[a-zA-Z_:][a-zA-Z0-9_:]*"
LAB = r'[a-zA-Z_][a-zA-Z0-9_]*="(?:[^"\\\n]|\\[\\"n])*"'
SAMPLE = re.compile(rf"^({NAME})(?:\{{((?:{LAB})(?:,{LAB})*)\}})? (\S+)$")
LABEL_PAIR = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\\n]|\\[\\"n])*)"')
HELP = re.compile(rf"^# HELP ({NAME}) ((?:[^\\\n]|\\[\\n])*)$")
TYPE = re.compile(rf"^# TYPE ({NAME}) (counter|gauge|histogram|summary|untyped)$")


def unescape(s):
    return re.sub(r"\\([\\\"n])", lambda m: "\n" if m.group(1) == "n" else m.group(1), s)


def parse_value(tok):
    if tok in ("+Inf", "-Inf", "NaN"):
        return float(tok.replace("Inf", "inf").replace("NaN", "nan"))
    if not re.match(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$", tok):
        raise ValueError(f"not a number: {tok!r}")
    return float(tok)


def validate(text):
    """Return (list of problems, dict family -> list of (sample name, labels dict, value))."""
    problems, fams, order = [], {}, []
    if text and not text.endswith("\n"):
        problems.append("the text must end with a newline")
    cur, seen_series, helped = None, set(), set()
    for no, line in enumerate(text.split("\n")[:-1] if text.endswith("\n") else text.split("\n"), 1):
        if line == "":
            problems.append(f"line {no}: blank lines are not allowed here")
            continue
        if line.startswith("# HELP"):
            m = HELP.match(line)
            if not m:
                problems.append(f"line {no}: malformed HELP line: {line!r}")
                continue
            if m.group(1) in fams:
                problems.append(f"line {no}: family {m.group(1)} appears twice (families must be contiguous)")
            helped.add(m.group(1))
            cur = None
            continue
        if line.startswith("# TYPE"):
            m = TYPE.match(line)
            if not m:
                problems.append(f"line {no}: malformed TYPE line: {line!r}")
                continue
            name = m.group(1)
            if name not in helped:
                problems.append(f"line {no}: TYPE for {name} without a HELP line before it")
            if name in fams:
                problems.append(f"line {no}: second TYPE line for {name}")
            fams[name] = {"type": m.group(2), "samples": []}
            order.append(name)
            cur = name
            continue
        if line.startswith("#"):
            continue
        m = SAMPLE.match(line)
        if not m:
            problems.append(f"line {no}: not a valid sample line: {line!r}")
            continue
        sname, labtxt, valtxt = m.groups()
        labels = {k: unescape(v) for k, v in LABEL_PAIR.findall(labtxt or "")}
        if len(labels) != len(LABEL_PAIR.findall(labtxt or "")):
            problems.append(f"line {no}: duplicate label name in {line!r}")
        try:
            val = parse_value(valtxt)
        except ValueError as e:
            problems.append(f"line {no}: {e}")
            continue
        if cur is None:
            problems.append(f"line {no}: sample {sname} before any TYPE line")
            continue
        fam = fams[cur]
        allowed = [cur] if fam["type"] in ("counter", "gauge") else [cur + "_bucket", cur + "_sum", cur + "_count"]
        if sname not in allowed:
            problems.append(f"line {no}: sample {sname} does not belong to {fam['type']} family {cur}")
        key = (sname, tuple(sorted(labels.items())))
        if key in seen_series:
            problems.append(f"line {no}: duplicate series {sname}{labels}")
        seen_series.add(key)
        fam["samples"].append((sname, labels, val))
    for name in order:
        fam = fams[name]
        if fam["type"] == "counter":
            for s, lab, v in fam["samples"]:
                if v < 0 or math.isnan(v):
                    problems.append(f"counter {s}{lab} has value {v}")
            if not name.endswith("_total"):
                problems.append(f"counter {name} should end in _total")
        if fam["type"] == "histogram":
            groups = {}
            for s, lab, v in fam["samples"]:
                base = tuple(sorted((k, x) for k, x in lab.items() if k != "le"))
                groups.setdefault(base, {"b": [], "sum": [], "count": []})
                if s.endswith("_bucket"):
                    if "le" not in lab:
                        problems.append(f"{s}{lab}: bucket without an le label")
                    else:
                        groups[base]["b"].append((lab["le"], v))
                elif s.endswith("_sum"):
                    groups[base]["sum"].append(v)
                else:
                    groups[base]["count"].append(v)
            for base, g in groups.items():
                who = f"{name}{dict(base)}"
                if len(g["sum"]) != 1 or len(g["count"]) != 1:
                    problems.append(f"{who}: needs exactly one _sum and one _count")
                    continue
                if not g["b"] or g["b"][-1][0] != "+Inf":
                    problems.append(f"{who}: the last bucket must be le=\"+Inf\"")
                    continue
                try:
                    les = [parse_value(le) for le, _ in g["b"]]
                except ValueError:
                    problems.append(f"{who}: unparseable le value")
                    continue
                if any(a >= b for a, b in zip(les, les[1:])):
                    problems.append(f"{who}: le bounds must be strictly increasing, got {[le for le, _ in g['b']]}")
                counts = [v for _, v in g["b"]]
                if any(a > b for a, b in zip(counts, counts[1:])):
                    problems.append(f"{who}: bucket counts must be cumulative (non-decreasing), got {counts}")
                if counts[-1] != g["count"][0]:
                    problems.append(f"{who}: the +Inf bucket ({counts[-1]}) must equal _count ({g['count'][0]})")
    return problems, fams


def m5():
    # the validator itself must catch real mistakes (so a pass means something)
    good = ("# HELP a_total x\n# TYPE a_total counter\na_total{k=\"v\"} 1\n"
            "# HELP h_seconds x\n# TYPE h_seconds histogram\nh_seconds_bucket{le=\"1\"} 1\nh_seconds_bucket{le=\"+Inf\"} 2\n"
            "h_seconds_sum 3\nh_seconds_count 2\n")
    assert validate(good)[0] == [], f"validator self-test failed on a good text: {validate(good)[0]}"
    for broken in (good.replace('{le="+Inf"} 2', '{le="+Inf"} 3'),
                   good.replace("h_seconds_count 2\n", ""),
                   good.replace('h_seconds_bucket{le="+Inf"} 2\n', ""),
                   good.replace("# TYPE a_total counter\n", ""),
                   good.replace('{k="v"}', '{k=v}'),
                   good.replace('h_seconds_bucket{le="1"} 1', 'h_seconds_bucket{le="1"} 5'),
                   good.rstrip("\n")):
        assert validate(broken)[0], "the validator failed to flag a broken exposition"

    assert mod.format_value(5) == "5" and mod.format_value(5.0) == "5" and mod.format_value(1.0) == "1", "whole numbers print without .0"
    assert mod.format_value(0.25) == "0.25" and mod.format_value(-2.5) == "-2.5"
    assert mod.format_value(float("inf")) == "+Inf" and mod.format_value(float("-inf")) == "-Inf" and mod.format_value(float("nan")) == "NaN"
    assert mod.escape_label_value('a"b\\c\nd') == 'a\\"b\\\\c\\nd', "label values escape backslash, quote and newline"
    assert mod.escape_help('x\\y\nz "q"') == 'x\\\\y\\nz "q"', "HELP escapes only backslash and newline (quotes stay)"

    reg = mod.Registry()
    c = mod.Counter("http_requests_total", "Total requests.", ("route", "status"), reg)
    c.labels(route="/cart", status=500).inc()
    c.labels(route="/cart", status=200).inc(3)
    g = mod.Gauge("queue_depth", "Items waiting.", (), reg)
    g.set(7)
    h = mod.Histogram("request_duration_seconds", "Request latency.", [0.125, 0.5, 1], ("route",), reg)
    for v in (0.0625, 0.125, 0.25, 2.0):
        h.labels(route="/cart").observe(v)
    golden = (
        "# HELP http_requests_total Total requests.\n"
        "# TYPE http_requests_total counter\n"
        'http_requests_total{route="/cart",status="200"} 3\n'
        'http_requests_total{route="/cart",status="500"} 1\n'
        "# HELP queue_depth Items waiting.\n"
        "# TYPE queue_depth gauge\n"
        "queue_depth 7\n"
        "# HELP request_duration_seconds Request latency.\n"
        "# TYPE request_duration_seconds histogram\n"
        'request_duration_seconds_bucket{route="/cart",le="0.125"} 2\n'
        'request_duration_seconds_bucket{route="/cart",le="0.5"} 3\n'
        'request_duration_seconds_bucket{route="/cart",le="1"} 3\n'
        'request_duration_seconds_bucket{route="/cart",le="+Inf"} 4\n'
        'request_duration_seconds_sum{route="/cart"} 2.4375\n'
        'request_duration_seconds_count{route="/cart"} 4\n')
    text = reg.expose()
    assert text == golden, "exposition differs from the expected text.\n--- yours ---\n" + text + "--- expected ---\n" + golden
    probs, _ = validate(text)
    assert not probs, "format problems: " + "; ".join(probs)

    # awkward content: escaping, empty children, specials; then a randomised registry
    reg = mod.Registry()
    c = mod.Counter("odd_total", 'Help with \\ backslash\nand newline "q".', ("path",), reg)
    c.labels(path='C:\\dir "x"\nnext').inc(2)
    mod.Gauge("never_used", "A labelled gauge with no children yet.", ("k",), reg)
    mod.Gauge("weird", "specials", (), reg).set(float("inf"))
    text = reg.expose()
    probs, fams = validate(text)
    assert not probs, "format problems: " + "; ".join(probs) + "\n" + text
    assert fams["odd_total"]["samples"][0][1]["path"] == 'C:\\dir "x"\nnext', "label value must survive escape -> parse"
    assert fams["weird"]["samples"][0][2] == float("inf") and "weird +Inf\n" in text
    assert "# TYPE never_used gauge" in text, "a metric with no children still gets HELP and TYPE lines"
    assert mod.Registry().expose() == "", "an empty registry exposes the empty string"

    lines = []
    for s in seeds(range(1, 9)):
        rng = random.Random(s)
        reg = mod.Registry(max_series=10_000)
        for i in range(rng.randint(2, 5)):
            kind = rng.choice(["c", "g", "h"])
            labs = tuple(rng.sample(["route", "code", "az", "method"], rng.randint(0, 2)))
            name = f"m{i}_" + rng.choice(["alpha", "beta", "gamma"])
            if kind == "c":
                met = mod.Counter(name + "_total", "A counter.", labs, reg)
            elif kind == "g":
                met = mod.Gauge(name, "A gauge.", labs, reg)
            else:
                met = mod.Histogram(name + "_seconds", "A histogram.", sorted(rng.sample([0.005 * 2 ** k for k in range(10)], rng.randint(2, 8))), labs, reg)
            for _ in range(rng.randint(1, 6)):
                kv = {l: rng.choice(["a", "b", 'q"x', "c\\d"]) for l in labs}
                ch = met.labels(**kv)
                for _ in range(rng.randint(1, 40)):
                    if kind == "c":
                        ch.inc(rng.randint(0, 5))
                    elif kind == "g":
                        ch.set(rng.uniform(-5, 5))
                    else:
                        ch.observe(rng.lognormvariate(-3, 1.2))
        text = reg.expose()
        probs, fams = validate(text)
        assert not probs, f"seed {s}: format problems: " + "; ".join(probs[:4]) + "\n" + text[:600]
        # round trip: rebuild a histogram from the TEXT only (as a scraper would) and ask it for a quantile
        for m in reg.collect():
            if m.kind != "histogram":
                continue
            samples = fams[m.name]["samples"]
            for key, child in m.children.items():
                lab = dict(zip(m.labelnames, key))
                bs = [(parse_value(l["le"]), v) for n, l, v in samples if n.endswith("_bucket") and {k: x for k, x in l.items() if k != "le"} == lab]
                parsed_cum = tuple(int(v) for _, v in bs)
                assert parsed_cum == tuple(child.cumulative()), f"seed {s}: scraped buckets differ from the live histogram"
                bounds = tuple(b for b, _ in bs[:-1])
                assert near(mod.quantile(0.9, bounds, parsed_cum), child.quantile(0.9), 1e-9)
        lines.append(len(text.split("\n")) - 1)
    return f"golden text matched; 8 random registries validated ({min(lines)}-{max(lines)} lines each) and scraped back into the same quantiles"


MILESTONES = [
    (1, "Milestone 1: counters, gauges and a registry that refuses cardinality blowups", m1),
    (2, "Milestone 2: a histogram with configurable buckets", m2),
    (3, "Milestone 3: quantiles from buckets, with an honest error bar", m3),
    (4, "Milestone 4: merging hosts (and why the average of p99s is wrong)", m4),
    (5, "Milestone 5: the Prometheus text exposition format", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 2 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
