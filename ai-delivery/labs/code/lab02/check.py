"""Self-check for Lab 2: A Cost & Latency Model.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 6 14    # milestone 6, replaying ONLY the random cases of seed 14

Everything is arithmetic on fixed assumptions (prices, speeds, token counts are ILLUSTRATIVE);
the only randomness is in seeded property checks, and a failure prints its seed. There is no
network and no clock, and the whole check finishes in a fraction of a second.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import contextlib
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


def expect(cond, msg):
    assert cond, msg


@contextlib.contextmanager
def patched(**consts):
    """Temporarily change module constants: your functions must READ them when they run."""
    old = {k: getattr(mod, k) for k in consts}
    for k, v in consts.items():
        setattr(mod, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(mod, k, v)


def wilson_oracle(k, n, z=1.96):
    p = k / n
    a, b, c = 1 + z * z / n, -(2 * p + z * z / n), p * p
    d = math.sqrt(b * b - 4 * a * c)
    return (-b - d) / (2 * a), (-b + d) / (2 * a)


def one_call(model, prefix, var, out, cached):
    """Independent re-derivation of one call's cost, in dollars."""
    pin, pout = mod.PRICE[model]
    if cached > 0:
        in_tokens_cost = prefix * pin * (cached * mod.CACHE_READ + (1 - cached) * mod.CACHE_WRITE) + var * pin
    else:
        in_tokens_cost = (prefix + var) * pin
    return (in_tokens_cost + out * pout) / 1_000_000


# =============================================================================
# Milestone 1: call_cost
# =============================================================================
def m1():
    got = mod.call_cost("mid", 1500, 6000, 300)
    expect(near(got, 0.027), f"mid, 1,500 + 6,000 input and 300 output tokens: (7,500 x 3 + 300 x 15) / 1,000,000 = 0.0270; got {got}")
    got = mod.call_cost("small", 1500, 6000, 300)
    expect(near(got, 0.001305), f"small: (7,500 x 0.15 + 300 x 0.60) / 1e6 = 0.001305; got {got}")
    got = mod.call_cost("mid", 1500, 6000, 300, 0.9)
    expect(near(got, 0.0234675), f"mid with 90% of the prefix cached: prefix is billed at 1500 x (0.9 x 0.10 + 0.1 x 1.25) = 322.5 token-equivalents, "
           f"so (322.5 x 3 + 6,000 x 3 + 300 x 15) / 1e6 = 0.0234675; got {got}")
    got = mod.call_cost("mid", 1500, 6000, 300, 1.0)
    expect(near(got, 0.02295), f"with the whole prefix read from the cache: (150 x 3 + 18,000 + 4,500) / 1e6 = 0.02295; got {got}")
    expect(mod.call_cost("large", 0, 0, 0) == 0, "no tokens, no cost")
    expect(mod.call_cost("mid", 1000, 0, 0, 0.01) > mod.call_cost("mid", 1000, 0, 0, 0.0),
           "a cache that is almost never hit costs MORE than no cache, because the rest of the prefix pays the write premium (1.25x); "
           "cached_share == 0 means caching is off, not 'all writes'")
    for s in seeds(range(1, 21)):
        rng = random.Random(s)
        model = rng.choice(["small", "mid", "large"])
        p, v, o = rng.randint(0, 3000), rng.randint(0, 9000), rng.randint(0, 900)
        c = rng.choice([0.0, 0.25, 0.9, 1.0])
        got = mod.call_cost(model, p, v, o, c)
        expect(near(got, one_call(model, p, v, o, c), 1e-12), f"seed {s}: call_cost({model!r}, {p}, {v}, {o}, {c}) = {got}, expected {one_call(model, p, v, o, c)}")
        expect(near(mod.call_cost(model, 2 * p, 2 * v, 2 * o, c), 2 * got, 1e-12), f"seed {s}: doubling every token count should double the cost")
        expect(mod.call_cost(model, p, v, o, 1.0) <= mod.call_cost(model, p, v, o, 0.5) + 1e-15 or p == 0, f"seed {s}: a higher cached share should never cost more (cache reads are cheaper than writes)")
    return "a 7,500-token letter + 300-token answer: mid 0.0270 USD, small 0.0013 USD, mid with a warm cache 0.0235 USD"


# =============================================================================
# Milestone 2: task_cost, review_cost, total_cost
# =============================================================================
def ref_task(design):
    model, s, c, b = design.get("model", "mid"), design.get("small_share", 0.0), design.get("cached", 0.0), design.get("batch_share", 0.0)
    t = sum((1 - s) * one_call(model, p, v, o, c) + s * one_call("small", p, v, o, c) for _n, p, v, o in mod.CALLS)
    return t * (1 + mod.RETRY) * (1 - b * (1 - mod.BATCH))


def m2():
    designs = [("A  all mid-tier", {}, 0.0431), ("B  + cache the prefixes", {"cached": 0.9}, 0.0373),
               ("C  + route 60% to small", {"cached": 0.9, "small_share": 0.6}, 0.0160),
               ("D  + batch half", {"cached": 0.9, "small_share": 0.6, "batch_share": 0.5}, 0.0120)]
    lines = []
    for name, d, want in designs:
        got = mod.task_cost(d)
        expect(abs(got - want) < 0.00006, f"design {name}: the cost chapter's table says about {want:.4f} USD a task; got {got:.5f}. "
               "Sum the calls, apply the routing mix, multiply by (1 + RETRY), then the batch discount")
        expect(near(got, ref_task(d), 1e-12), f"design {name}: {got} differs from an independent calculation {ref_task(d)}")
        lines.append(f"{name:26s} {got:.4f} USD per task   {got * 1000:6.2f} per 1,000")
    expect(near(mod.review_cost(), 1.12), f"review: 35% x 4 min = 1.4 min at 48 USD/h = 1.12 USD a task; got {mod.review_cost()}")
    expect(near(mod.total_cost({}), mod.task_cost({}) + 1.12), "total_cost = model cost + review cost")
    expect(mod.task_cost({"model": "large"}) > mod.task_cost({}) > mod.task_cost({"model": "small"}), "a larger tier must cost more per task")
    expect(near(mod.task_cost({"small_share": 1.0}), mod.task_cost({"model": "small"})), "routing 100% to small equals running everything on small")
    expect(near(mod.task_cost({"batch_share": 1.0}), 0.5 * mod.task_cost({})), "batching every task halves the cost (BATCH = 0.5)")
    with patched(RETRY=0.0):
        expect(near(mod.task_cost({}), ref_task({}), 1e-12), "with RETRY = 0 the cost should drop by the retry factor: read RETRY when the function runs")
        base0 = mod.task_cost({})
    with patched(RETRY=0.5):
        expect(near(mod.task_cost({}), base0 * 1.5), "RETRY is a constant your function must read when it runs: with RETRY = 0.5 the cost should be 1.5 times the no-retry cost")
    for s in seeds(range(1, 21)):
        rng = random.Random(s)
        d = {"model": rng.choice(["small", "mid", "large"]), "small_share": rng.choice([0, 0.2, 0.5, 0.8]), "cached": rng.choice([0, 0.5, 0.9]),
             "batch_share": rng.choice([0, 0.25, 0.5])}
        expect(near(mod.task_cost(d), ref_task(d), 1e-12), f"seed {s}: task_cost({d}) = {mod.task_cost(d)}, expected {ref_task(d)}")
        expect(near(mod.total_cost(d), ref_task(d) + 1.12, 1e-12), f"seed {s}: total_cost({d}) wrong")
    a, d = mod.task_cost({}), mod.task_cost(designs[3][1])
    return "\n".join(lines) + f"\nhuman review 1.12 USD a task: the model is {a / (a + 1.12):.1%} of design A and {d / (d + 1.12):.1%} of design D"


# =============================================================================
# Milestone 3: latency
# =============================================================================
def ref_pct(design, q):
    s = design.get("small_share", 0.0)
    big = sum(mod.SPEED[design.get("model", "mid")][0] + o / mod.SPEED[design.get("model", "mid")][1] for *_x, o in mod.CALLS)
    small = sum(mod.SPEED["small"][0] + o / mod.SPEED["small"][1] for *_x, o in mod.CALLS)
    out = sorted([(small, s * (1 - mod.RETRY)), (2 * small, s * mod.RETRY), (big, (1 - s) * (1 - mod.RETRY)), (2 * big, (1 - s) * mod.RETRY)])
    cum = 0.0
    for lat, w in out:
        cum += w
        if cum >= q - 1e-9:
            return lat
    return out[-1][0]


def m3():
    expect(near(mod.call_latency("mid", 300), 0.5 + 300 / 90), f"mid: 0.5 s to first token + 300 / 90 tokens per second = 3.83 s; got {mod.call_latency('mid', 300)}")
    expect(near(mod.call_latency("small", 0), 0.25), "with no output tokens the latency is just the time to first token")
    for model, want in (("small", 4.25), ("mid", 28 / 3), ("large", 18.466666666666667)):
        got = mod.path_latency(model)
        expect(near(got, want, 1e-9), f"path_latency({model!r}) should be {want:.3f} s (the two calls run one after the other); got {got}")
    p = lambda d, q: mod.latency_percentile(d, q)
    expect(near(p({}, 0.5), 28 / 3), f"the median of an all-mid design is one pass: 9.33 s; got {p({}, 0.5)}")
    expect(near(p({}, 0.94), 28 / 3), "94% of tasks make no retry, so the 94th percentile is still one pass (9.33 s)")
    expect(near(p({}, 0.95), 56 / 3), f"6% of tasks retry and take twice as long, so the 95th percentile is the DOUBLE pass: 18.67 s; got {p({}, 0.95)}. "
           "Cumulative probability of the one-pass outcomes is 0.94, which has not reached 0.95")
    expect(near(p({"small_share": 0.6}, 0.5), 4.25) and near(p({"small_share": 0.6}, 0.95), 28 / 3),
           f"routing 60% to small: median is a small pass (4.25 s); at the 95th percentile the doubled small pass (8.5 s) comes before the mid pass (9.33 s) in the sorted outcomes, "
           f"the cumulative probability reaches 0.95 only at the mid pass; got {p({'small_share': 0.6}, 0.5)} and {p({'small_share': 0.6}, 0.95)}")
    expect(near(p({"model": "large"}, 0.95), 2 * 18.466666666666667), "all-large: p95 is the doubled path, 36.9 s")
    expect(near(p({"batch_share": 0.5}, 0.95), p({}, 0.95)), "batched tasks leave the interactive budget; the rest see the same latencies")
    with patched(RETRY=0.03):
        expect(near(p({}, 0.95), 28 / 3), "with RETRY = 0.03 the doubled outcomes hold only 3% of the tasks, so p95 is one pass")
    try:
        p({"batch_share": 1.0}, 0.95)
    except ValueError:
        pass
    else:
        raise AssertionError("a design that batches everything has no interactive latency: raise ValueError")
    for s in seeds(range(1, 21)):
        rng = random.Random(s)
        d = {"model": rng.choice(["small", "mid", "large"]), "small_share": rng.choice([0, 0.1, 0.3, 0.6, 0.9, 1.0])}
        qs = sorted(rng.uniform(0.01, 1.0) for _ in range(5))
        vals = [p(d, q) for q in qs]
        expect(vals == sorted(vals), f"seed {s}: a higher quantile cannot be a lower latency: {list(zip(qs, vals))}")
        expect(all(near(v, ref_pct(d, q), 1e-9) for v, q in zip(vals, qs)), f"seed {s}: percentiles of {d} differ from an independent calculation: {vals} vs {[ref_pct(d, q) for q in qs]}")
    return "p95 interactive latency: all small 8.5 s, all mid 18.7 s, all large 36.9 s (the retries set the tail)"


# =============================================================================
# Milestone 4: cost per accepted task and the choice
# =============================================================================
def m4():
    d = {"cached": 0.9}
    expect(near(mod.cost_per_accepted(d, 0.92), mod.total_cost(d) / 0.92), "cost_per_accepted = total_cost / accepted share")
    expect(near(mod.cost_per_accepted(d, 1.0), mod.total_cost(d)), "when every output is accepted, the two are equal")
    for bad in (0, -0.1, 1.2):
        try:
            mod.cost_per_accepted(d, bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted = {bad} should raise ValueError (the share must be in (0, 1])")
    C = mod.CANDIDATES
    r = mod.choose(C, 0.85, 20)
    expect(r["name"] == "B mid + cache", f"bar 85% on the interval's LOW end, p95 <= 20 s: only B should win; got {r['name']!r} (rejected: {r['rejected']})")
    want = {"C route 60% small": ["quality"], "F all large + cache": ["latency"], "G all small + cache": ["quality"]}
    expect(r["rejected"] == want, f"rejected should be {want} (C and G fail the quality gate, F the latency gate); got {r['rejected']}. "
           "D passes on a lower bound of 85.7%; A and B pass both; only the cheapest passer is chosen but passers are NOT listed as rejected")
    expect(near(r["cost"], mod.total_cost(C[1]["design"]) / (276 / 300)), f"the winner's cost is its cost per accepted task (1.258); got {r['cost']}")
    r = mod.choose(C, 0.85, 10)
    expect(r["name"] == "E D + batch half" and sorted(r["rejected"]) == ["A all mid", "B mid + cache", "C route 60% small", "F all large + cache", "G all small + cache"],
           f"with p95 <= 10 s the mid-only designs are too slow and routed designs must win; expected E (D plus batching), got {r['name']!r}, rejected {sorted(r['rejected'])}")
    expect(r["rejected"]["F all large + cache"] == ["latency"] and r["rejected"]["A all mid"] == ["latency"], "A and F fail latency only")
    r = mod.choose(C, 0.99, 20)
    expect(r["name"] is None and r["cost"] is None and len(r["rejected"]) == len(C), "if nothing clears the bar, name and cost are None and everything is listed in rejected")
    both = mod.choose([{"name": "slowbad", "design": {"model": "large"}, "k": 100, "n": 300}], 0.8, 5)
    expect(both["rejected"] == {"slowbad": ["latency", "quality"]}, f"a candidate failing both gates lists both, sorted; got {both['rejected']}")
    twin = [dict(C[1], name="Z twin"), dict(C[1], name="B mid + cache")]
    expect(mod.choose(twin, 0.85, 20)["name"] == "B mid + cache", "equal cost goes to the alphabetically first name")
    # the lesson: with a reviewer in the loop the bigger model bill is cheaper per accepted task; with none it is not
    with patched(REVIEW_SHARE=0.0):
        r2 = mod.choose(C, 0.85, 20)
        expect(r2["name"] == "E D + batch half", f"with no human review the model bill is the whole cost, and routing plus batching should win; got {r2['name']!r}")
    return ("bar 85% (interval low end), p95 <= 20 s -> B mid + cache at 1.258 USD per accepted task\n"
            "(D and E are cheaper on the model bill but lose more outputs to review)")


# =============================================================================
# Milestone 5: pay per token or host
# =============================================================================
def m5():
    fixed = mod.selfhost_fixed(2.50, 2, 1500)
    expect(near(fixed, 5150.0), f"2 GPUs at 2.50 USD an hour for 730 hours is 3,650, plus 1,500 operations = 5,150 USD a month; got {fixed}")
    expect(near(mod.selfhost_fixed(1.0, 1, 0, hours=100), 100.0), "the `hours` argument must be used")
    cap = mod.selfhost_capacity(6, 2, 0.40)
    expect(near(cap, 12_614_400.0), f"6 req/s x 2 GPUs x 730 h x 3600 s x 40% = 12,614,400 requests a month; got {cap}")
    expect(mod.monthly_selfhost(0, 5150, 1000) == 5150 and mod.monthly_selfhost(1000, 5150, 1000) == 5150, "one fleet at zero volume and at exactly its capacity")
    expect(mod.monthly_selfhost(1001, 5150, 1000) == 10300 and mod.monthly_selfhost(2500, 5150, 1000) == 15450, "fleets are bought whole: 1,001 requests need two, 2,500 need three")
    mid, front = 0.005, 0.015                  # (3,000 x 1 + 400 x 5) / 1e6 and (3,000 x 3 + 400 x 15) / 1e6
    expect(round(mod.breakeven_volume(5150, mid)) == 1_030_000, f"break-even against the mid-tier API: 5,150 / 0.005 = 1,030,000; got {mod.breakeven_volume(5150, mid)}")
    expect(round(mod.breakeven_volume(5150, front)) == 343_333, "break-even against the frontier API: 343,333 requests a month")
    api = {"mid-tier API": mid, "frontier API": front}
    for vol, want_name, want_cost in ((50_000, "mid-tier API", 250), (200_000, "mid-tier API", 1000), (1_000_000, "mid-tier API", 5000),
                                      (5_000_000, "self-hosted", 5150), (12_000_000, "self-hosted", 5150), (20_000_000, "self-hosted", 10300)):
        name, cost = mod.cheapest_option(vol, api, fixed, cap)
        expect(name == want_name and near(cost, want_cost, 1e-6), f"{vol:,} requests a month: the cost chapter's table says {want_name} at {want_cost:,} USD; got {name} at {cost:,.2f}")
    expect(mod.cheapest_option(500_000, api, fixed, cap)[0] == "mid-tier API", "at 500,000 requests the mid-tier API (2,500 USD) beats a 5,150 USD fleet")
    expect(mod.cheapest_option(500_000, {"b": 0.01, "a": 0.01}, 1e9, 1e9)[0] == "a", "ties go to the alphabetically first name")
    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        f, per = rng.uniform(1000, 9000), rng.uniform(0.001, 0.03)
        be = mod.breakeven_volume(f, per)
        cap = 10 * be
        below, above = mod.cheapest_option(be * 0.9, {"api": per}, f, cap)[0], mod.cheapest_option(be * 1.1, {"api": per}, f, cap)[0]
        expect(below == "api" and above == "self-hosted", f"seed {s}: 10% below break-even the API should win and 10% above the fleet should (fixed {f:.0f}, per request {per:.4f}); got {below}, {above}")
    return "self-hosted fixed cost 5,150 USD a month; capacity 12.6 M requests; break-even 1,030,000 (mid-tier API) and 343,333 (frontier API)"


# =============================================================================
# Milestone 6: net present value, sensitivity, chance of loss
# =============================================================================
def m6():
    expect(near(mod.npv([-100, 60, 60], 0.10), -100 + 60 / 1.1 + 60 / 1.21), f"npv([-100, 60, 60], 10%) = -100 + 54.55 + 49.59 = 4.13; got {mod.npv([-100, 60, 60], 0.10)}")
    expect(near(mod.npv([-50, 0, 0], 0.5), -50) and near(mod.npv([10, 10], 0.0), 20), "year 0 is not discounted; a zero rate is a plain sum")
    f = lambda x: mod.npv(mod.project_flows(x), mod.DISCOUNT)
    modes = {k: v[1] for k, v in mod.INPUTS.items()}
    expect(abs(f(modes) - 2_634_504.5) < 1.0, f"the project at its most likely inputs should have an NPV of about 2,634,505 USD; got {f(modes):,.0f}")
    # tornado on a toy function with a known answer
    toy_inputs = {"a": (0, 1, 2), "b": (0, 10, 20)}
    rows = mod.tornado(lambda x: 3 * x["a"] + x["b"], toy_inputs)
    expect([r[0] for r in rows] == ["b", "a"] and rows[0][1:] == (3, 23, 20) and rows[1][1:] == (10, 16, 6),
           f"toy: b swings f from 3 to 23 (20), a from 10 to 16 (6), largest first; others held at their modes. Got {rows}")
    rows = mod.tornado(lambda x: -x["a"] * 5, {"a": (0, 1, 2)})
    expect(rows[0][3] == 10, "swing is the ABSOLUTE difference (a falling function still has a positive swing)")
    rows = mod.tornado(f, mod.INPUTS)
    names = [r[0] for r in rows]
    expect(names[:3] == ["realisation", "adoption", "manual_min"] and names[-1] == "model_per_task",
           f"for the project, the three biggest swings should be realisation, adoption, manual_min and the smallest the model price; got {names}")
    expect(abs(rows[0][3] - 3_800_084) < 5, f"realisation swings the NPV by about 3.80 M; got {rows[0][3]:,.0f}")
    # chance of loss: exact draws, and the logic on trivial functions
    toy = {"a": (0.0, 1.0, 2.0)}
    for s in seeds((14, 3, 99)):
        rng = random.Random(s)
        lost = sum(rng.triangular(0.0, 2.0, 1.0) < 1.0 for _ in range(2000)) / 2000
        got = mod.chance_of_loss(lambda x: x["a"] - 1.0, toy, 2000, s)
        expect(near(got, lost), f"seed {s}: contract draws rng.triangular(low, high, mode) once per input, names sorted, one shared random.Random(seed); expected {lost}, got {got}")
    expect(mod.chance_of_loss(lambda x: 1.0, toy, 100, 1) == 0.0 and mod.chance_of_loss(lambda x: -1.0, toy, 100, 1) == 1.0, "never negative gives 0.0, always negative gives 1.0")
    two = {"a": (0.0, 1.0, 2.0), "b": (5.0, 6.0, 9.0)}
    rng = random.Random(8)
    lost = 0
    for _ in range(500):
        x = {"a": rng.triangular(0.0, 2.0, 1.0), "b": rng.triangular(5.0, 9.0, 6.0)}
        lost += x["a"] + x["b"] < 6.5
    expect(near(mod.chance_of_loss(lambda x: x["a"] + x["b"] - 6.5, two, 500, 8), lost / 500), "with two inputs the draw order matters: name order 'a' then 'b'")
    p = mod.chance_of_loss(f, mod.INPUTS, 5000, 14)
    expect(0.0 <= p <= 0.05, f"the project should lose money in only a small share of draws (about 0.5%); got {p:.3f}")
    # break-even input
    r = mod.break_even_input(lambda x: x["a"] - 3, {"a": (0, 1, 10)}, "a", 0, 10)
    expect(abs(r - 3) < 1e-5, f"the root of a - 3 is 3; got {r}")
    r = mod.break_even_input(lambda x: 7 - 2 * x["a"], {"a": (0, 1, 10)}, "a", 0, 10)
    expect(abs(r - 3.5) < 1e-5, f"a falling function works too: 7 - 2a is zero at 3.5; got {r}")
    try:
        mod.break_even_input(lambda x: x["a"] + 1, {"a": (0, 1, 10)}, "a", 0, 10)
    except ValueError:
        pass
    else:
        raise AssertionError("no sign change between lo and hi: raise ValueError")
    r = mod.break_even_input(f, mod.INPUTS, "manual_min", 1.0, 14.0)
    expect(abs(f(dict(modes, manual_min=r))) < 10, f"at the returned manual_min ({r:.4f}) the NPV should be about 0; got {f(dict(modes, manual_min=r)):,.1f}")
    return (f"NPV at the most likely inputs {f(modes) / 1e6:.2f} M USD; biggest swings: {', '.join(names[:3])}; chance of loss {p:.1%} (5,000 draws);\n"
            f"the case breaks even if the work takes {r:.2f} minutes today instead of 11")


MILESTONES = [
    (1, "Milestone 1: the price of one call (tokens, caching)", m1),
    (2, "Milestone 2: the price of a task (retries, routing, batching, the reviewer)", m2),
    (3, "Milestone 3: latency and the retry tail", m3),
    (4, "Milestone 4: cost per accepted task and the cheapest design that clears the bar", m4),
    (5, "Milestone 5: pay per token or run your own GPUs", m5),
    (6, "Milestone 6: net present value, sensitivity and chance of loss", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 2 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
