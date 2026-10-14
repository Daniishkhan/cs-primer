"""Lab 2: a cost and latency model for a document pipeline.

The brief: a claims-letter assistant (the pipeline of the cost chapter) makes two model
calls per letter, an EXTRACT call over the letter and a DRAFT call for the reply. You
must price it under several designs (a model tier, prompt caching, routing easy letters
to a small model, batching the letters that can wait), check each against a quality
bar and a latency target, pick the cheapest one that clears both, decide between paying
per token and running your own GPUs, and finally ask which uncertain assumption
decides whether the whole project pays back.

Every price, speed, token count and quality figure below is an ILLUSTRATIVE ASSUMPTION
chosen to be plausible in shape, not any vendor's price list. The method is the point.

What is GIVEN: the constants, the candidate designs with their measured quality, and the
project cash-flow model. What YOU write is marked TODO:

    1  call_cost
    2  task_cost, review_cost, total_cost
    3  call_latency, path_latency, latency_percentile
    4  cost_per_accepted, choose
    5  selfhost_fixed, selfhost_capacity, monthly_selfhost, breakeven_volume, cheapest_option
    6  npv, tornado, chance_of_loss, break_even_input

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import math
import random

# =============================================================================
# GIVEN: constants (all ILLUSTRATIVE)
# =============================================================================
# USD per million tokens: (input, output)
PRICE = {"small": (0.15, 0.60), "mid": (3.00, 15.00), "large": (15.00, 75.00)}
# Prompt caching and batch multipliers (see the cost chapter's dated note; check the current price list).
CACHE_READ, CACHE_WRITE, BATCH = 0.10, 1.25, 0.50
# (name, static prefix tokens, variable input tokens, output tokens)
CALLS = [("extract", 1500, 6000, 300), ("draft", 800, 1500, 450)]
RETRY = 0.06                                   # share of tasks where every call is repeated after a format failure
REVIEW_SHARE, REVIEW_MIN, RATE = 0.35, 4.0, 48.0   # 35% of outputs reviewed for 4 minutes at a loaded 48 USD/hour
# (time to first token in seconds, output tokens per second) for each tier
SPEED = {"small": (0.25, 200.0), "mid": (0.50, 90.0), "large": (0.90, 45.0)}

# Candidate designs. `model` is the main model, `small_share` of tasks are routed to "small",
# `cached` is the share of the static prefix served from the cache, `batch_share` of tasks wait for the
# batch API (they leave the interactive latency budget). `k` of `n` gold cases were judged correct
# (measured on the same sealed gold set for every design).
CANDIDATES = [
    {"name": "A all mid",                "design": {"model": "mid"},                                                "k": 276, "n": 300},
    {"name": "B mid + cache",            "design": {"model": "mid", "cached": 0.9},                                "k": 276, "n": 300},
    {"name": "C route 60% small",        "design": {"model": "mid", "cached": 0.9, "small_share": 0.6},            "k": 259, "n": 300},
    {"name": "D route 30% small",        "design": {"model": "mid", "cached": 0.9, "small_share": 0.3},            "k": 269, "n": 300},
    {"name": "E D + batch half",         "design": {"model": "mid", "cached": 0.9, "small_share": 0.3, "batch_share": 0.5}, "k": 269, "n": 300},
    {"name": "F all large + cache",      "design": {"model": "large", "cached": 0.9},                              "k": 289, "n": 300},
    {"name": "G all small + cache",      "design": {"model": "small", "cached": 0.9},                              "k": 228, "n": 300},
]

# The project cash-flow model for milestone 6: ranges (low, most likely, high) for each uncertain input.
INPUTS = {
    "volume":       (280_000, 400_000, 480_000),     # tasks per year at full adoption
    "manual_min":   (8.0, 11.0, 14.0),               # minutes per task today
    "review_share": (0.20, 0.35, 0.50),
    "review_min":   (2.0, 4.0, 6.0),
    "rate":         (40.0, 48.0, 60.0),              # loaded USD per hour
    "realisation":  (0.30, 0.60, 0.90),              # share of freed time that turns into something countable
    "adoption":     (0.40, 0.80, 0.95),
    "model_per_task": (0.006, 0.012, 0.024),         # USD
    "fixed_run":    (140_000, 171_000, 230_000),     # hosting, support, tooling, model migration, per year
    "one_off":      (640_000, 715_000, 1_100_000),   # build, integration, security review, training
}
DISCOUNT, YEARS = 0.08, 3


def project_flows(x):
    """GIVEN. Cash flows [year 0, year 1, ..., year 3] in USD for one set of input values `x`
    (a dict with the keys of INPUTS): the one-off cost, then each year's counted saving minus the
    model bill and the fixed running cost."""
    freed_min = x["manual_min"] - x["review_share"] * x["review_min"]
    tasks = x["volume"] * x["adoption"]
    saving = tasks * freed_min / 60 * x["rate"] * x["realisation"]
    yearly = saving - tasks * x["model_per_task"] - x["fixed_run"]
    return [-x["one_off"]] + [yearly] * YEARS


# =============================================================================
# Milestone 1: the price of one call
# =============================================================================
def call_cost(model, prefix, var, out, cached_share=0.0):
    """USD for one call to `model` (a key of PRICE) with `prefix` static input tokens, `var` variable
    input tokens and `out` output tokens. Prices are per million tokens.

    cached_share == 0: no caching, input = (prefix + var) * input price.
    cached_share > 0 : the static prefix is billed at CACHE_READ x price for the cached share and
                       CACHE_WRITE x price for the rest; the variable tokens are billed in full.
    Output tokens are billed at the output price either way.
    call_cost("mid", 1500, 6000, 300) -> 0.0270   (7,500 x 3 + 300 x 15, per million)"""
    pin, pout = PRICE[model]
    if cached_share > 0:
        inp = prefix * (cached_share * CACHE_READ + (1 - cached_share) * CACHE_WRITE) * pin + var * pin
    else:
        inp = (prefix + var) * pin
    return (inp + out * pout) / 1e6


# =============================================================================
# Milestone 2: the price of a task, with retries, routing and batching
# =============================================================================
def task_cost(design):
    """Model cost in USD of one task under `design`, a dict with optional keys
    model='mid', small_share=0.0, cached=0.0, batch_share=0.0.

    Sum over CALLS of: (1 - small_share) x the cost on `model` + small_share x the cost on 'small'
    (both with the `cached` share); multiply by (1 + RETRY) for repeated calls; then batching
    takes (1 - BATCH) off the cost of the batch_share of tasks:  x (1 - batch_share x (1 - BATCH))."""
    model = design.get("model", "mid")
    s = design.get("small_share", 0.0)
    cached = design.get("cached", 0.0)
    total = 0.0
    for _name, prefix, var, out in CALLS:
        big = call_cost(model, prefix, var, out, cached)
        small = call_cost("small", prefix, var, out, cached)
        total += (1 - s) * big + s * small
    total *= 1 + RETRY
    return total * (1 - design.get("batch_share", 0.0) * (1 - BATCH))


def review_cost():
    """USD of human review per task: REVIEW_SHARE x REVIEW_MIN minutes at RATE USD an hour."""
    return REVIEW_SHARE * REVIEW_MIN / 60 * RATE


def total_cost(design):
    """USD per task including the reviewer: task_cost(design) + review_cost()."""
    return task_cost(design) + review_cost()


# =============================================================================
# Milestone 3: latency, and why retries decide the tail
# =============================================================================
def call_latency(model, out):
    """Seconds for one call: time to first token plus out / tokens-per-second (SPEED[model])."""
    ttft, tps = SPEED[model]
    return ttft + out / tps


def path_latency(model):
    """Seconds for one task that goes through `model`: the calls run one after another, so add the
    call latencies of all CALLS."""
    return sum(call_latency(model, out) for _name, _p, _v, out in CALLS)


def latency_percentile(design, q):
    """The q-quantile (0 < q <= 1) of INTERACTIVE task latency under `design`, in seconds.

    A task goes through 'small' with probability small_share, else through design['model'] (default
    'mid'). With probability RETRY it runs twice (latency doubles). Build the weighted outcomes
    (latency, probability), sort by latency, and return the first latency whose cumulative probability
    reaches q (weighted nearest-rank; allow 1e-9 for float error). Batched tasks are not interactive and
    are ignored: batch_share >= 1 raises ValueError."""
    if design.get("batch_share", 0.0) >= 1:
        raise ValueError("a fully batched design has no interactive latency")
    s = design.get("small_share", 0.0)
    big = path_latency(design.get("model", "mid"))
    small = path_latency("small")
    outcomes = []
    for lat, w in ((small, s), (big, 1 - s)):
        outcomes.append((lat, w * (1 - RETRY)))
        outcomes.append((2 * lat, w * RETRY))
    outcomes.sort()
    cum = 0.0
    for lat, w in outcomes:
        cum += w
        if cum >= q - 1e-9:
            return lat
    return outcomes[-1][0]


# =============================================================================
# GIVEN: Wilson interval (as in Lab 1)
# =============================================================================
def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


# =============================================================================
# Milestone 4: the cheapest design that clears the bar
# =============================================================================
def cost_per_accepted(design, accepted):
    """USD per ACCEPTED task: total_cost(design) / accepted, where `accepted` is the share (0 < a <= 1)
    of outputs that end in an accepted result. A task that fails still cost money."""
    if not 0 < accepted <= 1:
        raise ValueError("accepted must be in (0, 1]")
    return total_cost(design) / accepted


def choose(candidates, bar, p95_limit):
    """Pick the winner among candidates (dicts with name, design, k, n).

    A candidate passes QUALITY if the LOW end of the 95% Wilson interval of k/n is >= bar, and passes
    LATENCY if latency_percentile(design, 0.95) <= p95_limit seconds. Among those passing both, the winner has
    the lowest cost_per_accepted(design, k / n); ties go to the alphabetically first name.

    Returns {'name', 'cost', 'rejected'}: the winner's name and cost per accepted task, and
    `rejected`, a dict name -> sorted list of the gates failed (['latency'], ['quality'] or both).
    If nothing passes, name and cost are None."""
    rejected, best = {}, None
    for c in candidates:
        failed = []
        if wilson(c["k"], c["n"])[0] < bar:
            failed.append("quality")
        if latency_percentile(c["design"], 0.95) > p95_limit:
            failed.append("latency")
        if failed:
            rejected[c["name"]] = sorted(failed)
            continue
        cost = cost_per_accepted(c["design"], c["k"] / c["n"])
        if best is None or (cost, c["name"]) < (best[1], best[0]):
            best = (c["name"], cost)
    return {"name": best[0] if best else None, "cost": best[1] if best else None, "rejected": rejected}


# =============================================================================
# Milestone 5: pay per token, or run your own GPUs?
# =============================================================================
HOURS = 730                       # hours in a month


def selfhost_fixed(gpu_hour, gpus, ops_month, hours=HOURS):
    """USD a month for one self-hosted fleet: GPUs for every hour of the month, plus the operations share."""
    return gpu_hour * gpus * hours + ops_month


def selfhost_capacity(req_per_s_per_gpu, gpus, utilisation, hours=HOURS):
    """Requests one fleet can serve in a month: rate x GPUs x seconds in the month x average utilisation."""
    return req_per_s_per_gpu * gpus * hours * 3600 * utilisation


def monthly_selfhost(volume, fixed, capacity):
    """USD a month to serve `volume` requests: fleets are bought whole, so ceil(volume / capacity) fleets
    (at least one, even at zero volume) times `fixed`."""
    return max(1, math.ceil(volume / capacity)) * fixed


def breakeven_volume(fixed, api_per_request):
    """Requests a month at which paying per request costs as much as one fleet: fixed / api_per_request."""
    return fixed / api_per_request


def cheapest_option(volume, api, fixed, capacity):
    """The cheapest way to serve `volume` requests a month. `api` maps an API's name to its USD per request;
    self-hosting is the option named 'self-hosted' costing monthly_selfhost(volume, fixed, capacity).
    Returns (name, monthly USD); ties go to the alphabetically first name."""
    options = {name: volume * per for name, per in api.items()}
    options["self-hosted"] = monthly_selfhost(volume, fixed, capacity)
    name = min(sorted(options), key=lambda n: options[n])
    return name, options[name]


# =============================================================================
# Milestone 6: which assumption decides the case?
# =============================================================================
def npv(flows, rate):
    """Net present value: flows[t] discounted by (1 + rate) ** t, so year 0 is not discounted."""
    return sum(f / (1 + rate) ** t for t, f in enumerate(flows))


def tornado(f, inputs):
    """One-at-a-time sensitivity. `f` maps a dict of input values to a number; `inputs` maps name ->
    (low, mode, high). With every other input at its mode, evaluate f at each input's low and high.

    Returns a list of (name, f_at_low, f_at_high, swing) with swing = abs(f_at_high - f_at_low),
    sorted by swing, largest first (ties by name)."""
    base = {k: v[1] for k, v in inputs.items()}
    rows = []
    for name, (lo, _mode, hi) in inputs.items():
        a = f(dict(base, **{name: lo}))
        b = f(dict(base, **{name: hi}))
        rows.append((name, a, b, abs(b - a)))
    return sorted(rows, key=lambda r: (-r[3], r[0]))


def chance_of_loss(f, inputs, n, seed):
    """Share of n random draws for which f(x) < 0. Each draw takes every input from a triangular
    distribution: x[name] = rng.triangular(low, high, mode), one shared random.Random(seed), names in sorted order."""
    rng = random.Random(seed)
    losses = 0
    for _ in range(n):
        x = {name: rng.triangular(inputs[name][0], inputs[name][2], inputs[name][1]) for name in sorted(inputs)}
        if f(x) < 0:
            losses += 1
    return losses / n


def break_even_input(f, inputs, name, lo, hi, tol=1e-6):
    """The value of input `name` (others at their modes) where f crosses zero, found by bisection between
    lo and hi. f(lo) and f(hi) must have opposite signs (otherwise raise ValueError). Stop when hi - lo < tol
    and return the midpoint."""
    base = {k: v[1] for k, v in inputs.items()}
    g = lambda v: f(dict(base, **{name: v}))
    glo, ghi = g(lo), g(hi)
    if glo * ghi > 0:
        raise ValueError("f does not change sign between lo and hi")
    while hi - lo >= tol:
        mid = (lo + hi) / 2
        gm = g(mid)
        if (gm < 0) == (glo < 0):
            lo, glo = mid, gm
        else:
            hi, ghi = mid, gm
    return (lo + hi) / 2
