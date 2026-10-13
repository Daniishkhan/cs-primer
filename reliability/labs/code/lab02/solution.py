"""Lab 2: a small metrics library (counters, gauges, histograms, a registry, an exposition).

Pure Python, one process, no network and no threads. Time never appears: a metric is
just numbers that code updates. Every random number comes from a seeded random.Random.

The cast (chapter 4 of this course):

    Counter    only goes up; you export totals and compute rates at query time
    Gauge      goes up and down; the level right now
    Histogram  cumulative bucket counts + a sum + a count; mergeable across hosts
    Registry   owns the metrics, refuses a label that would explode the series count,
               and renders everything in the Prometheus text exposition format

What is GIVEN: name validation, the Metric base class, Snapshot, the fleet generator and
the "wrong" way to aggregate. What YOU write is marked TODO:

    1  label_key, Metric.labels, CounterChild.inc, GaugeChild.set/inc/dec,
       Registry.register, Registry.admit
    2  check_bounds, exponential_buckets, HistogramChild.observe / cumulative
    3  quantile, HistogramChild.quantile
    4  merge
    5  format_value, escape_label_value, escape_help, render

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import bisect
import math
import random
import re
from dataclasses import dataclass

NAME_RE = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
LABEL_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class CardinalityError(Exception):
    """A new label combination would push a metric past the registry's series limit."""


# =============================================================================
# Milestone 1: counters, gauges, labels, and a registry that says no
# =============================================================================
def label_key(labelnames, kv):
    """Turn the keyword labels of one call into the tuple that identifies a child.

    `labelnames` is the tuple declared on the metric, e.g. ("route", "status");
    `kv` is what the caller passed, e.g. {"status": 200, "route": "/cart"}.
    Return the label VALUES, converted to str, in the declared order:
    ("/cart", "200"). Raise ValueError if the caller passed a different SET of labels
    (a missing one, an extra one): a metric has exactly the labels it declared.
    """
    if set(kv) != set(labelnames):
        raise ValueError(f"expected labels {sorted(labelnames)}, got {sorted(kv)}")
    return tuple(str(kv[n]) for n in labelnames)


class Registry:
    """Owns the metrics. `max_series` caps the number of time series ONE metric may create."""

    def __init__(self, max_series=1000):
        self.max_series = max_series
        self.metrics = {}          # name -> metric
        self.rejected = {}         # name -> how many new label combinations were refused

    def register(self, metric):
        """Add a metric. Raise ValueError if the name is already taken (two metrics
        with one name would produce one confusing exposition)."""
        if metric.name in self.metrics:
            raise ValueError(f"metric {metric.name!r} is already registered")
        self.metrics[metric.name] = metric

    def admit(self, metric, key):
        """Called by Metric.labels BEFORE it creates a child for a label combination it has
        not seen. `key` is the label_key tuple. A child costs metric.series_per_child()
        time series. If creating it would take the metric's total above self.max_series,
        count the refusal in self.rejected[metric.name] and raise CardinalityError (the
        message should name the metric and the limit). Otherwise return None."""
        if (len(metric.children) + 1) * metric.series_per_child() > self.max_series:
            self.rejected[metric.name] = self.rejected.get(metric.name, 0) + 1
            raise CardinalityError(f"{metric.name}: a new label combination {key} would exceed the limit of "
                                   f"{self.max_series} series")

    def series_count(self):
        return sum(len(m.children) * m.series_per_child() for m in self.metrics.values())

    def collect(self):
        """The metrics, sorted by name."""
        return [self.metrics[n] for n in sorted(self.metrics)]

    def expose(self):
        return render(self)


class Metric:
    kind = "untyped"

    def __init__(self, name, help, labelnames=(), registry=None):
        if not NAME_RE.match(name):
            raise ValueError(f"invalid metric name {name!r}")
        for ln in labelnames:
            if not LABEL_RE.match(ln) or ln.startswith("__"):
                raise ValueError(f"invalid label name {ln!r}")
        if len(set(labelnames)) != len(labelnames):
            raise ValueError("duplicate label names")
        self.name, self.help, self.labelnames = name, help, tuple(labelnames)
        self.children = {}               # label key -> child
        self.registry = registry
        if registry is not None:
            registry.register(self)
        if not self.labelnames:
            self.labels()                # an unlabelled metric has its one child from the start

    def series_per_child(self):
        return 1

    def _new_child(self):
        raise NotImplementedError

    def labels(self, **kv):
        """Return the child for this label combination, creating it on first use.

        Steps: compute the key with label_key; if the child exists, return it WITHOUT
        asking the registry (revisiting a combination must never count against the limit);
        otherwise, if there is a registry, call registry.admit(self, key) (it may raise
        CardinalityError), then create the child with self._new_child(), store it in
        self.children[key] and return it."""
        key = label_key(self.labelnames, kv)
        child = self.children.get(key)
        if child is None:
            if self.registry is not None:
                self.registry.admit(self, key)
            child = self.children[key] = self._new_child()
        return child


class CounterChild:
    def __init__(self):
        self.value = 0.0

    def inc(self, amount=1):
        """Add `amount` (default 1). A counter never goes down: raise ValueError if amount < 0."""
        if amount < 0:
            raise ValueError("a counter can only increase")
        self.value += amount


class Counter(Metric):
    """By Prometheus convention (and by rule in this lab) a counter's name ends in _total."""
    kind = "counter"

    def __init__(self, name, help, labelnames=(), registry=None):
        if not name.endswith("_total"):
            raise ValueError("counter names end in _total")
        super().__init__(name, help, labelnames, registry)

    def _new_child(self):
        return CounterChild()

    def inc(self, amount=1):                   # shortcut for an unlabelled counter
        self.labels().inc(amount)


class GaugeChild:
    def __init__(self):
        self.value = 0.0

    def set(self, v):
        self.value = float(v)

    def inc(self, amount=1):
        self.value += amount

    def dec(self, amount=1):
        self.value -= amount


class Gauge(Metric):
    kind = "gauge"

    def _new_child(self):
        return GaugeChild()

    def set(self, v):
        self.labels().set(v)

    def inc(self, amount=1):
        self.labels().inc(amount)

    def dec(self, amount=1):
        self.labels().dec(amount)


# =============================================================================
# Milestone 2: a histogram with configurable buckets
# =============================================================================
def check_bounds(bounds):
    """Validate user-supplied bucket upper bounds and return them as a tuple of floats
    WITHOUT +Inf (the +Inf bucket always exists and is implicit).

    Accept a trailing float('inf') and drop it. Raise ValueError if the list is empty,
    contains NaN or a non-trailing infinity, or is not strictly increasing."""
    b = [float(x) for x in bounds]
    if b and math.isinf(b[-1]) and b[-1] > 0:
        b.pop()
    if not b:
        raise ValueError("a histogram needs at least one finite bucket bound")
    if any(math.isnan(x) or math.isinf(x) for x in b):
        raise ValueError("bucket bounds must be finite")
    if any(b[i] >= b[i + 1] for i in range(len(b) - 1)):
        raise ValueError("bucket bounds must be strictly increasing")
    return tuple(b)


def exponential_buckets(start, factor, count):
    """[start, start*factor, start*factor**2, ...] with `count` entries.
    Raise ValueError unless start > 0, factor > 1 and count >= 1."""
    if start <= 0 or factor <= 1 or count < 1:
        raise ValueError("need start > 0, factor > 1, count >= 1")
    return [start * factor ** i for i in range(count)]


class HistogramChild:
    def __init__(self, bounds):
        self.bounds = bounds                    # finite upper bounds, strictly increasing
        self.sum = 0.0
        self.count = 0
        self.counts = [0] * (len(bounds) + 1)   # per-bucket (NOT cumulative); the last is +Inf

    def observe(self, v):
        """Record one value: it falls in the first bucket whose bound is >= v (so a value
        equal to a bound belongs to that bucket: le means "less than or equal"), or in the
        +Inf bucket if it is bigger than every bound. Update sum and count too.
        Raise ValueError for NaN (it belongs in no bucket and would poison the sum)."""
        if math.isnan(v):
            raise ValueError("cannot observe NaN")
        self.counts[bisect.bisect_left(self.bounds, v)] += 1
        self.sum += v
        self.count += 1

    def cumulative(self):
        """Cumulative counts, one per bound plus one for +Inf: entry i is the number of
        observations <= bound i. The last entry equals self.count."""
        out, run = [], 0
        for c in self.counts:
            run += c
            out.append(run)
        return out

    def snapshot(self):
        return Snapshot(self.bounds, tuple(self.cumulative()), self.sum, self.count)

    def quantile(self, q):
        return quantile(q, self.bounds, self.cumulative())


class Histogram(Metric):
    kind = "histogram"

    def __init__(self, name, help, buckets, labelnames=(), registry=None):
        if "le" in labelnames:
            raise ValueError("'le' is reserved for bucket bounds")
        self.bounds = check_bounds(buckets)
        super().__init__(name, help, labelnames, registry)

    def series_per_child(self):
        return len(self.bounds) + 1 + 2          # every bucket incl. +Inf, plus _sum and _count

    def _new_child(self):
        return HistogramChild(self.bounds)

    def observe(self, v):
        self.labels().observe(v)


# =============================================================================
# Milestone 3: quantiles from buckets
# =============================================================================
def quantile(q, bounds, cumulative):
    """Estimate the q-quantile (0 <= q <= 1) from bucket counts, the way PromQL's
    histogram_quantile does.

        bounds      finite upper bounds, increasing: (0.1, 0.2, 0.5, 1.0)
        cumulative  cumulative counts, one per bound plus the +Inf bucket: (10, 60, 90, 100, 100)

    Steps: total = cumulative[-1]; rank = q * total; find the first bucket whose cumulative
    count is >= rank AND that is not empty (its count is more than the previous one);
    assume its observations are spread evenly between its lower and upper bound and
    interpolate:  lower + (upper - lower) * (rank - cum_before) / (cum_here - cum_before).
    The first bucket's lower bound is 0. If the rank falls in the +Inf bucket there is no
    upper bound to interpolate to: return the largest finite bound.
    Return float('nan') if there are no observations, -inf if q < 0, +inf if q > 1.
    """
    if q < 0:
        return float("-inf")
    if q > 1:
        return float("inf")
    total = cumulative[-1]
    if total == 0:
        return float("nan")
    rank = q * total
    prev = 0
    for i, c in enumerate(cumulative):
        if c >= rank and c > prev:
            if i == len(bounds):
                return float(bounds[-1])
            lower = bounds[i - 1] if i else 0.0
            return lower + (bounds[i] - lower) * (rank - prev) / (c - prev)
        prev = c
    return float(bounds[-1])


# =============================================================================
# Milestone 4: merging histograms from many hosts
# =============================================================================
@dataclass(frozen=True)
class Snapshot:
    bounds: tuple
    cumulative: tuple
    sum: float
    count: int

    def quantile(self, q):
        return quantile(q, self.bounds, self.cumulative)


def merge(snapshots):
    """Combine the snapshots of the same histogram from several hosts (or several time
    slices) into one Snapshot: add the cumulative counts bucket by bucket, add the sums,
    add the counts. Raise ValueError if the list is empty or the bucket bounds differ:
    two layouts cannot be added without inventing data. The inputs must not be modified."""
    snapshots = list(snapshots)
    if not snapshots:
        raise ValueError("nothing to merge")
    bounds = snapshots[0].bounds
    if any(s.bounds != bounds for s in snapshots):
        raise ValueError("cannot merge histograms with different bucket bounds")
    cum = tuple(sum(col) for col in zip(*(s.cumulative for s in snapshots)))
    return Snapshot(bounds, cum, sum(s.sum for s in snapshots), sum(s.count for s in snapshots))


def host_latencies(rng, n, median_ms, sigma, slow_frac=0.0):
    """n latencies in ms: a lognormal body plus an optional slow mode (as in chapter 4)."""
    out = []
    for _ in range(n):
        v = rng.lognormvariate(math.log(median_ms), sigma)
        if rng.random() < slow_frac:
            v += rng.uniform(400, 900)
        out.append(v)
    return out


def fleet(seed, kind="sick-small"):
    """A fleet as a list of per-host latency lists (ms).

    "sick-small": two busy healthy hosts and a small sick one (chapter 4's example;
                  for seed 42 the averaged p99 is about four times the truth).
    "sick-large": three healthy hosts and a sick host with a QUARTER of the traffic
                  (the average of p99s now UNDERSTATES the truth).
    """
    rng = random.Random(seed)
    if kind == "sick-small":
        return [host_latencies(rng, 90_000, 40, 0.35), host_latencies(rng, 90_000, 42, 0.35),
                host_latencies(rng, 2_000, 45, 0.40, slow_frac=0.08)]
    return [host_latencies(rng, 25_000, 40, 0.35), host_latencies(rng, 25_000, 42, 0.35),
            host_latencies(rng, 25_000, 41, 0.35), host_latencies(rng, 25_000, 45, 0.40, slow_frac=0.08)]


def exact_quantile(xs, q):
    """The value of the ceil(q*n)-th smallest sample: what 'the q-quantile' means for raw data."""
    s = sorted(xs)
    return s[max(0, min(len(s) - 1, math.ceil(q * len(s)) - 1))]


def average_of_quantiles(snapshots, q):
    """The WRONG way: a quantile per host, then the plain average of the quantiles."""
    return sum(s.quantile(q) for s in snapshots) / len(snapshots)


# =============================================================================
# Milestone 5: the Prometheus text exposition format
# =============================================================================
def format_value(v):
    """A sample value (or an `le` bound) as text. +Inf, -Inf and NaN are spelled exactly
    that way. A number with no fractional part prints without ".0" (5.0 -> "5", 1.0 -> "1");
    anything else prints with repr (0.25 -> "0.25")."""
    v = float(v)
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "+Inf" if v > 0 else "-Inf"
    if v.is_integer() and abs(v) < 1e15:
        return str(int(v))
    return repr(v)


def escape_label_value(s):
    """Label values are written inside double quotes: escape backslash, double quote and
    newline as \\\\, \\" and \\n (in that order: backslash first)."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def escape_help(s):
    """HELP text is not quoted: escape only backslash and newline."""
    return s.replace("\\", "\\\\").replace("\n", "\\n")


def render(registry):
    """The whole registry in the Prometheus text exposition format (version 0.0.4).

    For each metric, in name order:
        # HELP <name> <help>
        # TYPE <name> <counter|gauge|histogram>
    then one line per sample, children sorted by their label values:
        counter / gauge:   name{l1="v1",l2="v2"} value        (no braces if there are no labels)
        histogram:         name_bucket{...,le="0.1"} cumulative   one per bound, in order,
                           then name_bucket{...,le="+Inf"}, then name_sum{...}, then name_count{...}
    `le` goes last among the labels. The text ends with a newline."""
    def labelstr(names, values, extra=()):
        pairs = list(zip(names, values)) + list(extra)
        return "{" + ",".join(f'{n}="{escape_label_value(v)}"' for n, v in pairs) + "}" if pairs else ""

    lines = []
    for m in registry.collect():
        lines.append(f"# HELP {m.name} {escape_help(m.help)}")
        lines.append(f"# TYPE {m.name} {m.kind}")
        for key in sorted(m.children):
            child = m.children[key]
            if m.kind == "histogram":
                cum = child.cumulative()
                for b, c in zip(list(m.bounds) + [float("inf")], cum):
                    lines.append(f"{m.name}_bucket{labelstr(m.labelnames, key, [('le', format_value(b))])} {format_value(c)}")
                lines.append(f"{m.name}_sum{labelstr(m.labelnames, key)} {format_value(child.sum)}")
                lines.append(f"{m.name}_count{labelstr(m.labelnames, key)} {format_value(child.count)}")
            else:
                lines.append(f"{m.name}{labelstr(m.labelnames, key)} {format_value(child.value)}")
    return "\n".join(lines) + "\n" if lines else ""
