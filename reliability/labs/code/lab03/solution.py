"""Lab 3: tracing from scratch, on simulated services and simulated time.

One process. No sockets, no threads, no real clock: time is a number of milliseconds that
a SimClock advances, and every random number comes from a seeded random.Random. A
"service call" is a Python function call that carries a dict of headers, so the
propagation code you write is exactly what a real tracer does at a process boundary.

The cast (chapter 6 of this course):

    Span          one named, timed unit of work, with a trace id, a span id and a parent id
    SpanContext   what travels between processes: trace id, parent span id, sampled flag
    traceparent   the W3C header that carries a SpanContext: 00-<trace>-<span>-<flags>
    link          a reference from a span to another span's context that is NOT its parent
    collector     where finished spans go, in any order, after any delay

What is GIVEN: the data classes, the clock, the id generator, the World that runs simulated
services, the queue, the delivery simulator, the workload generator, the tail sampler's
buffering, and the text renderers. What YOU write is marked TODO:

    1  IdGenerator.trace_id / span_id, Tracer.start_span / finish / span
    2  format_traceparent, parse_traceparent, inject, extract
    3  publish, consume_as_child, consume_linked, consume_batch
    4  assemble
    5  critical_path, head_keep, tail_decision, baseline_rate

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import heapq
import math
import random
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Optional


# =============================================================================
# GIVEN: data, clock
# =============================================================================
@dataclass(frozen=True)
class SpanContext:
    trace_id: str
    span_id: str
    sampled: bool = True


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    service: str
    name: str
    start: float
    end: Optional[float] = None
    kind: str = "internal"          # internal, server, client, producer, consumer
    status: str = "ok"              # "ok" or "error"
    sampled: bool = True
    attrs: dict = field(default_factory=dict)
    links: list = field(default_factory=list)    # SpanContexts of spans this one is related to

    def context(self):
        return SpanContext(self.trace_id, self.span_id, self.sampled)

    @property
    def duration(self):
        return None if self.end is None else self.end - self.start


class SimClock:
    """Simulated time in milliseconds."""

    def __init__(self):
        self.now = 0.0

    def advance(self, ms):
        self.now += ms

    def advance_to(self, t):
        self.now = max(self.now, t)


# =============================================================================
# Milestone 1: ids, spans, parent/child on simulated time
# =============================================================================
class IdGenerator:
    """Random ids from a seeded generator, so a seed replays the same traces."""

    def __init__(self, rng):
        self.rng = rng

    def trace_id(self):
        """32 lowercase hex characters (128 bits), never all zeros."""
        while True:
            v = self.rng.getrandbits(128)
            if v:
                return f"{v:032x}"

    def span_id(self):
        """16 lowercase hex characters (64 bits), never all zeros."""
        while True:
            v = self.rng.getrandbits(64)
            if v:
                return f"{v:016x}"


class Tracer:
    """One service's tracer. Finished, sampled spans are appended to `sink`."""

    def __init__(self, service, clock, ids, sink, sampler=None):
        self.service, self.clock, self.ids, self.sink = service, clock, ids, sink
        self.sampler = sampler or (lambda trace_id: True)    # the HEAD sampling decision, made at a root
        self.stack = []                                       # ambient context: spans open in this process

    def current(self):
        return self.stack[-1] if self.stack else None

    def start_span(self, name, parent=None, kind="internal", links=(), attrs=None):
        """Create a span starting now (self.clock.now) and return it. Do not push it on the stack.

        `parent` may be a Span, a SpanContext or None.
          * If it is None, use the ambient span, self.current(), if there is one.
          * If there is still no parent, this is a ROOT: new trace id, parent_id None, and the
            sampled flag comes from self.sampler(trace_id).
          * Otherwise the span joins the parent's trace: same trace_id, parent_id = the parent's
            span_id, and it inherits the parent's `sampled` flag (a decision made once, at the
            root, rides along with the request).
        Every span gets a fresh span id. `links` is a sequence of SpanContexts (stored as a list).
        """
        parent = parent if parent is not None else self.current()
        if parent is None:
            trace_id = self.ids.trace_id()
            parent_id, sampled = None, bool(self.sampler(trace_id))
        else:
            trace_id, parent_id, sampled = parent.trace_id, parent.span_id, parent.sampled
        return Span(trace_id, self.ids.span_id(), parent_id, self.service, name, self.clock.now,
                    kind=kind, sampled=sampled, attrs=dict(attrs or {}), links=list(links))

    def finish(self, span, status=None):
        """End a span now. Set span.end to the clock; if `status` is given, set span.status.
        Raise ValueError if the span has already ended (a span ends exactly once). If the span is
        sampled, append it to self.sink: unsampled spans are never exported."""
        if span.end is not None:
            raise ValueError("span already ended")
        span.end = self.clock.now
        if status is not None:
            span.status = status
        if span.sampled:
            self.sink.append(span)

    @contextmanager
    def span(self, name, parent=None, kind="internal", links=(), attrs=None):
        """`with tracer.span("work") as s:` starts a span, makes it the ambient span for the
        block (push on self.stack), and on the way out pops it and finishes it. If the block
        raises, the span ends with status "error" and the exception propagates. The stack must be
        restored even when the block raises."""
        s = self.start_span(name, parent, kind, links, attrs)
        self.stack.append(s)
        try:
            yield s
        except BaseException:
            self.stack.pop()
            self.finish(s, "error")
            raise
        self.stack.pop()
        self.finish(s)


# =============================================================================
# Milestone 2: W3C trace context
# =============================================================================
def format_traceparent(ctx):
    """version-trace_id-parent_id-flags, lowercase hex, dash-separated. Version "00". The flags
    byte is "01" when ctx.sampled and "00" otherwise."""
    return f"00-{ctx.trace_id}-{ctx.span_id}-{'01' if ctx.sampled else '00'}"


def parse_traceparent(header):
    """Parse a traceparent header into a SpanContext, or return None if it is not valid.

    Rules (W3C Trace Context, version 00 and forward-compatibly later versions):
      * Surrounding spaces and tabs are ignored.
      * Four fields: version (2 hex), trace-id (32 hex), parent-id (16 hex), flags (2 hex), joined
        by single dashes. Hex digits are LOWERCASE only.
      * Version "ff" is invalid. Trace-id all zeros is invalid. Parent-id all zeros is invalid.
      * Version "00" must be exactly 55 characters: no trailing data allowed.
      * A version above "00" (01 to fe) may carry extra data, but only after a dash following the
        four fields: it is accepted if the header is exactly 55 characters or character 55 is "-".
      * sampled is the lowest bit of the flags byte (test with a mask, not equality).
    Never raise: any garbage (including a non-string) gives None.
    """
    if not isinstance(header, str):
        return None
    h = header.strip(" \t")
    if len(h) < 55:
        return None
    parts = h[:55].split("-")
    if len(parts) != 4:
        return None
    ver, tid, pid, flags = parts
    hexd = set("0123456789abcdef")
    for field_, n in ((ver, 2), (tid, 32), (pid, 16), (flags, 2)):
        if len(field_) != n or any(c not in hexd for c in field_):
            return None
    if ver == "ff" or tid == "0" * 32 or pid == "0" * 16:
        return None
    if ver == "00":
        if len(h) != 55:
            return None
    elif len(h) > 55 and h[55] != "-":
        return None
    return SpanContext(tid, pid, bool(int(flags, 16) & 1))


def inject(headers, ctx):
    """Write ctx into the headers dict under the name "traceparent"."""
    headers["traceparent"] = format_traceparent(ctx)


def extract(headers):
    """Read a SpanContext from a headers dict: the header name is case-insensitive
    ("traceparent", "Traceparent", "TRACEPARENT"). Return None if it is absent or invalid."""
    for k, v in headers.items():
        if k.lower() == "traceparent":
            return parse_traceparent(v)
    return None


# =============================================================================
# GIVEN: a world of simulated services
# =============================================================================
class World:
    """Services that call each other with headers, on one clock.

    `drop_headers` names services that sit behind a proxy which drops unknown headers: they
    receive no traceparent, so whatever they start is a new trace.
    """

    def __init__(self, seed, drop_headers=(), sampler=None):
        self.rng = random.Random(seed)
        self.clock = SimClock()
        self.ids = IdGenerator(self.rng)
        self.sink = []
        self.drop_headers = set(drop_headers)
        self.sampler = sampler
        self._tracers = {}

    def tracer(self, service):
        if service not in self._tracers:
            self._tracers[service] = Tracer(service, self.clock, self.ids, self.sink, self.sampler)
        return self._tracers[service]

    def call(self, caller, service, name, work):
        """The caller makes a client span, sends headers, the callee makes a server span under
        whatever it extracts, and runs `work(server_span)`. 1 ms of network each way."""
        with caller.span(f"call {service}", kind="client") as cs:
            headers = {}
            inject(headers, cs.context())
            self.clock.advance(1)
            callee = self.tracer(service)
            parent = None if service in self.drop_headers else extract(headers)
            with callee.span(name, parent=parent, kind="server") as ss:
                work(ss)
            self.clock.advance(1)
        return cs

    def parallel(self, thunks):
        """Run thunks 'at the same time': each starts at the current time; afterwards the clock is
        at the latest finish."""
        t0, ends = self.clock.now, []
        for th in thunks:
            self.clock.now = t0
            th()
            ends.append(self.clock.now)
        self.clock.now = max(ends)


def checkout_request(world, queue=None, fail_payment=False):
    """One user request through gateway -> checkout -> (inventory || pricing -> cache) -> payments.
    If `queue` is given, checkout also publishes an order message before it returns (milestone 3).
    Returns the root span."""
    gw = world.tracer("gateway")
    clock = world.clock

    def inventory(s):
        clock.advance(8)

    def pricing(s):
        clock.advance(1)
        with world.tracer("pricing").span("cache lookup") as c:
            clock.advance(2)
        clock.advance(22)

    def payments(s):
        clock.advance(2)
        with world.tracer("payments").span("db write") as d:
            clock.advance(12)
            if fail_payment:
                raise RuntimeError("card declined")

    def checkout(s):
        ck = world.tracer("checkout")
        clock.advance(3)
        world.parallel([lambda: world.call(ck, "inventory", "GET /stock", inventory),
                        lambda: world.call(ck, "pricing", "GET /price", pricing)])
        try:
            world.call(ck, "payments", "POST /charge", payments)
        except RuntimeError:
            pass
        if queue is not None:
            publish(world, ck, queue, {"order": 1})
        clock.advance(1)

    with gw.span("POST /checkout", kind="server") as root:
        clock.advance(1)
        world.call(gw, "checkout", "POST /checkout", checkout)
        clock.advance(1)
    return root


# =============================================================================
# Milestone 3: asynchronous propagation through a queue, with links
# =============================================================================
@dataclass
class Message:
    headers: dict
    body: dict
    deliver_at: float
    attempt: int = 1


class Queue:
    """A queue with a delivery delay. Messages carry headers, just like a broker's message headers."""

    def __init__(self, world, delay=(200, 900)):
        self.world, self.delay, self.heap, self.n = world, delay, [], 0

    def put(self, headers, body, extra_delay=0.0):
        d = self.world.rng.uniform(*self.delay) + extra_delay
        m = Message(dict(headers), body, self.world.clock.now + d)
        self.n += 1
        heapq.heappush(self.heap, (m.deliver_at, self.n, m))
        return m

    def redeliver(self, msg, after):
        """Put a failed message back, `after` ms from now; same headers, next attempt number."""
        m = replace(msg, deliver_at=self.world.clock.now + after, attempt=msg.attempt + 1)
        self.n += 1
        heapq.heappush(self.heap, (m.deliver_at, self.n, m))
        return m

    def take_all(self):
        out = []
        while self.heap:
            out.append(heapq.heappop(self.heap)[2])
        return out


def publish(world, tracer, queue, body):
    """Send a message. Make a producer span named "publish orders" (kind "producer") as a child of the
    ambient span, inject a traceparent for THAT span into a fresh headers dict, and put the message
    on the queue with queue.put(headers, body). The span covers 1 ms of simulated time
    (world.clock.advance(1) inside the span). Return the producer span."""
    with tracer.span("publish orders", kind="producer") as ps:
        headers = {}
        inject(headers, ps.context())
        queue.put(headers, body)
        world.clock.advance(1)
    return ps


def consume_as_child(world, tracer, msg, work_ms=20):
    """Process one message INSIDE the producer's trace. First world.clock.advance_to(msg.deliver_at). Then
    a span "process orders" (kind "consumer", attrs {"attempt": msg.attempt}) whose parent is the
    context extracted from the message headers; the work takes `work_ms`. Return the span."""
    world.clock.advance_to(msg.deliver_at)
    with tracer.span("process orders", parent=extract(msg.headers), kind="consumer",
                     attrs={"attempt": msg.attempt}) as s:
        world.clock.advance(work_ms)
    return s


def consume_linked(world, tracer, msg, work_ms=20, fail=False):
    """Process one message in a NEW trace that LINKS back to the producer. First advance_to the delivery time.
    Then a span "process orders" (kind "consumer", attrs {"attempt": msg.attempt}) with no parent and
    links=[the context extracted from the headers]. If `fail` is true the work raises RuntimeError inside
    the span (so the span ends with status "error") and the exception is swallowed after the span ends.
    Return the span. The extracted context may be None (a message without headers): then no links."""
    world.clock.advance_to(msg.deliver_at)
    ctx = extract(msg.headers)
    s = None
    try:
        # parent=None would fall back to the ambient span; the consumer has none, so this is a root
        with tracer.span("process orders", kind="consumer", links=[ctx] if ctx else [],
                         attrs={"attempt": msg.attempt}) as s:
            world.clock.advance(work_ms)
            if fail:
                raise RuntimeError("downstream unavailable")
    except RuntimeError:
        pass
    return s


def consume_batch(world, tracer, msgs, work_ms=40):
    """Process a batch of messages in ONE span "process orders batch" (kind "consumer", attrs
    {"batch_size": len(msgs)}) in a new trace, with one link per message that carries a valid context.
    advance_to the latest delivery time in the batch first. Return the span."""
    world.clock.advance_to(max(m.deliver_at for m in msgs))
    links = [c for c in (extract(m.headers) for m in msgs) if c is not None]
    with tracer.span("process orders batch", kind="consumer", links=links, attrs={"batch_size": len(msgs)}) as s:
        world.clock.advance(work_ms)
    return s


def trace_duration(spans):
    """Latest end minus earliest start, over the spans of one trace."""
    return max(s.end for s in spans) - min(s.start for s in spans)


# =============================================================================
# GIVEN: spans arriving at a collector, out of order
# =============================================================================
SERVICE_LAG = {"gateway": 5, "checkout": 40, "inventory": 120, "pricing": 15, "payments": 300, "fulfilment": 60}


def simulate_delivery(spans, seed, loss=0.0, dup=0.0, jitter=400.0):
    """The order in which a collector receives finished spans from many services.

    Every service batches and ships its spans after its own lag plus jitter, so spans arrive in an
    order unrelated to the order in which they happened: children before parents, one trace's spans
    interleaved with another's. `loss` drops spans, `dup` delivers some twice (an at-least-once exporter).
    Returns copies of the spans in arrival order."""
    rng = random.Random(seed)
    arrivals = []
    for sp in spans:
        if rng.random() < loss:
            continue
        for _ in range(2 if rng.random() < dup else 1):
            t = sp.end + SERVICE_LAG.get(sp.service, 50) + rng.uniform(0, jitter)
            arrivals.append((t, len(arrivals), replace(sp, attrs=dict(sp.attrs), links=list(sp.links))))
    arrivals.sort(key=lambda a: (a[0], a[1]))
    return [a[2] for a in arrivals]


# =============================================================================
# Milestone 4: assembling trace trees
# =============================================================================
@dataclass
class Node:
    span_id: str
    span: Optional[Span]                   # None for a placeholder standing in for a span we never received
    children: list = field(default_factory=list)

    @property
    def missing(self):
        return self.span is None


@dataclass
class Tree:
    trace_id: str
    roots: list                            # real roots (parent_id None) by start time, then placeholders by span id
    span_count: int                        # number of distinct real spans
    missing_parents: set                   # parent ids that were referenced but never received

    @property
    def complete(self):
        return not self.missing_parents


def assemble(spans):
    """Group spans (in ANY order, possibly duplicated, from many traces) into one Tree per trace.

    Returns a dict {trace_id: Tree}.
      * Duplicates (same trace_id and span_id) count once. If one copy has an end time and another does
        not, keep the one that has.
      * A span whose parent_id is None is a root. A span whose parent was received becomes that
        parent's child. A span whose parent_id was NOT received hangs under a placeholder Node
        (Node(span_id=<the missing parent id>, span=None)) which is itself a root of the tree, and the
        id goes into tree.missing_parents. Children of a placeholder share one placeholder.
      * Children of every node are sorted by (start, span_id). tree.roots lists real roots sorted by
        (start, span_id), then placeholders sorted by id.
      * The result must not depend on the order of the input.
    """
    by_trace = {}
    for sp in spans:
        d = by_trace.setdefault(sp.trace_id, {})
        old = d.get(sp.span_id)
        if old is None or (old.end is None and sp.end is not None):
            d[sp.span_id] = sp
    out = {}
    for tid, d in by_trace.items():
        nodes = {sid: Node(sid, sp) for sid, sp in d.items()}
        roots, holes = [], {}
        for sid, sp in d.items():
            if sp.parent_id is None:
                roots.append(nodes[sid])
            elif sp.parent_id in nodes:
                nodes[sp.parent_id].children.append(nodes[sid])
            else:
                holes.setdefault(sp.parent_id, Node(sp.parent_id, None)).children.append(nodes[sid])
        key = lambda n: (n.span.start, n.span_id)
        for n in list(nodes.values()) + list(holes.values()):
            n.children.sort(key=key)
        roots.sort(key=key)
        out[tid] = Tree(tid, roots + [holes[k] for k in sorted(holes)], len(d), set(holes))
    return out


def render_tree(tree, width=40):
    """A text waterfall of a Tree. Placeholders print as <missing span ...>."""
    real = [n.span for r in tree.roots for n in _walk(r) if n.span]
    t0 = min(s.start for s in real) if real else 0
    t1 = max(s.end for s in real) if real else 1
    scale = width / max(t1 - t0, 1e-9)
    lines = [f"trace {tree.trace_id[:8]}  {tree.span_count} spans" + ("" if tree.complete else "  INCOMPLETE")]

    def go(n, d):
        if n.span is None:
            lines.append(f"{'  ' * d}<missing span {n.span_id[:8]}>")
        else:
            s = n.span
            a = int((s.start - t0) * scale)
            b = max(a + 1, int(round((s.end - t0) * scale)))
            label = f"{'  ' * d}{s.name}"
            lines.append(f"{label:30s}{s.service:10s}|{' ' * a}{'#' * (b - a)}{' ' * (width - b)}|{s.end - s.start:7.1f} ms")
        for c in n.children:
            go(c, d + 1)
    for r in tree.roots:
        go(r, 0)
    return "\n".join(lines)


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


# =============================================================================
# Milestone 5: critical path, and head vs tail sampling
# =============================================================================
def critical_path(node):
    """The chain of spans that determines when `node`'s span ends, with each span's SELF time.

    Returns [(span, self_ms), ...] in chronological depth-first order, starting with node.span.
    Walk backwards from the end of the span: t = span.end. Consider its children from the last to
    finish to the first; a child whose end <= t is ON the path (a child that ends after t overlaps
    one already chosen, or outlives its parent: not on the path), and then t = that child's start.
    The span's self time is its duration minus the durations of its on-path children. Recurse into
    the on-path children. The self times along the whole path add up to node.span.duration.
    """
    s = node.span
    t, chain = s.end, []
    for c in sorted(node.children, key=lambda c: (c.span.end, c.span.start), reverse=True):
        if c.span.end <= t + 1e-9:
            chain.append(c)
            t = c.span.start
    chain.sort(key=lambda c: c.span.start)
    out = [(s, s.duration - sum(c.span.duration for c in chain))]
    for c in chain:
        out += critical_path(c)
    return out


def head_keep(trace_id, rate):
    """The head-sampling decision: keep the trace if a number derived from its id is below `rate`.
    Use the low 64 bits of the id as a fraction of 2**64: int(trace_id[16:], 16) / 2**64 < rate.
    It depends on the trace id alone, so every service that sees the id decides the same way.
    (This assumes trace ids are random, as the W3C recommends.)"""
    return int(trace_id[16:], 16) / 2 ** 64 < rate


def tail_decision(spans, slow_ms, baseline_rate):
    """Decide about a COMPLETE buffered trace. Return the reason it is kept, or None to drop it:
      "error"     if any span has status "error"
      "slow"      else if the trace's duration (trace_duration) is above slow_ms
      "baseline"  else if head_keep(trace_id, baseline_rate): a small unbiased sample of ordinary traces
      None        otherwise."""
    if any(s.status == "error" for s in spans):
        return "error"
    if trace_duration(spans) > slow_ms:
        return "slow"
    if head_keep(spans[0].trace_id, baseline_rate):
        return "baseline"
    return None


def baseline_rate(budget, total, interesting):
    """The baseline sampling rate that makes a tail sampler store `budget` traces in all, when
    `total` traces arrive and `interesting` of them (errors and slow ones) are always kept:
    (budget - interesting) / (total - interesting), clamped to [0, 1]. If nothing is left to
    sample (total == interesting) return 0.0."""
    if total <= interesting:
        return 0.0
    return min(1.0, max(0.0, (budget - interesting) / (total - interesting)))


class TailSampler:
    """Buffers spans per trace until the trace has been quiet for `wait_ms`, then decides."""

    def __init__(self, wait_ms, slow_ms, rate):
        self.wait_ms, self.slow_ms, self.rate = wait_ms, slow_ms, rate
        self.buf = {}                        # trace_id -> [last_arrival, [spans]]
        self.peak_traces = self.peak_spans = 0
        self.kept = {}                       # trace_id -> reason
        self.dropped = set()

    def add(self, span, now):
        entry = self.buf.setdefault(span.trace_id, [now, []])
        entry[0] = now
        entry[1].append(span)
        self.peak_traces = max(self.peak_traces, len(self.buf))
        self.peak_spans = max(self.peak_spans, sum(len(e[1]) for e in self.buf.values()))

    def flush(self, now):
        for tid in [t for t, e in self.buf.items() if now - e[0] >= self.wait_ms]:
            spans = self.buf.pop(tid)[1]
            reason = tail_decision(spans, self.slow_ms, self.rate)
            if reason:
                self.kept[tid] = reason
            else:
                self.dropped.add(tid)


@dataclass
class Workload:
    traces: list            # one list of spans per request, in request order
    kinds: list             # "error", "slow" or "ok", per trace
    rps: float


def make_workload(seed, n=20000, rps=50.0, error_rate=0.005, slow_rate=0.02):
    """n requests arriving at `rps` per second. Each trace has 6 spans (gateway -> checkout -> inventory,
    pricing -> cache, payments). A trace is an error (one span has status "error"), slow (pricing takes
    1 to 3 seconds extra) or ordinary. Times are in ms. Built directly, not via World, to keep it fast."""
    rng = random.Random(seed)
    ids = IdGenerator(rng)
    traces, kinds = [], []
    for i in range(n):
        t0 = i * 1000.0 / rps + rng.uniform(0, 1000.0 / rps)
        r = rng.random()
        kind = "error" if r < error_rate else "slow" if r < error_rate + slow_rate else "ok"
        tid = ids.trace_id()
        sid = [ids.span_id() for _ in range(6)]
        inv = rng.uniform(5, 14)
        price = rng.uniform(15, 30) + (rng.uniform(1000, 3000) if kind == "slow" else 0)
        pay = rng.uniform(10, 18)
        c0 = t0 + 1
        ck = c0 + 3
        par_end = ck + 1 + max(inv, price + 3) + 1
        pay_end = par_end + 2 + pay + 1
        end = pay_end + 3
        mk = lambda k, par, svc, name, a, b, kd="internal": Span(tid, sid[k], par, svc, name, a, b, kind=kd)
        spans = [
            mk(0, None, "gateway", "POST /checkout", t0, end, "server"),
            mk(1, sid[0], "checkout", "POST /checkout", c0, end - 1, "server"),
            mk(2, sid[1], "inventory", "GET /stock", ck + 1, ck + 1 + inv),
            mk(3, sid[1], "pricing", "GET /price", ck + 1, ck + 1 + price),
            mk(4, sid[3], "pricing", "cache lookup", ck + 2, ck + 4),
            mk(5, sid[1], "payments", "POST /charge", par_end, pay_end),
        ]
        if kind == "error":
            spans[rng.choice([2, 3, 5])].status = "error"
        traces.append(spans)
        kinds.append(kind)
    return Workload(traces, kinds, rps)
