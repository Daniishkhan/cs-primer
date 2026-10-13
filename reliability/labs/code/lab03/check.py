"""Self-check for Lab 3: Tracing from Scratch.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 7     # milestone 4, replaying ONLY seed 7

The "services" are Python functions in one process, time is a simulated clock, and every random
number is seeded, so every run is identical and the whole check takes a few seconds.
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


HEX32, HEX16 = re.compile(r"^[0-9a-f]{32}$"), re.compile(r"^[0-9a-f]{16}$")


def trace_spans(world, trace_id):
    return [s for s in world.sink if s.trace_id == trace_id]


# =============================================================================
# Milestone 1: ids, spans, parent/child on simulated time
# =============================================================================
class ScriptedRng:
    """An rng stub that returns scripted values from getrandbits."""

    def __init__(self, values):
        self.values = list(values)

    def getrandbits(self, k):
        return self.values.pop(0)


def m1():
    g = mod.IdGenerator(random.Random(1))
    tids = [g.trace_id() for _ in range(10000)]
    sids = [g.span_id() for _ in range(10000)]
    assert all(HEX32.match(t) for t in tids), f"trace ids are 32 lowercase hex characters; got {tids[0]!r}"
    assert all(HEX16.match(s) for s in sids), f"span ids are 16 lowercase hex characters; got {sids[0]!r}"
    assert len(set(tids)) == 10000 and len(set(sids)) == 10000, "10,000 random ids should all be different"
    assert [mod.IdGenerator(random.Random(5)).trace_id() for _ in range(2)][0] == mod.IdGenerator(random.Random(5)).trace_id(), \
        "the same seed must give the same ids"
    z = mod.IdGenerator(ScriptedRng([0, 0, 7]))
    assert z.trace_id() == "0" * 31 + "7", "an all-zero id is invalid: draw again"
    z = mod.IdGenerator(ScriptedRng([0, 255]))
    assert z.span_id() == "0" * 14 + "ff", "an all-zero span id is invalid: draw again"

    w = mod.World(1)
    t = w.tracer("svc")
    s = t.start_span("root")
    assert s.parent_id is None and s.end is None and s.start == 0 and s.service == "svc" and s.name == "root"
    assert HEX32.match(s.trace_id) and HEX16.match(s.span_id) and s.sampled is True
    assert t.current() is None, "start_span must not push the span on the ambient stack"
    w.clock.advance(5)
    t.finish(s)
    assert s.end == 5 and s.status == "ok" and s.duration == 5, "finish stamps the end from the clock"
    assert w.sink == [s], "a finished, sampled span goes to the sink"
    try:
        t.finish(s)
    except ValueError:
        pass
    else:
        raise AssertionError("a span ends exactly once: finishing twice must raise ValueError")
    assert len(w.sink) == 1

    w = mod.World(2)
    t = w.tracer("svc")
    with t.span("outer", attrs={"k": 1}) as outer:
        w.clock.advance(10)
        with t.span("inner") as inner:
            w.clock.advance(20)
            assert t.current() is inner
        assert t.current() is outer
        w.clock.advance(5)
    assert t.current() is None and t.stack == [], "the stack is empty after the blocks"
    assert inner.parent_id == outer.span_id and inner.trace_id == outer.trace_id, "a nested span is a child in the same trace"
    assert outer.parent_id is None and outer.attrs == {"k": 1}
    assert (outer.start, outer.end) == (0, 35) and (inner.start, inner.end) == (10, 30), \
        f"times come from the simulated clock: outer 0..35, inner 10..30; got {(outer.start, outer.end)}, {(inner.start, inner.end)}"
    assert [x.name for x in w.sink] == ["inner", "outer"], "spans are exported in the order they FINISH: children before parents"
    with t.span("second root") as r2:
        pass
    assert r2.trace_id != outer.trace_id and r2.parent_id is None, "after the first trace ends, a new root starts a new trace"

    # explicit parents (a SpanContext from another process) and links
    other = w.tracer("other")
    ctx = mod.SpanContext("a" * 32, "b" * 16, True)
    with other.span("remote child", parent=ctx) as rc:
        pass
    assert rc.trace_id == "a" * 32 and rc.parent_id == "b" * 16, "an explicit SpanContext parent decides trace and parent ids"
    with t.span("busy"):
        with t.span("elsewhere", parent=ctx) as e2:
            pass
    assert e2.trace_id == "a" * 32, "an explicit parent beats the ambient span"
    lk = other.start_span("linked", links=[ctx])
    assert lk.links == [ctx] and lk.parent_id is None and lk.trace_id != "a" * 32, "links are stored; they do not make a parent"

    # failure inside a span
    w = mod.World(3)
    t = w.tracer("svc")
    try:
        with t.span("outer"):
            with t.span("boom") as boom:
                w.clock.advance(3)
                raise KeyError("x")
    except KeyError:
        pass
    else:
        raise AssertionError("an exception inside a span block must propagate")
    assert t.stack == [], "the stack is restored even when the block raises"
    names = {s.name: s for s in w.sink}
    assert names["boom"].status == "error" and names["outer"].status == "error", \
        "both spans the exception passed through end with status 'error'"
    assert names["boom"].end == 3

    # head sampling: the root decides, everyone below inherits, unsampled spans are never exported
    w = mod.World(4, sampler=lambda tid: False)
    t = w.tracer("svc")
    with t.span("root") as r:
        with t.span("child") as c:
            pass
    assert r.sampled is False and c.sampled is False, "children inherit the root's sampled flag"
    assert w.sink == [], "unsampled spans are not exported"
    w = mod.World(4, sampler=lambda tid: tid[0] in "01234567")
    t = w.tracer("svc")
    for _ in range(40):
        with t.span("root"):
            pass
    assert 5 < len(w.sink) < 35, "the sampler is consulted once per root, with the new trace id"
    return "ids are random-looking, never zero, and replay by seed; spans nest on simulated time and survive exceptions"


# =============================================================================
# Milestone 2: traceparent
# =============================================================================
SPEC = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def m2():
    c = mod.parse_traceparent(SPEC)
    assert c == mod.SpanContext("4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7", True), f"the W3C example must parse; got {c}"
    assert mod.format_traceparent(c) == SPEC, "format must reproduce the W3C example exactly"
    assert mod.format_traceparent(mod.SpanContext("1" * 32, "2" * 16, False)) == "00-" + "1" * 32 + "-" + "2" * 16 + "-00"
    assert len(SPEC) == 55
    rng = random.Random(1)
    for _ in range(500):
        ctx = mod.SpanContext(f"{rng.getrandbits(128) | 1:032x}", f"{rng.getrandbits(64) | 1:016x}", rng.random() < 0.5)
        back = mod.parse_traceparent(mod.format_traceparent(ctx))
        assert back == ctx, f"round trip failed for {ctx}: got {back}"

    t, p = "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7"
    invalid = {
        "empty": "", "garbage": "hello", "three fields": f"00-{t}-{p}", "no dashes": f"00{t}{p}01",
        "uppercase trace id": f"00-{t.upper()}-{p}-01", "uppercase parent id": f"00-{t}-{p.upper()}-01",
        "uppercase flags": f"00-{t}-{p}-0A", "all-zero trace id": f"00-{'0' * 32}-{p}-01",
        "all-zero parent id": f"00-{t}-{'0' * 16}-01", "version ff": f"ff-{t}-{p}-01",
        "short trace id": f"00-{t[:-1]}-{p}-01", "long trace id": f"00-{t}0-{p}-01",
        "short parent id": f"00-{t}-{p[:-1]}-01", "short flags": f"00-{t}-{p}-1",
        "non-hex": f"00-{t[:-1]}g-{p}-01", "non-hex version": f"0g-{t}-{p}-01",
        "version 00 with extra field": f"00-{t}-{p}-01-extra", "version 00 with trailing dash": f"00-{t}-{p}-01-",
        "version 00 with trailing space inside": f"00-{t}-{p}-01 x",
        "future version, data without a dash": f"01-{t}-{p}-01extra", "wrong separator": f"00_{t}_{p}_01",
        "None": None, "bytes": SPEC.encode(), "int": 5,
    }
    for why, h in invalid.items():
        got = mod.parse_traceparent(h)
        assert got is None, f"parse_traceparent must reject {why}: {h!r}; got {got}"
    assert mod.parse_traceparent(f"01-{t}-{p}-01") == mod.SpanContext(t, p, True), "a future version with exactly four fields is fine"
    assert mod.parse_traceparent(f"01-{t}-{p}-01-whatever-else") == mod.SpanContext(t, p, True), \
        "a future version may carry extra data after a dash"
    assert mod.parse_traceparent(f"  {SPEC}\t") == mod.SpanContext(t, p, True), "surrounding spaces and tabs are ignored"
    for flags, sampled in (("00", False), ("01", True), ("02", False), ("03", True), ("ff", True), ("fe", False)):
        got = mod.parse_traceparent(f"00-{t}-{p}-{flags}")
        assert got is not None and got.sampled is sampled, f"flags {flags}: sampled is the LOWEST BIT, expected {sampled}"

    h = {}
    mod.inject(h, c)
    assert h == {"traceparent": SPEC}, f"inject writes one header named 'traceparent'; got {h}"
    for name in ("traceparent", "Traceparent", "TRACEPARENT"):
        assert mod.extract({name: SPEC, "other": "x"}) == c, f"header names are case-insensitive: {name}"
    assert mod.extract({}) is None and mod.extract({"traceparent": "junk"}) is None and mod.extract({"x": SPEC}) is None

    # end to end: one request through six services
    w = mod.World(1)
    root = mod.checkout_request(w)
    spans = w.sink
    assert len(spans) == 11, f"expected 11 spans for a checkout request, got {len(spans)}: {[s.service + ':' + s.name for s in spans]}"
    assert len({s.trace_id for s in spans}) == 1, "every service must join the SAME trace: the header carried the context"
    by_id = {s.span_id: s for s in spans}
    assert sum(1 for s in spans if s.parent_id is None) == 1 and root.parent_id is None
    for s in spans:
        if s.kind == "server" and s.service != "gateway":
            par = by_id[s.parent_id]
            assert par.kind == "client" and par.service != s.service, (
                f"server span {s.service}:{s.name} must be the child of the CALLER's client span, got "
                f"{par.service}:{par.name}")
    assert round(root.duration, 6) == 51.0, f"the simulated request takes 51 ms end to end; got {root.duration}"
    # the broken hop: a proxy in front of pricing drops the header
    w = mod.World(1, drop_headers={"pricing"})
    mod.checkout_request(w)
    traces = {}
    for s in w.sink:
        traces.setdefault(s.trace_id, []).append(s)
    assert len(traces) == 2, f"a hop that drops the header severs the trace: expected 2 traces, got {len(traces)}"
    small = min(traces.values(), key=len)
    assert sorted(s.name for s in small) == ["GET /price", "cache lookup"] and any(s.parent_id is None for s in small), \
        "pricing's work starts a new trace of its own, with its server span as a new root"
    # the sampled decision rides in the flags byte
    w = mod.World(1)
    t = w.tracer("a")
    s = t.start_span("x", parent=mod.SpanContext("1" * 32, "2" * 16, False))
    hdr = {}
    mod.inject(hdr, s.context())
    assert hdr["traceparent"].endswith("-00") and mod.extract(hdr).sampled is False, "an unsampled context travels as flags 00"
    return "the W3C example parses and formats; 23 invalid headers rejected; one request keeps one trace id across 6 services; a header-dropping proxy splits it in two"


# =============================================================================
# Milestone 3: queues and links
# =============================================================================
def one_flow(seed, **kw):
    w = mod.World(seed)
    q = mod.Queue(w, **kw)
    root = mod.checkout_request(w, q)
    pub = next(s for s in w.sink if s.kind == "producer")
    return w, q, root, pub


def m3():
    w, q, root, pub = one_flow(3)
    assert pub.name == "publish orders" and pub.kind == "producer" and pub.service == "checkout"
    server = next(s for s in w.sink if s.service == "checkout" and s.kind == "server")
    assert pub.parent_id == server.span_id and pub.trace_id == root.trace_id, "the producer span is a child of the ambient span"
    assert pub.duration == 1, "the publish span covers 1 ms of simulated time"
    msgs = list(q.heap)
    assert len(msgs) == 1, "publish puts exactly one message on the queue"
    msg = q.take_all()[0]
    assert set(msg.headers) == {"traceparent"} and mod.parse_traceparent(msg.headers["traceparent"]) == pub.context(), \
        "the message headers carry the PRODUCER span's context (so the consumer can name it as parent or link)"
    assert msg.deliver_at >= pub.end + 200, "the queue adds its delivery delay"

    # mode A: the consumer continues the producer's trace as a child
    fulfil = w.tracer("fulfilment")
    n_before = len(w.sink)
    s = mod.consume_as_child(w, fulfil, msg)
    assert s.trace_id == root.trace_id and s.parent_id == pub.span_id and s.kind == "consumer", "child mode: same trace, parent = publish span"
    assert s.start >= msg.deliver_at and s.attrs.get("attempt") == 1 and near(s.duration, 20)
    gap = s.start - pub.end
    whole = mod.trace_duration(trace_spans(w, root.trace_id))
    assert gap >= 200 and whole > gap, f"in child mode the trace includes the queue wait: gap {gap:.0f} ms, trace {whole:.0f} ms"

    # mode B: a new trace with a link back
    w2, q2, root2, pub2 = one_flow(3)
    msg2 = q2.take_all()[0]
    s2 = mod.consume_linked(w2, w2.tracer("fulfilment"), msg2)
    assert s2.trace_id != root2.trace_id and s2.parent_id is None, "linked mode: a NEW trace, no parent"
    assert s2.links == [pub2.context()], f"linked mode: one link, to the publish span's context; got {s2.links}"
    assert s2.kind == "consumer" and s2.attrs.get("attempt") == 1
    short = mod.trace_duration(trace_spans(w2, root2.trace_id))
    assert short < 100 and mod.trace_duration(trace_spans(w2, s2.trace_id)) == s2.duration, \
        "in linked mode both traces stay short: the request's trace does not include the queue wait"

    # a retry hours later still links to the SAME publish span
    w3, q3, root3, pub3 = one_flow(4)
    m = q3.take_all()[0]
    cons = w3.tracer("fulfilment")
    a1 = mod.consume_linked(w3, cons, m, fail=True)
    assert a1.status == "error" and a1.end is not None, "a failing consumer ends its span with status 'error' and swallows the exception"
    assert cons.stack == [], "the consumer's ambient stack is clean after a failure"
    m_retry = q3.redeliver(m, 5000)
    a2 = mod.consume_linked(w3, cons, q3.take_all()[0])
    assert a2.attrs["attempt"] == 2 and a2.links == [pub3.context()] and a2.start >= a1.end + 5000 - 1e-9, \
        "the retry (attempt 2, 5 s later) links to the same publish span"
    assert a2.trace_id != a1.trace_id, "every attempt is its own trace"

    # a batch of messages from five different traces: one span, five links
    wb = mod.World(9)
    qb = mod.Queue(wb)
    roots = [mod.checkout_request(wb, qb) for _ in range(5)]
    mb = qb.take_all()
    bs = mod.consume_batch(wb, wb.tracer("fulfilment"), mb)
    assert bs.attrs.get("batch_size") == 5 and bs.name == "process orders batch" and bs.parent_id is None
    assert len(bs.links) == 5, f"one link per message: expected 5, got {len(bs.links)}"
    assert sorted(l.trace_id for l in bs.links) == sorted(r.trace_id for r in roots), "the links point into the five producers' traces"
    assert bs.trace_id not in {r.trace_id for r in roots} and bs.start >= max(x.deliver_at for x in mb)
    # a message with no usable context gets no link, but is still processed
    wb = mod.World(9)
    qb = mod.Queue(wb)
    for _ in range(3):
        mod.checkout_request(wb, qb)
    mb = qb.take_all()
    mb[0].headers.clear()
    mb[1].headers["traceparent"] = "garbage"
    bs = mod.consume_batch(wb, wb.tracer("fulfilment"), mb)
    assert len(bs.links) == 1 and bs.attrs["batch_size"] == 3, "messages without a valid context contribute no link (but count in batch_size)"
    s0 = mod.consume_linked(wb, wb.tracer("fulfilment"), mb[0])
    assert s0.links == [] and s0.parent_id is None, "a message without headers: process it in a new trace, with no links"
    return (f"child mode: queue wait of {gap:.0f} ms is inside a {whole:.0f} ms trace; linked mode: the request's trace stays {short:.0f} ms "
            "and the consumer's own trace links back; a batch of 5 messages is one span with 5 links")


# =============================================================================
# Milestone 4: assembling trees from out-of-order spans
# =============================================================================
def world_with_traces(seed, n):
    w = mod.World(seed)
    q = mod.Queue(w)
    roots = []
    for _ in range(n):
        roots.append(mod.checkout_request(w, q, fail_payment=(len(roots) % 4 == 3)))
        w.clock.advance(w.rng.uniform(1, 30))
    fulfil = w.tracer("fulfilment")
    for m in q.take_all():
        mod.consume_as_child(w, fulfil, m)
    return w


def canon(node):
    """Order-independent structure: (span id, sorted child structures)."""
    return (node.span_id, tuple(sorted(canon(c) for c in node.children)))


def truth_canon(spans):
    kids = {}
    for s in spans:
        kids.setdefault(s.parent_id, []).append(s)

    def go(s):
        return (s.span_id, tuple(sorted(go(c) for c in kids.get(s.span_id, []))))
    return go


def count_nodes(n):
    return 1 + sum(count_nodes(c) for c in n.children)


def m4():
    note = ""
    for s in seeds((1, 2, 3)):
        w = world_with_traces(s, 12)
        by_trace = {}
        for sp in w.sink:
            by_trace.setdefault(sp.trace_id, []).append(sp)
        assert len(by_trace) == 12 and all(len(v) == 13 for v in by_trace.values()), "world: 12 traces of 13 spans"
        truth = {}
        for tid, sps in by_trace.items():
            root = next(x for x in sps if x.parent_id is None)
            truth[tid] = truth_canon(sps)(root)
        ref = None
        for order_seed in range(25):
            arrived = mod.simulate_delivery(w.sink, order_seed * 7 + s, jitter=2000.0)
            if order_seed % 5 == 4:
                random.Random(order_seed).shuffle(arrived)
            before = [(x.trace_id, x.span_id, x.end) for x in arrived]
            trees = mod.assemble(arrived)
            assert [(x.trace_id, x.span_id, x.end) for x in arrived] == before, "assemble must not modify its input"
            assert set(trees) == set(by_trace), f"seed {s}/{order_seed}: expected one tree per trace id"
            for tid, tr in trees.items():
                assert tr.complete and tr.missing_parents == set() and tr.span_count == 13, f"seed {s}/{order_seed}: trace {tid[:8]} should be complete with 13 spans"
                assert len(tr.roots) == 1 and not tr.roots[0].missing, "one real root"
                assert canon(tr.roots[0]) == truth[tid], f"seed {s}/{order_seed}: tree of trace {tid[:8]} differs from the real call structure"
                assert all(n.span.trace_id == tid for r in tr.roots for n in mod._walk(r)), "spans of different traces were mixed"
                for r in tr.roots:
                    for n in mod._walk(r):
                        starts = [(c.span.start, c.span_id) for c in n.children]
                        assert starts == sorted(starts), "children must be sorted by (start, span id)"
            if ref is None:
                ref = {tid: render for tid, render in ((t, mod.render_tree(tr)) for t, tr in trees.items())}
            else:
                assert {t: mod.render_tree(tr) for t, tr in trees.items()} == ref, \
                    f"seed {s}/{order_seed}: the result depends on arrival order"
        if s == seeds((1,))[0]:
            tid = next(iter(by_trace))
            note = mod.render_tree(mod.assemble(w.sink)[tid])

        # duplicates: an at-least-once exporter delivers some spans twice
        arrived = mod.simulate_delivery(w.sink, 99, dup=0.5)
        assert len(arrived) > len(w.sink)
        for tid, tr in mod.assemble(arrived).items():
            assert tr.span_count == 13 and tr.complete, "duplicate deliveries must count once"
        # an in-flight copy (no end yet) and a finished copy of the same span: keep the finished one
        sp = w.sink[0]
        open_copy = mod.replace(sp, end=None)
        for order in ([open_copy, sp], [sp, open_copy]):
            tr = mod.assemble([x for x in w.sink[1:] if x.trace_id == sp.trace_id] + order)[sp.trace_id]
            kept = next(n.span for r in tr.roots for n in mod._walk(r) if n.span_id == sp.span_id)
            assert kept.end == sp.end, "when two copies disagree, keep the one that has an end time"

        # one lost span in the middle, one lost root
        tid = next(iter(by_trace))
        sps = by_trace[tid]
        victim = next(x for x in sps if x.name == "call pricing")
        tr = mod.assemble([x for x in w.sink if x.span_id != victim.span_id])[tid]
        assert not tr.complete and tr.missing_parents == {victim.span_id} and tr.span_count == 12, \
            f"seed {s}: losing 'call pricing' must be detected: missing_parents {tr.missing_parents}"
        holes = [r for r in tr.roots if r.missing]
        assert len(tr.roots) == 2 and len(holes) == 1 and holes[0].span_id == victim.span_id, "orphans hang under ONE placeholder for the lost span"
        assert [c.span.name for c in holes[0].children] == ["GET /price"], "the pricing server span is the placeholder's child"
        assert count_nodes(tr.roots[0]) + count_nodes(holes[0]) == 13, "no span may be dropped: 12 real nodes plus the placeholder"
        rootspan = next(x for x in sps if x.parent_id is None)
        tr = mod.assemble([x for x in w.sink if x.span_id != rootspan.span_id])[tid]
        assert tr.roots and all(r.missing for r in tr.roots) and tr.missing_parents == {rootspan.span_id}, "a lost root: its children hang under a placeholder"

    # loss in transit: every lost span that had a surviving child is detected; lost leaves are invisible
    w = world_with_traces(5, 60)
    for loss_seed in seeds((1, 2)):
        arrived = mod.simulate_delivery(w.sink, loss_seed, loss=0.08)
        got = {s.span_id for s in arrived}
        all_by_trace = {}
        for sp in w.sink:
            all_by_trace.setdefault(sp.trace_id, []).append(sp)
        trees = mod.assemble(arrived)
        detectable = invisible = 0
        for tid, sps in all_by_trace.items():
            lost = {x.span_id for x in sps if x.span_id not in got}
            orphaned = {x.parent_id for x in sps if x.span_id in got and x.parent_id in lost}
            if tid not in trees:
                assert len(lost) == len(sps)
                continue
            tr = trees[tid]
            assert tr.missing_parents == orphaned, (f"loss seed {loss_seed}, trace {tid[:8]}: missing_parents should be the lost spans "
                                                    f"that had surviving children {sorted(i[:6] for i in orphaned)}; got {sorted(i[:6] for i in tr.missing_parents)}")
            assert tr.complete == (not orphaned)
            detectable += bool(orphaned)
            invisible += bool(lost and not orphaned)
    return (f"{note}\n" if note else "") + (f"25 arrival orders x 3 seeds give identical trees; lost parents are found "
            f"({detectable} traces flagged incomplete); {invisible} traces lost only leaf spans and look complete - a tree cannot see a span it never heard of")


# =============================================================================
# Milestone 5: critical path and sampling
# =============================================================================
def sp(i, parent, name, a, b, status="ok"):
    return mod.Span("t" * 32, f"{i:016x}", None if parent is None else f"{parent:016x}", "svc", name, a, b, status=status)


def tree_of(spans):
    return mod.assemble(spans)["t" * 32].roots[0]


def m5():
    # the chapter-6 trace: 48 ms, parallel inventory and pricing, then a database write
    ch = tree_of([sp(1, None, "POST /checkout", 0, 48), sp(2, 1, "call inventory", 3, 13), sp(3, 2, "GET /stock", 4, 12),
                  sp(4, 1, "call pricing", 3, 30), sp(5, 4, "GET /price", 4, 29), sp(6, 5, "cache lookup", 5, 7), sp(7, 1, "db write", 35, 47)])
    path = mod.critical_path(ch)
    names = [s.name for s, _ in path]
    selfs = {s.name: round(t, 6) for s, t in path}
    assert names == ["POST /checkout", "call pricing", "GET /price", "cache lookup", "db write"], \
        f"critical path of the chapter-6 trace: expected root, call pricing, GET /price, cache lookup, db write; got {names}"
    assert selfs == {"POST /checkout": 9, "call pricing": 2, "GET /price": 23, "cache lookup": 2, "db write": 12}, f"self times: {selfs}"
    assert near(sum(t for _, t in path), 48), "self times along the path add up to the trace duration"
    leaf = tree_of([sp(1, None, "only", 5, 12)])
    assert [(s.name, t) for s, t in mod.critical_path(leaf)] == [("only", 7)]
    par = tree_of([sp(1, None, "root", 0, 100), sp(2, 1, "A", 10, 60), sp(3, 1, "B", 10, 90)])
    got = [(s.name, t) for s, t in mod.critical_path(par)]
    assert got == [("root", 20), ("B", 80)], f"parallel branches: only the slower one is on the path; got {got}"
    seq = tree_of([sp(1, None, "root", 0, 100), sp(2, 1, "A", 10, 30), sp(3, 1, "B", 50, 70)])
    got = [(s.name, t) for s, t in mod.critical_path(seq)]
    assert got == [("root", 60), ("A", 20), ("B", 20)], f"sequential calls are all on the path, in time order; got {got}"
    late = tree_of([sp(1, None, "root", 0, 100), sp(2, 1, "async tail", 50, 130), sp(3, 1, "A", 10, 90)])
    got = [s.name for s, _ in mod.critical_path(late)]
    assert got == ["root", "A"], f"a child that outlives its parent is not on the path; got {got}"

    def random_tree(rng, a, b, depth, ids, out, parent):
        i = next(ids)
        out.append(sp(i, parent, f"s{i}", a, b))
        if depth == 0 or b - a < 8:
            return
        if rng.random() < 0.5:                                # sequential children
            t, k = a + rng.uniform(0, 2), rng.randint(1, 3)
            for _ in range(k):
                dur = rng.uniform(1, (b - t) / 2) if b - t > 2 else 0
                if dur < 1:
                    break
                random_tree(rng, t, t + dur, depth - 1, ids, out, i)
                t += dur + rng.uniform(0, 2)
        else:                                                 # parallel children
            for _ in range(rng.randint(2, 4)):
                x = a + rng.uniform(0, 3)
                y = rng.uniform(x + 1, b - 0.5)
                random_tree(rng, x, y, depth - 1, ids, out, i)

    import itertools
    for s in seeds(range(200)):
        rng = random.Random(s)
        out = []
        random_tree(rng, 0.0, rng.uniform(50, 500), 4, itertools.count(1), out, None)
        root = tree_of(out)
        path = mod.critical_path(root)
        assert near(sum(t for _, t in path), root.span.duration, 1e-6), f"seed {s}: self times {sum(t for _, t in path):.3f} != duration {root.span.duration:.3f}"
        assert all(t >= -1e-9 for _, t in path), f"seed {s}: negative self time"
        ids_on = [x.span_id for x, _ in path]
        assert len(ids_on) == len(set(ids_on)), "a span appears once on the path"

    # head sampling
    rng = random.Random(1)
    tids = [f"{rng.getrandbits(128):032x}" for _ in range(20000)]
    t0 = tids[0]
    assert mod.head_keep(t0, 0.5) == mod.head_keep(t0, 0.5), "deterministic"
    assert not any(mod.head_keep(t, 0.0) for t in tids[:500]) and all(mod.head_keep(t, 1.0) for t in tids[:500])
    k05 = {t for t in tids if mod.head_keep(t, 0.05)}
    k10 = {t for t in tids if mod.head_keep(t, 0.10)}
    assert k05 <= k10, "raising the rate only ADDS traces (monotone)"
    assert abs(len(k05) - 1000) < 4 * math.sqrt(20000 * 0.05 * 0.95), f"rate 0.05 of 20,000 ids should keep about 1,000; kept {len(k05)}"
    # the decision depends on the id alone, so every service agrees
    assert mod.head_keep("0" * 16 + "0" * 15 + "1", 0.01) and not mod.head_keep("f" * 32, 0.99)

    # tail decisions
    def trace(dur, status="ok", tid=None):
        tid = tid or "9" * 32
        return [mod.Span(tid, "1" * 16, None, "a", "root", 0, dur), mod.Span(tid, "2" * 16, "1" * 16, "b", "child", 1, dur - 1, status=status)]
    low = "0" * 32                       # head_keep(low, r) is true for every r > 0
    high = "f" * 32                      # and false for every r < 1
    assert mod.tail_decision(trace(50, "error", high), 1000, 0.0) == "error", "any error span keeps the trace"
    assert mod.tail_decision(trace(5000, "error", high), 1000, 0.0) == "error", "error beats slow"
    assert mod.tail_decision(trace(1001, "ok", high), 1000, 0.0) == "slow"
    assert mod.tail_decision(trace(1000, "ok", high), 1000, 0.0) is None, "exactly at the threshold is not slow"
    assert mod.tail_decision(trace(50, "ok", low), 1000, 0.01) == "baseline"
    assert mod.tail_decision(trace(50, "ok", high), 1000, 0.5) is None
    assert mod.tail_decision(trace(5000, "ok", low), 1000, 1.0) == "slow", "slow beats baseline"
    assert near(mod.baseline_rate(1000, 20000, 500), 500 / 19500)
    assert mod.baseline_rate(1000, 20000, 1500) == 0.0 and mod.baseline_rate(10**9, 100, 10) == 1.0 and mod.baseline_rate(5, 10, 10) == 0.0

    # the comparison: the same storage budget, two ways to spend it
    lines = []
    for s in seeds((1, 2, 3)):
        wl = mod.make_workload(s, 20000)
        n = len(wl.traces)
        budget = n // 20
        interesting = sum(1 for k in wl.kinds if k != "ok")
        by_kind = {k: sum(1 for x in wl.kinds if x == k) for k in ("error", "slow", "ok")}
        head = {i for i, spans in enumerate(wl.traces) if mod.head_keep(spans[0].trace_id, budget / n)}
        rate = mod.baseline_rate(budget, n, interesting)
        ts = mod.TailSampler(wait_ms=10_000, slow_ms=1000, rate=rate)
        events = sorted(((x.end + 30, x) for spans in wl.traces for x in spans), key=lambda e: e[0])
        tick = 1000.0
        for at, x in events:
            while tick <= at:
                ts.flush(tick)
                tick += 1000.0
            ts.add(x, at)
        ts.flush(float("inf"))
        index = {spans[0].trace_id: i for i, spans in enumerate(wl.traces)}
        tail = {index[t] for t in ts.kept}
        assert len(ts.kept) + len(ts.dropped) == n and not ts.buf, "every trace must be decided"
        for name, kept in (("head", head), ("tail", tail)):
            assert 0.9 * budget <= len(kept) <= 1.1 * budget, f"seed {s}: {name} sampling stored {len(kept)} traces, budget {budget}: the comparison must use the same budget"
        rec = lambda kept, kind: sum(1 for i in kept if wl.kinds[i] == kind) / by_kind[kind]
        assert rec(tail, "error") == 1.0 and rec(tail, "slow") == 1.0, (
            f"seed {s}: tail sampling must keep every error and every slow trace; kept {rec(tail, 'error'):.2f} / {rec(tail, 'slow'):.2f}")
        assert rec(head, "error") < 0.2, f"seed {s}: head sampling at 5% should keep only a few errors; kept {rec(head, 'error'):.2f}"
        base_ok = sum(1 for i in tail if wl.kinds[i] == "ok") / by_kind["ok"]
        assert abs(base_ok - rate) < 0.012, f"seed {s}: ordinary traces should be kept at about the baseline rate {rate:.3f}, got {base_ok:.3f}"
        # the price: buffered traces ~ arrival rate x wait (Little's law)
        little = wl.rps * 10.0
        assert 0.9 * little <= ts.peak_traces <= 2.0 * little, f"seed {s}: buffered traces peaked at {ts.peak_traces}; Little's law predicts about {little:.0f}"
        if s == seeds((1,))[0]:
            lines.append(f"seed {s}: {n:,} traces ({by_kind['error']} errors, {by_kind['slow']} slow), budget {budget}")
            lines.append(f"  head 5%   stored {len(head):4d}: errors kept {100 * rec(head, 'error'):5.1f}%  slow kept {100 * rec(head, 'slow'):5.1f}%  ordinary kept {100 * sum(1 for i in head if wl.kinds[i] == 'ok') / by_kind['ok']:4.1f}%")
            lines.append(f"  tail      stored {len(tail):4d}: errors kept {100 * rec(tail, 'error'):5.1f}%  slow kept {100 * rec(tail, 'slow'):5.1f}%  ordinary kept {100 * base_ok:4.1f}%   "
                         f"(buffered at peak: {ts.peak_traces} traces, {ts.peak_spans} spans)")
    return "\n".join(lines)


MILESTONES = [
    (1, "Milestone 1: ids and parent/child spans on simulated time", m1),
    (2, "Milestone 2: W3C traceparent across simulated services", m2),
    (3, "Milestone 3: async propagation through a queue, with links", m3),
    (4, "Milestone 4: trace trees from out-of-order spans, with missing parents", m4),
    (5, "Milestone 5: critical path, head vs tail sampling", m5),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 3 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
