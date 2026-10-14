"""Self-check for Lab 7: Traces & a Regression Gate.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 1 7     # milestone 1, replaying ONLY the random trials of seed 7

Everything is synthetic and seeded: the support bot (bot.py), its clock, the 120 regression cases
(suite.jsonl), the ten production traces (prod_traces.jsonl) and the bootstrap resamples. There is no
network and no real model, so every run gives identical numbers and finishes in a couple of seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import copy
import hashlib
import importlib
import json
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
import bot as B  # noqa: E402
from llm import ScriptedModel  # noqa: E402

results = []
SUITE = mod.load_suite()
PROD = mod.load_prod_traces()
FX = {B.fixture_key("lookup_order", {"order_id": "A-1042"}): {"total": 80.0, "status": "lost"}}
FLAKY_KEY = "t-41"        # a request id whose lookup times out (found by search; the luck is seeded)
EMAIL_RAW = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CARD_RAW = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
PHONE_RAW = re.compile(r"\b0\d{3,4} ?\d{3} ?\d{3,4}\b")


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}".rstrip())
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:  # a crash in the learner's code is a failure with a pointer, not a traceback
        print(f"  ✘ {name}: crashed with {type(e).__name__}: {e}")
        results.append(False)


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception:
        return False
    return False


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


def span(id, parent, name, start, end, status="OK", **attrs):
    return {"trace_id": "x", "id": id, "parent": parent, "name": name, "kind": "INTERNAL",
            "start": float(start), "end": float(end), "status": status, "attrs": attrs}


# ----------------------------------------------------------------------------- milestone 1

def build_random_tree(seed):
    """Open random nested spans; return the tracer and the (name, parent name) pairs we expect."""
    rng = random.Random(seed)
    clock = B.Clock(100.0)
    tr = mod.Tracer(clock, f"r{seed}")
    expected = []

    def grow(depth, parent_name):
        for i in range(rng.randint(1, 3)):
            name = f"{parent_name}.{i}"
            expected.append((name, parent_name))
            with tr.span(name):
                clock.advance(rng.randint(1, 20))
                if depth < 3 and rng.random() < 0.6:
                    grow(depth + 1, name)
                clock.advance(rng.randint(0, 20))

    with tr.span("root"):
        grow(0, "root")
    return tr, expected


def m1():
    clock = B.Clock()
    tr = mod.Tracer(clock, "tx")
    with tr.span("root", a=1) as r:
        clock.advance(10)
        with tr.span("child1", "CLIENT", model="m") as c:
            clock.advance(30)
            c["attrs"]["n"] = 5
        clock.advance(5)
        with tr.span("child2"):
            clock.advance(20)
        clock.advance(5)
    s = tr.spans
    assert [x["name"] for x in s] == ["root", "child1", "child2"], f"spans are listed in the order they started; got {[x['name'] for x in s]}"
    assert [x["id"] for x in s] == ["s1", "s2", "s3"], f"ids count up from s1 in order of start; got {[x['id'] for x in s]}"
    assert [x["parent"] for x in s] == [None, "s1", "s1"], f"expected parents [None, 's1', 's1']; got {[x['parent'] for x in s]}. The parent is the innermost span still open"
    assert [(x["start"], x["end"]) for x in s] == [(0, 70), (10, 40), (45, 65)], f"expected (start, end) of (0, 70), (10, 40), (45, 65) from clock.now; got {[(x['start'], x['end']) for x in s]}"
    assert [x["kind"] for x in s] == ["INTERNAL", "CLIENT", "INTERNAL"] and all(x["trace_id"] == "tx" and x["status"] == "OK" for x in s), "kind defaults to INTERNAL, trace_id comes from the tracer, status starts as OK"
    assert s[0]["attrs"] == {"a": 1} and s[1]["attrs"] == {"model": "m", "n": 5}, f"attributes passed to span() are kept, and the yielded dict lets the caller add more; got {s[0]['attrs']} and {s[1]['attrs']}"
    assert r is s[0], "the span() block must yield the very dict that is stored in tracer.spans"
    with tr.span("later"):
        pass
    assert tr.spans[3]["parent"] is None and tr.spans[3]["id"] == "s4", "after the root block ends no span is open, so the next span has no parent (pop the stack in a finally)"

    # a nested grandchild, then a sibling
    clock = B.Clock()
    tr2 = mod.Tracer(clock)
    with tr2.span("a"):
        with tr2.span("b"):
            with tr2.span("c"):
                clock.advance(1)
            with tr2.span("d"):
                clock.advance(1)
    par = {x["name"]: x["parent"] for x in tr2.spans}
    ids = {x["name"]: x["id"] for x in tr2.spans}
    assert par == {"a": None, "b": ids["a"], "c": ids["b"], "d": ids["b"]}, f"c and d are both children of b; got parents {par}"

    # errors: recorded, closed, re-raised
    clock = B.Clock()
    tr3 = mod.Tracer(clock)
    with tr3.span("outer"):
        try:
            with tr3.span("inner"):
                clock.advance(7)
                raise ValueError("boom")
        except ValueError:
            pass
        clock.advance(3)
    inner, outer = tr3.spans[1], tr3.spans[0]
    assert inner["status"] == "ERROR" and inner["attrs"].get("error.type") == "ValueError", f"a span whose block raises has status ERROR and attrs['error.type'] = the exception class name; got {inner['status']}, {inner['attrs']}"
    assert inner["end"] == 7, "the failed span still ends: its end is the clock time when the exception passed through"
    assert outer["status"] == "OK" and outer["end"] == 10, "an exception caught inside the outer block leaves the outer span OK"

    def boom():
        with mod.Tracer(B.Clock()).span("x"):
            raise KeyError("k")
    assert raises(KeyError, boom), "the exception must propagate out of the with block (re-raise it)"

    # two tracers do not share state
    t_a, t_b = mod.Tracer(B.Clock(), "a"), mod.Tracer(B.Clock(), "b")
    with t_a.span("x"):
        with t_b.span("y"):
            pass
    assert t_b.spans[0]["parent"] is None and t_b.spans[0]["id"] == "s1", "each Tracer has its own id counter and its own stack"

    for seed in seeds(range(1, 21)):
        tr_, expected = build_random_tree(seed)
        by_name = {x["name"]: x for x in tr_.spans}
        assert len(tr_.spans) == len(expected) + 1 and len({x["id"] for x in tr_.spans}) == len(tr_.spans), f"(seed {seed}) every span appears once with a unique id"
        for name, parent in expected:
            sp, pa = by_name[name], by_name[parent]
            assert sp["parent"] == pa["id"], f"(seed {seed}) span {name} should have parent {parent}"
            assert pa["start"] <= sp["start"] <= sp["end"] <= pa["end"], f"(seed {seed}) child {name} must sit inside its parent's interval"

    # self time
    sp = [span("p", None, "parent", 0, 100), span("c1", "p", "c1", 10, 40), span("c2", "p", "c2", 30, 60)]
    st = mod.self_times(sp)
    assert near(st["p"], 50) and near(st["c1"], 30) and near(st["c2"], 30), f"parent 0-100 with overlapping children 10-40 and 30-60 covers 50 ms once: expected self times p=50, c1=30, c2=30; got {st}"
    sp = [span("p", None, "parent", 0, 100), span("c1", "p", "c1", 10, 40), span("c2", "p", "c2", 50, 90), span("g", "c1", "g", 15, 20)]
    st = mod.self_times(sp)
    assert near(st["p"], 30) and near(st["c1"], 25) and near(st["c2"], 40) and near(st["g"], 5), f"sequential children subtract their durations; only DIRECT children count (a grandchild is inside its parent already): expected p=30, c1=25, c2=40, g=5; got {st}"
    sp = [span("p", None, "parent", 10, 50), span("c", "p", "c", 0, 30)]
    assert near(mod.self_times(sp)["p"], 20), "a child that starts before its parent is clipped to the parent's interval: only 10-30 is covered, so p has 20 ms of its own"
    assert mod.self_times([]) == {}, "no spans, no times"
    for t in PROD:
        st = mod.self_times(t["spans"])
        root = t["spans"][0]
        assert near(sum(st.values()), root["end"] - root["start"], 1e-6), f"trace {t['trace_id']}: the calls run one after another, so the self times of all spans add up to the root's duration; got {sum(st.values())} for {root['end'] - root['start']}"
    clock = B.Clock()
    tr4 = mod.Tracer(clock, "demo")
    with tr4.span("invoke_agent support-bot"):
        clock.advance(40)
        with tr4.span("chat demo-model", "CLIENT"):
            clock.advance(310)
        with tr4.span("execute_tool lookup_order"):
            clock.advance(95)
        with tr4.span("chat demo-model", "CLIENT"):
            clock.advance(420)
    return "a tiny hand-made trace, drawn by the given waterfall():\n" + mod.waterfall(tr4.spans, 36)


# ----------------------------------------------------------------------------- milestone 2

SAMPLES = [
    ("Mail me at jo@example.com please", "Mail me at <EMAIL> please"),
    ("two: a.b+c@x-y.co.uk and d@e.fr", "two: <EMAIL> and <EMAIL>"),
    ("card 4929 1234 5678 9010 thanks", "card <CARD> thanks"),
    ("card 4929-1234-5678-9010.", "card <CARD>."),
    ("card 4929123456789010", "card <CARD>"),
    ("ring 07123 456 789 now", "ring <PHONE> now"),
    ("Refund A-1042 for 80.00 on 3 October at 14:05", "Refund A-1042 for 80.00 on 3 October at 14:05"),
    ("", ""),
]


def tool_span_attrs(tr, name):
    return [s for s in tr.spans if s["name"] == f"execute_tool {name}"]


def m2():
    for raw, want in SAMPLES:
        got = mod.redact(raw)
        assert got == want, f"redact({raw!r}) should give {want!r}; got {got!r}"
        assert mod.redact(got) == got, f"redact must be idempotent (redact of {got!r} changed it to {mod.redact(got)!r}): a mask must not match a pattern"
    rng = random.Random(0)
    words = "please refund my order thanks where is parcel hello again".split()
    pii = [lambda: "jo%d@example.com" % rng.randint(1, 99), lambda: " ".join(str(rng.randint(1000, 9999)) for _ in range(4)),
           lambda: "07%d %d %d" % (rng.randint(100, 999), rng.randint(100, 999), rng.randint(100, 999))]
    for _ in range(100):
        parts = [rng.choice(words) for _ in range(5)]
        parts.insert(rng.randint(0, 5), rng.choice(pii)())
        out = mod.redact(" ".join(parts))
        assert not (EMAIL_RAW.search(out) or CARD_RAW.search(out) or PHONE_RAW.search(out)), f"a raw identifier survived: {out!r}"
        assert [w for w in out.split() if w in words] == [w for w in parts if w in words], "ordinary words must be left alone"

    # TracedModel
    clock = B.Clock()
    tr = mod.Tracer(clock, "m")
    inner = B.TimedModel(ScriptedModel(["Hello there."]), clock, name="demo-model")
    tm = mod.TracedModel(tr, inner)
    reply = tm.complete([{"role": "user", "content": "hi, I am jo@example.com"}], system="be nice")
    assert reply.content[0]["text"] == "Hello there.", "the wrapper must return the inner model's reply unchanged"
    s = tr.spans[0]
    want = {"gen_ai.operation.name": "chat", "gen_ai.provider.name": "demo", "gen_ai.request.model": "demo-model",
            "gen_ai.usage.input_tokens": reply.usage["input_tokens"], "gen_ai.usage.output_tokens": reply.usage["output_tokens"],
            "gen_ai.response.finish_reasons": ["end_turn"]}
    assert s["name"] == "chat demo-model" and s["kind"] == "CLIENT", f"span name is 'chat <model>' and kind CLIENT; got {s['name']!r}, {s['kind']!r}"
    assert s["attrs"] == want, f"expected attributes {want}; got {s['attrs']}"
    assert s["end"] - s["start"] == clock.now and clock.now > 0, "the span must cover the inner call, which advances the clock"
    assert "jo@example.com" not in json.dumps(tr.spans), "model messages are content: the chat span must not store them"

    class Broken:
        name = "broken-model"

        def complete(self, messages, **kw):
            raise RuntimeError("503")
    tr_b = mod.Tracer(B.Clock())
    assert raises(RuntimeError, mod.TracedModel(tr_b, Broken()).complete, []), "an exception from the model must propagate"
    assert tr_b.spans[0]["status"] == "ERROR" and tr_b.spans[0]["attrs"]["error.type"] == "RuntimeError", "and the chat span must be recorded as an ERROR"

    # trace_tools
    clock = B.Clock()
    tr = mod.Tracer(clock)

    def lookup(order_id):
        clock.advance(25)
        return {"status": "lost", "contact": "jo@example.com"}

    def fail(order_id):
        raise B.ToolError("upstream timeout")
    tools = mod.trace_tools(tr, {"lookup_order": lookup, "other": fail}, capture=True)
    assert set(tools) == {"lookup_order", "other"}, "same tool names in, same tool names out"
    out = tools["lookup_order"](order_id="A-1")
    assert out == {"status": "lost", "contact": "jo@example.com"}, "the traced tool returns the real result unchanged"
    a = tr.spans[0]
    assert a["name"] == "execute_tool lookup_order" and a["kind"] == "INTERNAL" and a["end"] - a["start"] == 25, "span 'execute_tool <name>', INTERNAL, covering the call"
    assert a["attrs"]["gen_ai.operation.name"] == "execute_tool" and a["attrs"]["gen_ai.tool.name"] == "lookup_order", f"missing operation or tool name attributes: {a['attrs']}"
    assert a["attrs"].get("gen_ai.tool.call.arguments") == '{"order_id": "A-1"}', f"arguments are json.dumps(kwargs, sort_keys=True); got {a['attrs'].get('gen_ai.tool.call.arguments')!r}"
    assert a["attrs"].get("gen_ai.tool.call.result") == '{"contact": "<EMAIL>", "status": "lost"}', f"the result is stored as redact(json.dumps(result, sort_keys=True)); got {a['attrs'].get('gen_ai.tool.call.result')!r}"
    assert raises(B.ToolError, tools["other"], order_id="A-2"), "tool errors propagate to the agent loop"
    e = tr.spans[1]
    assert e["status"] == "ERROR" and e["attrs"]["error.type"] == "ToolError" and "gen_ai.tool.call.result" not in e["attrs"], "a failed tool call is an ERROR span with no result"
    tr_n = mod.Tracer(B.Clock())
    mod.trace_tools(tr_n, {"lookup_order": lookup}, capture=False)["lookup_order"](order_id="A-1")
    assert set(tr_n.spans[0]["attrs"]) == {"gen_ai.operation.name", "gen_ai.tool.name"}, f"with capture=False store no arguments and no result; got {sorted(tr_n.spans[0]['attrs'])}"

    # a whole request
    def traced(version, text, key, release="v1", capture=True):
        clock = B.Clock()
        rig = B.build(version, text, FX, key=key, trial=0, clock=clock)
        tr = mod.Tracer(clock, key)
        ans = mod.trace_request(tr, rig, text, release=release, conversation_id="conv-7", capture=capture)
        return tr, ans, clock

    text = "Refund my order A-1042, my email is jo@example.com"
    tr, ans, clock = traced("v1", text, "t-1")
    names = [s["name"] for s in tr.spans]
    assert names == ["invoke_agent support-bot", "chat demo-model", "execute_tool lookup_order", "chat demo-model",
                     "execute_tool escalate_to_human", "chat demo-model"], f"expected one root, then chat, lookup, chat, escalate, chat in order; got {names}"
    assert [s["parent"] for s in tr.spans] == [None] + ["s1"] * 5, "every model and tool span is a direct child of the root"
    root = tr.spans[0]
    assert root["start"] == 0 and root["end"] == clock.now, "the root covers the whole request, from the first model call to the last"
    assert root["kind"] == "INTERNAL" and root["status"] == "OK", "root: INTERNAL, OK"
    for k, v in {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "support-bot", "gen_ai.conversation.id": "conv-7", "app.release": "v1"}.items():
        assert root["attrs"].get(k) == v, f"root attribute {k} should be {v!r}; got {root['attrs'].get(k)!r}"
    assert json.loads(root["attrs"]["gen_ai.input.messages"]) == [{"role": "user", "content": "Refund my order A-1042, my email is <EMAIL>"}], f"input messages are stored redacted; got {root['attrs'].get('gen_ai.input.messages')!r}"
    assert json.loads(root["attrs"]["gen_ai.output.messages"])[0]["content"] == ans, "the output message is the answer"
    assert "jo@example.com" not in json.dumps(tr.spans), "the raw email must not appear anywhere in the trace"
    rig = B.build("v1", text, FX, key="t-1", trial=0)
    plain, _ = B.run_agent(text, rig.model, rig.tools)
    assert ans == plain and rig.clock.now == clock.now, "tracing must not change behaviour or timing: same answer and the same final clock as the untraced run"
    tr, ans, clock = traced("v1", text, "t-1", capture=False)
    assert "gen_ai.input.messages" not in tr.spans[0]["attrs"] and all("gen_ai.tool.call.arguments" not in s["attrs"] for s in tr.spans), "capture=False records metadata only"

    tr, ans, clock = traced("v1", "Where is my order A-1042?", FLAKY_KEY)
    bad = [s for s in tr.spans if s["status"] == "ERROR"]
    assert [s["name"] for s in bad] == ["execute_tool lookup_order"] and bad[0]["attrs"]["error.type"] == "ToolError", f"the timed-out lookup is the only ERROR span; got {[s['name'] for s in bad]}"
    assert bad[0]["end"] - bad[0]["start"] >= 1200 and tr.spans[0]["status"] == "OK", "the failed call took 1200 ms before failing, and the request itself still answered (the agent loop handled the error)"
    return "a refund request over the limit, traced (given waterfall):\n" + mod.waterfall(traced("v1", text, "t-1")[0].spans)


# ----------------------------------------------------------------------------- milestone 3

def hand_trace():
    return [span("s1", None, "invoke_agent support-bot", 0, 1195, **{"gen_ai.operation.name": "invoke_agent", "app.release": "v2", "gen_ai.usage.input_tokens": 9999}),
            span("s2", "s1", "chat demo-model", 0, 620, **{"gen_ai.operation.name": "chat", "gen_ai.usage.input_tokens": 36, "gen_ai.usage.output_tokens": 6}),
            span("s3", "s1", "execute_tool lookup_order", 620, 715, **{"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "lookup_order"}),
            span("s4", "s1", "execute_tool issue_refund", 715, 755, "ERROR", **{"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "issue_refund"}),
            span("s5", "s1", "chat demo-model", 755, 1195, **{"gen_ai.operation.name": "chat", "gen_ai.usage.input_tokens": 48, "gen_ai.usage.output_tokens": 14})]


def m3():
    r = mod.rollup(hand_trace())
    assert r["release"] == "v2" and r["duration_ms"] == 1195, f"release comes from the root's app.release and the duration is the root's end minus start; got {r['release']!r}, {r['duration_ms']}"
    assert (r["input_tokens"], r["output_tokens"]) == (84, 20), f"tokens are summed over the chat spans only (36 + 48 in, 6 + 14 out); a root with its own usage attribute must not be added; got {r['input_tokens']}, {r['output_tokens']}"
    assert near(r["cost"], (84 * 3 + 20 * 15) / 1e6), f"cost = (84 x 3 + 20 x 15) / 1e6 = 0.000552 dollars; got {r['cost']}"
    assert r["model_ms"] == 1060 and r["tool_ms"] == 135, f"model_ms = 620 + 440 and tool_ms = 95 + 40; got {r['model_ms']}, {r['tool_ms']}"
    assert near(r["model_share"], 1060 / 1195) and r["n_model_calls"] == 2, f"model_share = 1060 / 1195 and two model calls; got {r['model_share']}, {r['n_model_calls']}"
    assert r["tools"] == ["lookup_order", "issue_refund"] and r["errors"] == ["execute_tool issue_refund"], f"tools in order of start and the names of ERROR spans; got {r['tools']}, {r['errors']}"
    z = mod.rollup([span("s1", None, "invoke_agent support-bot", 5, 5, **{"gen_ai.operation.name": "invoke_agent"})])
    assert z["duration_ms"] == 0 and z["model_share"] == 0.0 and z["release"] is None and z["tools"] == [] and z["errors"] == [] and z["cost"] == 0, f"an empty trace: zero duration, zero share, no release, no tools, no errors; got {z}"
    for t in PROD:
        r = mod.rollup(t["spans"])
        chats = [s for s in t["spans"] if s["name"].startswith("chat ")]
        assert r["input_tokens"] == sum(s["attrs"]["gen_ai.usage.input_tokens"] for s in chats), f"{t['trace_id']}: input tokens are the sum over chat spans"

    # keep_trace
    quiet = {"errors": [], "duration_ms": 900}
    assert mod.keep_trace({"errors": ["execute_tool lookup_order"], "duration_ms": 900}, "a", feedback="down") == (True, "error"), "an error is kept, and 'error' is reported before 'feedback'"
    assert mod.keep_trace(quiet, "a", feedback="down") == (True, "feedback"), "thumbs-down is kept"
    assert mod.keep_trace(quiet, "a", feedback="up", base_rate=0) == (False, "drop"), "thumbs-up is not a reason to keep"
    assert mod.keep_trace({"errors": [], "duration_ms": 2500}, "a", base_rate=0) == (True, "slow"), "slower than slow_ms is kept"
    assert mod.keep_trace({"errors": [], "duration_ms": 2000}, "a", base_rate=0) == (False, "drop"), "exactly slow_ms is not slow (strictly greater)"
    assert mod.keep_trace({"errors": [], "duration_ms": 2500}, "a", slow_ms=3000, base_rate=0) == (False, "drop"), "slow_ms is a parameter"
    assert mod.keep_trace(quiet, "anything", base_rate=1.0) == (True, "baseline") and mod.keep_trace(quiet, "anything", base_rate=0.0) == (False, "drop"), "base_rate 1 keeps every quiet trace, base_rate 0 none"

    def h(tid):
        return int(hashlib.sha256(tid.encode()).hexdigest()[:8], 16) / 2 ** 32
    ids = [f"t-{i}" for i in range(6000)]
    for tid in ids[:300]:
        assert mod.keep_trace(quiet, tid, base_rate=0.05)[0] == (h(tid) < 0.05), f"baseline for {tid} should be int(sha256(trace_id)[:8], 16) / 2**32 < base_rate"
    kept = sum(mod.keep_trace(quiet, tid, base_rate=0.05)[0] for tid in ids)
    assert 0.04 < kept / len(ids) < 0.06, f"a 5% baseline should keep about 5% of quiet traces; kept {kept / len(ids):.1%}"
    assert all(mod.keep_trace(quiet, tid, base_rate=0.05) == mod.keep_trace(quiet, tid, base_rate=0.05) for tid in ids[:50]), "the same trace id must always get the same decision (hash it, do not call random)"

    lines = []
    for seed in seeds([17]):
        rng = random.Random(seed)
        N = 20000
        day = []
        for i in range(N):
            err = rng.random() < 0.015
            slow = rng.random() < 0.02
            down = rng.random() < 0.004
            day.append(({"errors": ["execute_tool lookup_order"] if err else [], "duration_ms": 3500 if slow else 1000 + rng.randint(0, 600)},
                        "down" if down else None, f"d{seed}-{i}", err or slow or down))
        interesting = sum(x[3] for x in day)
        tail = [mod.keep_trace(r, tid, fb, base_rate=0.02) for r, fb, tid, _ in day]
        stored = sum(k for k, _ in tail)
        got = sum(k for (k, _), x in zip(tail, day) if x[3])
        assert got == interesting, f"(seed {seed}) tail sampling must keep every error, slow or thumbs-down trace: kept {got} of {interesting}"
        head = sum(h(tid) < stored / N for _, _, tid, _ in day)
        head_got = sum(h(tid) < stored / N for _, _, tid, bad in day if bad)
        lines.append(f"a day of {N} traces, {interesting} of them worth reading; both policies store {stored / N:.1%}:")
        lines.append(f"  tail rules + 2% baseline keep {got / interesting:.0%} of the worth-reading traces; random head sampling keeps {head_got / interesting:.0%}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- milestone 4

def case(input, mode="refund_over_limit", id="x"):
    return {"id": id, "input": input, "mode": mode}


def all_cases():
    out = []
    for t in PROD:
        try:
            out.append(mod.trace_to_case(t["spans"], t["label"]))
        except ValueError:
            pass
    return out


def m4():
    fp = mod.fingerprint
    a = fp(case("Refund my order A-1042, my email is <EMAIL>"))
    assert isinstance(a, str) and re.fullmatch(r"[0-9a-f]{8}", a), f"a fingerprint is 8 hex characters; got {a!r}"
    assert a == fp(case("refund my order A-2231, my email is <EMAIL>")), "the same words with a different order id and different case must collide"
    assert a == fp(case("Refund my order A-77, my email is <EMAIL>")) and a == fp(case("Refund my order A-1042,   my email is  <CARD>")), "ids, digits, placeholders and runs of spaces are normalised away"
    assert a != fp(case("Refund my order A-1042, my email is <EMAIL>", mode="echoed_pii")), "the mode is part of the fingerprint"
    assert a != fp(case("Refund my order A-1042, ring me please")), "different words give a different fingerprint"
    assert fp(case("Total 80 pounds")) == fp(case("Total 9 pounds")), "any run of digits becomes #"

    t0 = PROD[0]
    c = mod.trace_to_case(t0["spans"], t0["label"])
    want_id = "prod-" + hashlib.sha256(t0["trace_id"].encode()).hexdigest()[:6]
    assert c["id"] == want_id, f"id should be 'prod-' plus 6 hex of sha256(trace_id); expected {want_id}, got {c['id']}"
    assert c["input"] == "Refund my order A-4417, my email is <EMAIL> and card <CARD>", f"input should be the redacted user message; got {c['input']!r}"
    assert c["fixtures"] == {'lookup_order:{"order_id": "A-4417"}': {"total": 80.0, "status": "delivered"}}, f"fixtures hold the lookup result under bot.fixture_key and nothing else (the refund the bot made is the thing to re-test, not to replay); got {c['fixtures']}"
    assert c["mode"] == "refund_over_limit" and c["slice"] == "refunds (critical)" and c["source"] == "trace:" + t0["trace_id"], f"mode, slice and source: got {c['mode']}, {c['slice']}, {c['source']}"
    assert c["assert"] == mod.ASSERTIONS["refund_over_limit"] and c["note"] == t0["label"]["note"], "assertions come from the mode, and the labeller's note is kept"
    c["assert"][0]["limit"] = 999
    assert mod.ASSERTIONS["refund_over_limit"][0]["limit"] == 50, "assert must be a deep copy: editing a case must not edit the shared table"

    built = all_cases()
    assert len(built) == 9, f"nine of the ten traces can be turned into cases (one has no successful lookup); got {len(built)}"
    blob = json.dumps(built)
    assert not (EMAIL_RAW.search(blob) or CARD_RAW.search(blob) or PHONE_RAW.search(blob)), "no raw email, card or phone may remain in any case: redact the input again, because older traces were captured before redaction was on"
    legacy = [t for t in PROD if PHONE_RAW.search(t["spans"][0]["attrs"].get("gen_ai.input.messages", ""))]
    assert legacy, "(check.py) the data should contain a trace captured without redaction"
    flaky = [t for t in PROD if any(s["status"] == "ERROR" for s in t["spans"])]
    assert flaky and raises(ValueError, mod.trace_to_case, flaky[0]["spans"], flaky[0]["label"]), "a trace whose only lookup failed has nothing to replay: raise ValueError"
    for c in built:
        assert B.run_case("v1", c, 0)["calls"][0]["result"] is not None, f"case {c['id']} does not replay: the recorded lookup was not found under fixture_key"

    suite = mod.load_suite()
    kept, skipped = mod.dedupe(suite, built)
    assert [k["id"] for k in kept] == ["prod-c85447", "prod-18d2f0", "prod-af671c", "prod-e8f2b6", "prod-55605d", "prod-5bd470"], f"expected six new cases, in input order; got {[k['id'] for k in kept]}"
    assert skipped == [("prod-e6cb5a", "R09"), ("prod-3d3922", "prod-c85447"), ("prod-ed8b04", "G76")], f"expected duplicates of a suite case, of an earlier new case and of a suite case; got {skipped}"
    assert all(k["fp"] == fp(k) for k in kept), "every kept case carries its fingerprint under 'fp'"
    assert "fp" not in built[0], "dedupe must not modify the cases it is given"
    assert mod.dedupe([], []) == ([], []) and mod.dedupe(suite, suite[:3])[0] == [], "nothing new, nothing kept"
    k2, s2 = mod.dedupe([], [case("Refund A-1", id="n1"), case("refund a-2", id="n2"), case("Refund A-3 now", id="n3")])
    assert [k["id"] for k in k2] == ["n1", "n3"] and s2 == [("n2", "n1")], f"with no existing cases the first of a pair is kept; got {[k['id'] for k in k2]}, {s2}"
    return (f"{len(PROD)} labelled production traces -> {len(built)} buildable -> {len(kept)} new cases, {len(skipped)} duplicates:\n"
            + "\n".join(f"  kept     {k['id']}  {k['slice']:<19} {k['input']}" for k in kept)
            + "\n" + "\n".join(f"  skipped  {a} duplicates {b}" for a, b in skipped))


# ----------------------------------------------------------------------------- milestone 5

def res(answer="ok", *calls):
    return {"answer": answer, "calls": list(calls)}


def lk(total=80.0, status="delivered"):
    return {"name": "lookup_order", "args": {"order_id": "A-1"}, "result": {"total": total, "status": status}, "error": None}


def lk_err():
    return {"name": "lookup_order", "args": {"order_id": "A-1"}, "result": None, "error": "upstream timeout"}


def call(name):
    return {"name": name, "args": {}, "result": {"ok": True}, "error": None}


def m5():
    ca = mod.check_assertion
    over = {"type": "tool_not_called_or_escalated", "tool": "issue_refund", "limit": 50}
    assert ca(over, res("x", lk(80), call("escalate_to_human")))[0], "an over-limit order that was escalated, not refunded, is fine"
    ok, why = ca(over, res("x", lk(80), call("issue_refund")))
    assert not ok and why, "an over-limit order that was refunded fails, with a reason"
    assert ca(over, res("x", lk(50), call("issue_refund")))[0] and ca(over, res("x", lk(30), call("issue_refund")))[0], "a total at or below the limit may be refunded (50 is allowed)"
    assert not ca(over, res("x", lk(50.01), call("issue_refund")))[0], "50.01 is over the limit"
    assert not ca(over, res("x", call("issue_refund")))[0] and not ca(over, res("x", lk_err(), call("issue_refund")))[0], "a refund with no successful lookup is not shown to be within the limit: fail"
    assert ca(over, res("sorry", lk_err()))[0], "no refund, nothing to complain about"
    called = {"type": "tool_called", "tool": "issue_refund"}
    assert ca(called, res("x", lk(30), call("issue_refund")))[0] and not ca(called, res("x", lk(30)))[0], "tool_called: the call must exist"
    assert not ca(called, res("x", {"name": "issue_refund", "args": {}, "result": None, "error": "denied"}))[0], "a call that errored does not count"
    cons = {"type": "answer_consistent_with_tool", "tool": "lookup_order", "field": "status"}
    assert ca(cons, res("Order A-1 appears to be LOST, sorry.", lk(status="lost")))[0], "the answer must contain the status word, ignoring case"
    assert not ca(cons, res("Good news: it should arrive tomorrow.", lk(status="lost")))[0], "an answer that never says 'lost' contradicts the tool"
    assert ca(cons, res("It is on its way.", lk(status="shipped")))[0] and ca(cons, res("being prepared", lk(status="processing")))[0], "each status has its word in bot.STATUS_WORDS"
    assert ca(cons, res("Order A-1 has been delivered.", lk(status="lost"), lk(status="delivered")))[0], "use the LAST successful lookup"
    ok, why = ca(cons, res("Sorry, I could not look that up.", lk_err()))
    assert not ok and why, "no successful lookup: the answer cannot be checked, so fail"
    omit = {"type": "answer_omits_placeholders"}
    assert ca(omit, res("Thanks, I have updated the details."))[0], "no identifier repeated"
    for bad in ("I have noted <CARD> for you.", "Call <PHONE>", "Noted jo@example.com", "card 4111 1111 1111 1111"):
        assert not ca(omit, res(bad))[0], f"{bad!r} repeats an identifier or its placeholder"
    assert raises(ValueError, ca, {"type": "answer_is_polite"}, res("x")), "an unknown assertion type must raise ValueError: a typo should never become a silent pass"

    c = {"id": "c1", "assert": [over, cons]}
    g = mod.grade_case(c, res("Good news: it arrives tomorrow.", lk(80, "lost"), call("issue_refund")))
    assert g["ok"] is False and len(g["failed"]) == 2, f"both assertions fail and both reasons are listed (do not stop at the first); got {g}"
    g = mod.grade_case(c, res("It is lost, sorry.", lk(30, "lost"), call("issue_refund")))
    assert g == {"ok": True, "failed": []}, f"both hold: expected ok with no reasons; got {g}"
    g = mod.grade_case(c, res("It arrives tomorrow.", lk(30, "lost")))
    assert g["ok"] is False and len(g["failed"]) == 1, "one failing assertion is enough to fail the case"
    assert raises(ValueError, mod.grade_case, {"id": "c2", "assert": []}, res("x")), "a case with no assertions raises ValueError"
    snap = copy.deepcopy(c)
    mod.grade_case(c, res("It is lost.", lk(30, "lost")))
    assert c == snap, "grading must not modify the case"

    # run_suite against a scripted runner, independent of the bot
    seen = []

    def fake(version, case, trial):
        seen.append((version, case["id"], trial))
        good = (case["id"], trial) not in {("b", 2), ("c", 0), ("c", 1), ("c", 2)}
        return res("x", lk(30), call("issue_refund")) if good else res("x", lk(30))
    real = mod.run_case, B.run_case
    mod.run_case = B.run_case = fake
    try:
        cs = [{"id": i, "assert": [called]} for i in "abc"]
        out = mod.run_suite(cs, "vX", 3)
        assert out == {"a": 3, "b": 2, "c": 0}, f"expected passes {{'a': 3, 'b': 2, 'c': 0}} out of 3; got {out}"
        assert sorted(seen) == sorted((v, i, t) for v in ("vX",) for i in "abc" for t in range(3)), f"each case is run once per trial 0, 1, 2 with the given version; runs were {sorted(seen)}"
        assert mod.run_suite(cs, "vX", 1) == {"a": 1, "b": 1, "c": 0} and list(mod.run_suite(cs, "vX", 2)) == ["a", "b", "c"], "k=1 uses only trial 0, and the result keeps the order of the cases"
    finally:
        mod.run_case, B.run_case = real

    for seed in seeds([1, 2, 3]):
        rng = random.Random(seed)
        sub = rng.sample(SUITE, 30)
        for v in ("v1", "v2"):
            c3, c2 = mod.run_suite(sub, v, 3), mod.run_suite(sub, v, 2)
            assert set(c3) == {x["id"] for x in sub} and all(0 <= n <= 3 for n in c3.values()), f"(seed {seed}) one count between 0 and 3 per case"
            assert all(0 <= c3[i] - c2[i] <= 1 for i in c3), f"(seed {seed}) running a third trial adds at most one pass; trials must be 0, 1, 2 and the same each time"
    c1 = mod.run_suite(SUITE, "v1", 3)
    c2 = mod.run_suite(SUITE, "v2", 3)
    lines = ["pass rate by slice (3 trials per case), v1 in production against candidate v2:"]
    for name in dict.fromkeys(x["slice"] for x in SUITE):
        ids = [x["id"] for x in SUITE if x["slice"] == name]
        r1, r2 = sum(c1[i] for i in ids) / 3 / len(ids), sum(c2[i] for i in ids) / 3 / len(ids)
        lines.append(f"  {name:<20} v1 {r1:.2f}   v2 {r2:.2f}")
    r = {s: [x["id"] for x in SUITE if x["slice"] == s] for s in ("general", "refunds (critical)")}
    assert sum(c2[i] for i in r["general"]) > sum(c1[i] for i in r["general"]) and sum(c2[i] for i in r["refunds (critical)"]) < sum(c1[i] for i in r["refunds (critical)"]), \
        "v2 should be better on general cases (it stopped ignoring tool results) and worse on refunds (it stopped escalating): if not, a grader is wrong"
    return "\n".join(lines)


# ----------------------------------------------------------------------------- milestone 6

def oracle_ci(diffs, B_, alpha, seed):
    rng = random.Random(seed)
    n = len(diffs)
    xs = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(B_))
    return xs[int(alpha / 2 * B_)], xs[int((1 - alpha / 2) * B_) - 1]


def tiny(base_counts, cand_counts, slices):
    cases = [{"id": f"c{i}", "slice": s} for i, s in enumerate(slices)]
    return cases, {f"c{i}": b for i, b in enumerate(base_counts)}, {f"c{i}": c for i, c in enumerate(cand_counts)}


def m6():
    d = [0.0, 1 / 3, -1 / 3, 2 / 3, 0.0, 1 / 3, 1.0, -2 / 3]
    for B_, alpha, seed in [(500, 0.05, 1), (300, 0.1, 5), (1000, 0.05, 0)]:
        lo, hi = mod.paired_ci(d, B=B_, alpha=alpha, seed=seed)
        olo, ohi = oracle_ci(d, B_, alpha, seed)
        assert near(lo, olo) and near(hi, ohi), f"expected ({olo:.4f}, {ohi:.4f}) for B={B_}, alpha={alpha}, seed={seed}: resample len(diffs) indices with random.Random(seed).randrange, take B means, sort; got ({lo:.4f}, {hi:.4f})"
    assert mod.paired_ci(d, 200, 0.05, 3) == mod.paired_ci(d, 200, 0.05, 3), "same seed, same interval"
    assert mod.paired_ci([0.0] * 12, 100) == (0.0, 0.0), "no differences, no uncertainty"
    assert mod.paired_ci([0.5], 100) == (0.5, 0.5), "a single case resamples to itself"
    lo, hi = mod.paired_ci([1.0, -1.0], 500, 0.05, 1)
    assert lo == -1.0 and hi == 1.0, "two cases, one up one down: the resampled mean can be -1, 0 or 1, so the interval spans (-1, 1)"

    cases, base, cand = tiny([3, 3, 3, 2, 1, 3], [0, 3, 1, 2, 3, 3], ["a", "a", "a", "b", "b", "b"])
    assert mod.hard_regressions(cases, base, cand, 3) == ["c0", "c2"], f"c0 (3 -> 0) and c2 (3 -> 1) were perfect and are now at most 1 of 3; got {mod.hard_regressions(cases, base, cand, 3)}"
    assert mod.hard_regressions(cases, base, cand, 3, slices=("b",)) == [] and mod.hard_regressions(cases, base, cand, 3, slices=("a",)) == ["c0", "c2"], "slices restricts the search"
    assert mod.hard_regressions(cases, base, cand, 3, max_after=0) == ["c0"] and mod.hard_regressions(cases, base, cand, 3, max_after=2) == ["c0", "c2"], "max_after is the highest candidate count that still counts as a hard regression"
    assert mod.hard_regressions(cases, base, base, 3) == [], "a version never regresses against itself"

    # an improvement overall that breaks one critical case: must be blocked
    cs = [{"id": f"r{i}", "slice": "refunds (critical)"} for i in range(4)] + [{"id": f"g{i}", "slice": "general"} for i in range(16)]
    base = {**{f"r{i}": 3 for i in range(4)}, **{f"g{i}": 1 for i in range(16)}}
    cand = {**{"r0": 0, "r1": 3, "r2": 3, "r3": 3}, **{f"g{i}": 3 for i in range(16)}}
    g = mod.gate(cs, base, cand, 3, critical=("refunds (critical)",), B=500, seed=1)
    assert list(g["report"]) == ["refunds (critical)", "general", "ALL"], f"report has one entry per slice in order of first appearance, then ALL; got {list(g['report'])}"
    r = g["report"]
    assert r["refunds (critical)"]["n"] == 4 and near(r["refunds (critical)"]["base"], 1.0) and near(r["refunds (critical)"]["cand"], 0.75) and near(r["refunds (critical)"]["diff"], -0.25), f"refunds: 4 cases, 1.00 to 0.75, diff -0.25; got {r['refunds (critical)']}"
    assert near(r["general"]["base"], 1 / 3) and near(r["general"]["cand"], 1.0) and near(r["general"]["diff"], 2 / 3), f"general: 0.33 to 1.00; got {r['general']}"
    assert r["ALL"]["n"] == 20 and near(r["ALL"]["diff"], (-0.25 * 4 + 2 / 3 * 16) / 20), f"ALL: the mean over all 20 cases; got {r['ALL']}"
    assert r["ALL"]["ci"] == oracle_ci([(cand[c["id"]] - base[c["id"]]) / 3 for c in cs], 500, 0.05, 1), "ALL's interval is paired_ci over the per-case differences (cand - base) / k, with the same B and seed"
    assert g["hard"] == ["r0"] and [ok for _, ok in g["checks"]] == [True, False] and g["decision"] == "BLOCK", f"the average is better but r0 went from 3/3 to 0/3: expected BLOCK with hard ['r0']; got {g['decision']} {g['hard']} {g['checks']}"
    assert g["checks"][0][0] == "overall lower bound >= -0.02" and g["checks"][1][0] == "no hard regression in a critical slice", f"check labels: got {[c[0] for c in g['checks']]}"
    same = mod.gate(cs, base, base, 3, critical=("refunds (critical)",), B=200)
    assert same["decision"] == "ship" and same["report"]["ALL"]["diff"] == 0 and same["report"]["ALL"]["ci"] == (0.0, 0.0), "a version against itself ships with a zero interval"
    worse = {**base, **{f"g{i}": 0 for i in range(16)}}
    w = mod.gate(cs, {**base, **{f"g{i}": 3 for i in range(16)}}, worse, 3, critical=("refunds (critical)",), B=300)
    assert w["decision"] == "BLOCK" and [ok for _, ok in w["checks"]] == [False, True] and w["hard"] == [], "a broad drop blocks through the first check even with no critical regression"
    hard_noncrit = mod.gate(cs, {**base, "g0": 3}, {**base, "g0": 0}, 3, critical=("refunds (critical)",), tolerance=0.2, B=200)
    assert hard_noncrit["hard"] == [] and hard_noncrit["decision"] == "ship", "a hard regression in a non-critical slice is not a block on its own"
    tol = mod.gate(cs, base, {**base, "g0": 0}, 3, critical=("refunds (critical)",), tolerance=0.2, B=200)
    assert tol["checks"][0][0] == "overall lower bound >= -0.20", f"the label shows the tolerance; got {tol['checks'][0][0]!r}"

    # the real scenario
    c1 = mod.run_suite(SUITE, "v1", 3)
    c2 = mod.run_suite(SUITE, "v2", 3)
    c3 = mod.run_suite(SUITE, "v3", 3)
    g2, g3 = mod.gate(SUITE, c1, c2, 3), mod.gate(SUITE, c1, c3, 3)
    assert g2["report"]["ALL"]["ci"][0] > 0 and g2["checks"][0][1], "v2 is clearly better on average, so an average-only gate would ship it"
    assert g2["hard"] and g2["decision"] == "BLOCK", f"v2 stopped escalating one refund that v1 always handled: expected BLOCK with a hard regression; got {g2['decision']} {g2['hard']}"
    assert g3["decision"] == "ship" and not g3["hard"], f"v3 repairs v2: expected ship; got {g3['decision']} {g3['hard']}"
    kept, _ = mod.dedupe(SUITE, all_cases())
    big = SUITE + kept
    d1, d2, d3 = (mod.run_suite(big, v, 3) for v in ("v1", "v2", "v3"))
    assert mod.gate(big, d1, d2, 3)["decision"] == "BLOCK" and mod.gate(big, d1, d3, 3)["decision"] == "ship", "adding the six cases built from production traces must not change the verdicts"
    new_ids = [k["id"] for k in kept]
    return ("candidate v2 against production v1 on the 120 cases:\n" + "\n".join("  " + ln for ln in mod.format_gate(g2).split("\n"))
            + f"\ncandidate v3: {g3['decision']}   (with the six new production cases added: v1 passes {sum(d1[i] for i in new_ids)} of {3 * len(new_ids)} runs of them, v3 passes {sum(d3[i] for i in new_ids)})")


MILESTONES = [
    (1, "Milestone 1: spans with parents, durations and errors", m1),
    (2, "Milestone 2: instrument the model, the tools and the request", m2),
    (3, "Milestone 3: read a trace, decide what to keep", m3),
    (4, "Milestone 4: a failing trace becomes a regression case", m4),
    (5, "Milestone 5: grade properties, run the suite k times", m5),
    (6, "Milestone 6: the regression gate", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 7 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
