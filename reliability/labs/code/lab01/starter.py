"""Lab 1: SLOs and burn-rate alerts, computed from a synthetic request log.

One process, no network, no clock. Time is a minute counter; every random number
comes from a seeded random.Random, so the same seed always gives the same log, the
same incident and the same answer.

The vocabulary is chapter 2 and chapter 7 of this course:

    SLI          good events / valid events
    SLO          a target for the SLI over a window (99.9% over 30 days)
    error budget 1 - SLO
    burn rate    (observed bad fraction) / (1 - SLO)

What is GIVEN: the log generator, the Series container, the three Workbook rules and
the synthetic incidents. What YOU write is marked TODO:

    1  parse_line, is_valid, is_good_availability, is_good_latency, compute_slis
    2  error_budget, budget_minutes, exhaustion_hours, budget_remaining
    3  Prefix: windowed counts, error ratio and burn rate in O(1)
    4  firing_intervals, detection_time, reset_time, evaluate
    5  verdict, confusion, precision_recall, score_policy

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import math
import random
from dataclasses import dataclass

SLO = 0.999
DAY = 24 * 60                    # minutes
WINDOW = 30 * DAY                # the SLO window, in minutes
LATENCY_MS = 300                 # the latency SLI's threshold
RPM = 1000                       # requests per minute in the synthetic series (constant, for clarity)


# =============================================================================
# GIVEN: requests and the synthetic log
# =============================================================================
@dataclass(frozen=True)
class Request:
    ts: int            # seconds since the start of the log
    method: str
    path: str
    status: int
    latency_ms: int
    client: str        # "web", "app", "partner", "loadtest", "probe"


def format_line(r: Request) -> str:
    return f"{r.ts} {r.method} {r.path} {r.status} {r.latency_ms} {r.client}"


def generate_log(seed, minutes=120, rps=4.0, outage=(60, 63)):
    """A load-balancer access log as a list of text lines, `rps` requests per second.

    It contains everything a real log contains: ordinary traffic, health checks, a
    load-test client, 4xx responses, 429s from load shedding, slow responses, 5xx
    errors, a few garbled lines, and a short outage (minutes `outage`) in which
    half the requests fail.
    """
    rng = random.Random(seed)
    lines = []
    paths = ["/api/cart", "/api/search", "/api/checkout", "/api/orders", "/api/health"]
    for sec in range(minutes * 60):
        for _ in range(int(rps) + (1 if rng.random() < rps - int(rps) else 0)):
            minute = sec // 60
            path = rng.choices(paths, weights=[30, 40, 10, 15, 5])[0]
            client = rng.choices(["web", "app", "partner", "loadtest", "probe"], weights=[50, 35, 8, 5, 2])[0]
            if path == "/api/health":
                client = "probe"
            if rng.random() < 0.004:                       # garbled line
                lines.append(rng.choice(["", "-", f"{sec} GET /api/cart 200", f"{sec} GET /api/cart OK 80 web",
                                         f"{sec} GET /api/cart 200 -5 web"]))
                continue
            status = rng.choices([200, 201, 404, 400, 429, 500, 503], weights=[9900, 500, 200, 100, 3, 2, 1])[0]
            if outage[0] <= minute < outage[1] and rng.random() < 0.5:
                status = rng.choice([500, 502, 503])
            lat = int(rng.lognormvariate(math.log(80), 0.6))
            if rng.random() < 0.01:
                lat += rng.randint(300, 1500)               # slow tail
            lines.append(format_line(Request(sec, rng.choice(["GET", "GET", "POST"]), path, status, lat, client)))
    return lines


@dataclass
class SLIReport:
    valid: int = 0
    good_availability: int = 0
    good_latency: int = 0
    skipped: int = 0           # lines that could not be parsed

    @property
    def availability(self):
        return self.good_availability / self.valid if self.valid else 1.0

    @property
    def latency(self):
        return self.good_latency / self.valid if self.valid else 1.0


# =============================================================================
# Milestone 1: parse a log, define valid and good
# =============================================================================
def parse_line(line):
    """Parse "ts method path status latency_ms client" into a Request, or return None.

    Return None (never raise) for anything malformed: blank lines, the wrong number
    of fields, a field that is not an integer where one is needed, a status outside
    100..599, a negative latency or a negative timestamp.
    """
    raise NotImplementedError("TODO milestone 1: parse_line")


def is_valid(r):
    """Does this request count in the denominator?

    Valid: a request for /api/* ... EXCEPT health checks (/api/health) and the
    load-test client (client == "loadtest"). Everything else, including 4xx and 5xx
    responses, is valid: a failure must stay in the denominator to count against you.
    """
    raise NotImplementedError("TODO milestone 1: is_valid")


def is_good_availability(r):
    """Is this (valid) request good for the availability SLI?

    5xx is bad. 429 is bad too: the service refused a valid request to protect
    itself, and the user got nothing. Any other 4xx is good (the client erred and the
    service correctly said so).
    """
    raise NotImplementedError("TODO milestone 1: is_good_availability")


def is_good_latency(r, threshold_ms=LATENCY_MS):
    """Is this (valid) request good for the latency SLI?

    Good means: good for availability AND latency_ms <= threshold_ms. A fast error is
    not a fast success. The boundary is inclusive: exactly 300 ms is good, 301 is not.
    """
    raise NotImplementedError("TODO milestone 1: is_good_latency")


def compute_slis(lines, threshold_ms=LATENCY_MS):
    """Fold a log into an SLIReport: valid, good_availability, good_latency, skipped.

    Unparseable lines count in `skipped` only; they are not valid and not good.
    Requests that parse but are not valid are simply ignored.
    """
    raise NotImplementedError("TODO milestone 1: compute_slis")


# =============================================================================
# GIVEN: per-minute series
# =============================================================================
class Series:
    """Per-minute counts: valid[i] requests were valid in minute i, bad[i] of them were bad."""

    def __init__(self, valid, bad):
        assert len(valid) == len(bad)
        self.valid, self.bad = valid, bad

    def __len__(self):
        return len(self.valid)


def constant_series(minutes, rpm=RPM, errors=None):
    """A series with `rpm` valid requests every minute; `errors` is {minute: bad count}."""
    bad = [0] * minutes
    for m, n in (errors or {}).items():
        bad[m] = n
    return Series([rpm] * minutes, bad)


# =============================================================================
# Milestone 2: the error budget over a rolling 30-day window
# =============================================================================
def error_budget(slo):
    """The fraction of valid events allowed to be bad: 1 - slo."""
    raise NotImplementedError("TODO milestone 2: error_budget")


def budget_minutes(slo, window=WINDOW):
    """The same budget as minutes of COMPLETE unavailability in `window` minutes."""
    raise NotImplementedError("TODO milestone 2: budget_minutes")


def exhaustion_hours(burn, window=WINDOW):
    """Hours until a full budget is gone at a constant burn rate (window is in minutes)."""
    raise NotImplementedError("TODO milestone 2: exhaustion_hours")


def budget_remaining(valid, bad, end, slo, window=WINDOW):
    """Fraction of the error budget still unspent in the window of `window` minutes
    ending at minute `end` (inclusive): the minutes end-window+1 .. end, clipped at 0.

        allowed = (1 - slo) * valid requests in the window
        remaining = 1 - bad requests in the window / allowed

    1.0 means untouched, 0.0 means exactly spent, negative means overspent. If the
    window holds no valid requests there is nothing to overspend: return 1.0.
    Straightforward is fine here: add up the slice.
    """
    raise NotImplementedError("TODO milestone 2: budget_remaining")


# =============================================================================
# Milestone 3: windows in O(1) with prefix sums
# =============================================================================
class Prefix:
    """Prefix sums over a Series, so any trailing window is two subtractions.

    After __init__ no method may loop over minutes or slice the original lists.
    """

    def __init__(self, series):
        """Build the prefix arrays. Keep them in `self.cv` and `self.cb`, each of
        length len(series) + 1, with cv[i] = valid requests in minutes 0 .. i-1."""
        raise NotImplementedError("TODO milestone 3: Prefix.__init__")

    def window(self, end, w):
        """(valid, bad) over the w minutes ending at minute `end` inclusive, clipped at minute 0."""
        raise NotImplementedError("TODO milestone 3: Prefix.window")

    def error_ratio(self, end, w):
        """bad / valid over the window; 0.0 if the window holds no valid requests."""
        raise NotImplementedError("TODO milestone 3: Prefix.error_ratio")

    def burn_rate(self, end, w, slo):
        """error_ratio / (1 - slo)."""
        raise NotImplementedError("TODO milestone 3: Prefix.burn_rate")

    def remaining(self, end, slo, window=WINDOW):
        """Same answer as budget_remaining, in O(1)."""
        raise NotImplementedError("TODO milestone 3: Prefix.remaining")


# =============================================================================
# Milestone 4: multi-window, multi-burn-rate alert rules
# =============================================================================
@dataclass(frozen=True)
class Rule:
    name: str
    severity: str      # "page" or "ticket"
    long_m: int        # long window, minutes
    short_m: int       # short window, minutes
    burn: float        # fire when the burn rate in the window is ABOVE this


# The Site Reliability Workbook's starting parameters for a 99.9% SLO (chapter 7).
RULES = [
    Rule("2% in 1h", "page", 60, 5, 14.4),
    Rule("5% in 6h", "page", 6 * 60, 30, 6.0),
    Rule("10% in 3d", "ticket", 3 * DAY, 6 * 60, 1.0),
]


def rule_fires(p, t, rule, slo=SLO, use_short=True):
    """Is `rule` firing at minute t? The burn rate over the long window must be above
    rule.burn and, when use_short is True, the burn rate over the short window must be
    above it too. Strictly above: a burn rate exactly equal to rule.burn does not fire."""
    raise NotImplementedError("TODO milestone 4: rule_fires")


def firing_intervals(p, rule, slo=SLO, use_short=True):
    """Every maximal run of consecutive minutes at which the rule fires, as a list of
    (first_minute, last_minute) pairs, both inclusive, in time order."""
    raise NotImplementedError("TODO milestone 4: firing_intervals")


def detection_time(intervals, incident_start):
    """Minutes from incident_start until the alert first fires at or after it
    (0 means it fired in the incident's first minute). None if it never does.
    An interval that began earlier but is still firing at incident_start counts as 0."""
    raise NotImplementedError("TODO milestone 4: detection_time")


def reset_time(intervals, incident_end):
    """Minutes the alert keeps firing after the incident is over. The incident covers
    minutes [start, incident_end), so incident_end is its first healthy minute. If the
    alert is firing at incident_end, count the minutes from incident_end to the last
    firing minute of that run, inclusive; otherwise 0."""
    raise NotImplementedError("TODO milestone 4: reset_time")


def evaluate(series, rules=RULES, slo=SLO, use_short=True):
    """{rule.name: firing_intervals} for every rule."""
    raise NotImplementedError("TODO milestone 4: evaluate")


# =============================================================================
# GIVEN: the chapter-7 incidents, and a seeded set of scenarios
# =============================================================================
LEAD = 3 * DAY                 # healthy days first, so every window is full
T0 = LEAD + 600                # incidents begin at 10:00 on day 4


def chapter_scenarios():
    """The four incidents of chapter 7, with no noise. Returns {name: (series, start, end)}."""
    def make(minutes, segs):
        errs = {}
        for a, b, ratio in segs:
            for t in range(a, b):
                errs[t] = int(RPM * ratio)
        return constant_series(minutes, errors=errs)
    n = LEAD + 4 * DAY
    return {
        "A outage": (make(n, [(T0, T0 + 30, 1.0)]), T0, T0 + 30),
        "B blip": (make(n, [(T0, T0 + 3, 0.20)]), T0, T0 + 3),
        "C bad deploy": (make(n, [(T0, T0 + 480, 0.01)]), T0, T0 + 480),
        "D slow leak": (make(n, [(T0, T0 + 3 * DAY, 0.002)]), T0, T0 + 3 * DAY),
    }


@dataclass
class Scenario:
    family: str
    label: str           # "page" (wake someone), "ticket" (look within days) or "none"
    series: Series
    start: int           # first incident minute
    end: int             # first healthy minute after the last incident minute


def _noisy(rng, minutes, base=0.0002):
    mu = RPM * base
    return [max(0, round(rng.gauss(mu, math.sqrt(mu)))) for _ in range(minutes)]


def make_scenario(rng, family):
    """One seeded scenario. Labels are set by design and cross-checked against the budget
    arithmetic: "page" scenarios spend at least 8% of the monthly budget at a burn rate of
    at least 7; "ticket" scenarios burn at 1.5 to 4 times the allowed rate and spend at
    least 12%; "none" scenarios spend under 3% (brief spikes, or a burn rate below 1)."""
    budget_req = (1 - SLO) * RPM * WINDOW
    bad = _noisy(rng, LEAD + 7 * DAY)
    start = LEAD + rng.randint(0, 600)

    def add(a, b, ratio):
        for t in range(a, b):
            bad[t] += round(RPM * ratio)

    if family == "outage":                      # fast and severe
        dur = rng.randint(10, 60)
        add(start, start + dur, 1.0)
        end, label = start + dur, "page"
    elif family == "partial":                   # severe but partial
        ratio = rng.uniform(0.05, 0.5)
        dur = math.ceil(0.08 * budget_req / (RPM * ratio)) + rng.randint(5, 30)
        add(start, start + dur, ratio)
        end, label = start + dur, "page"
    elif family == "bad_deploy":                # moderate and steady: burn 7 to 30
        ratio = rng.choice([rng.uniform(0.007, 0.0095), rng.uniform(0.0105, 0.03)])
        dur = math.ceil(0.08 * budget_req / (RPM * ratio)) + rng.randint(10, 120)
        add(start, start + dur, ratio)
        end, label = start + dur, "page"
    elif family == "slow_leak":                 # slow and steady: burn 1.5 to 4
        ratio = rng.uniform(0.0015, 0.004)
        dur = math.ceil(0.12 * budget_req / (RPM * ratio)) + rng.randint(60, 600)
        add(start, start + dur, ratio)
        end, label = start + dur, "ticket"
    elif family == "blip":                      # one brief spike
        ratio, dur = rng.uniform(0.1, 1.0), rng.randint(1, 4)
        while RPM * ratio * dur > 400:
            ratio, dur = rng.uniform(0.1, 1.0), rng.randint(1, 4)
        add(start, start + dur, ratio)
        end, label = start + dur, "none"
    elif family == "spike_train":               # 2-3 brief spikes, at least 2 hours apart
        t, end = start, start
        for _ in range(rng.randint(2, 3)):
            ratio, dur = rng.uniform(0.1, 1.0), rng.randint(1, 4)
            while RPM * ratio * dur > 400:
                ratio, dur = rng.uniform(0.1, 1.0), rng.randint(1, 4)
            add(t, t + dur, ratio)
            end = t + dur
            t += rng.randint(120, 300)
        label = "none"
    elif family == "mild":                      # a persistent 0.03-0.05% error rate on top of the noise: burn under 1
        ratio = rng.uniform(0.0003, 0.0005)
        dur = rng.randint(DAY, 3 * DAY)
        add(start, start + dur, ratio)
        end, label = start + dur, "none"
    elif family == "quiet":                     # nothing but background noise
        end, label = start, "none"
    else:
        raise ValueError(family)
    spent = sum(bad[start:end]) / budget_req
    if label == "page":
        assert spent >= 0.08, (family, spent)
    elif label == "ticket":
        assert spent >= 0.12, (family, spent)
    else:
        assert spent < 0.03 or family == "mild", (family, spent)
    return Scenario(family, label, Series([RPM] * len(bad), bad), start, end)


FAMILIES = ["outage", "partial", "bad_deploy", "slow_leak", "blip", "spike_train", "mild", "quiet"]


def make_scenarios(seed, n=48):
    """n scenarios, drawn evenly from the families (n should be a multiple of 8)."""
    rng = random.Random(seed)
    return [make_scenario(rng, FAMILIES[i % len(FAMILIES)]) for i in range(n)]


# =============================================================================
# Milestone 5: a naive threshold against the burn-rate rules
# =============================================================================
# The naive alert: page whenever the error ratio over the last 5 minutes is above 1%
# (a burn rate of 10). One window, one threshold, and no short window to confirm it.
NAIVE = [Rule("naive 1% over 5m", "page", 5, 5, 10.0)]
# Two single-window alternatives from the Workbook's progression: fast but blind to moderate burns,
# and precise but slow to detect and slow to reset.
ONE_HOUR = [Rule("10x over 1h", "page", 60, 60, 10.0)]
SIX_HOURS = [Rule("5x over 6h", "page", 360, 360, 5.0)]


def merge_intervals(intervals):
    """Union of (first, last) inclusive minute intervals, sorted, touching ones joined."""
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def median(xs):
    xs = sorted(xs)
    return None if not xs else xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2


def verdict(by_rule, rules):
    """What would this policy have done with a scenario? `by_rule` is evaluate()'s result.

    "page" if any rule whose severity is "page" fired at least once;
    otherwise "ticket" if any "ticket" rule fired; otherwise "none"."""
    raise NotImplementedError("TODO milestone 5: verdict")


def confusion(labels, verdicts, positive):
    """Counts (tp, fp, fn, tn) treating `positive` as the class we want to catch."""
    raise NotImplementedError("TODO milestone 5: confusion")


def precision_recall(tp, fp, fn):
    """(precision, recall). Precision is 1.0 when nothing fired; recall is 1.0 when
    there was nothing to catch."""
    raise NotImplementedError("TODO milestone 5: precision_recall")


def score_policy(scenarios, rules, use_short=True, positive="page"):
    """Run a policy on every scenario and report the four attributes of chapter 7.

    Returns a dict with keys
        precision, recall, tp, fp, fn, tn     for catching the `positive` class
        verdicts                              the policy's verdict for each scenario, in order
        detect, reset                         {family: [minutes, ...]} over the scenarios that
                                              were labelled `positive` AND caught
        detect_median, reset_median           the same, pooled over all families (None if empty)

    The policy's "alert" for a scenario is ON in every minute at which any rule of severity
    `positive` fires (use merge_intervals on the union). Detection time is measured from
    scenario.start, reset time from scenario.end."""
    raise NotImplementedError("TODO milestone 5: score_policy")
