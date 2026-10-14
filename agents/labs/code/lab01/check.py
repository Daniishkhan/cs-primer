"""Self-check for Lab 1: The Agent Loop from Scratch.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 4 17    # milestone 4, replaying ONLY the random scenario of seed 17

Everything is scripted and seeded: the "model" is a ScriptedModel with fixed replies,
the clock is a FakeClock you wind by hand, and no network is touched, so every run
gives identical results. The whole check takes about a second.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import json
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
from llm import Model, Response, ScriptedModel, count_tokens, text, text_of, tool_use  # noqa: E402

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


def call(name, args, id="t1"):
    return {"type": "tool_use", "id": id, "name": name, "input": args}


def fresh():
    shop = mod.Shop()
    return shop, mod.make_registry(shop)


def stuck_model():
    """A model that never gives up on the same call."""
    return ScriptedModel(lambda m, t, s: [tool_use("get_order", {"order_id": "A-1001"})])


def wanderer():
    """A model that keeps trying new things (never repeats a call)."""
    n = {"i": 0}

    def fn(m, t, s):
        n["i"] += 1
        return [tool_use("get_order", {"order_id": f"A-{1000 + n['i']}"})]
    return ScriptedModel(fn)


def oracle_pairing(messages):
    """An independent, plain check of the history rules (returns True when valid)."""
    for i, m in enumerate(messages):
        if m["role"] != ("user" if i % 2 == 0 else "assistant"):
            return False
        if isinstance(m["content"], str):
            continue
        uses = [b["id"] for b in m["content"] if b["type"] == "tool_use"]
        if uses:
            if i + 1 >= len(messages) or isinstance(messages[i + 1]["content"], str):
                return False
            got = [b["tool_use_id"] for b in messages[i + 1]["content"] if b["type"] == "tool_result"]
            if got != uses:
                return False
        if m["role"] == "user" and i > 0:
            ids = [b["tool_use_id"] for b in m["content"] if b["type"] == "tool_result"]
            prev = [b["id"] for b in messages[i - 1]["content"] if b["type"] == "tool_use"]
            if ids != prev:
                return False
    return True


# =============================================================================
# Milestone 1: schemas and argument validation
# =============================================================================
def m1():
    shop, reg = fresh()
    defs = reg.definitions()
    assert isinstance(defs, list) and [d["name"] for d in defs] == ["get_order", "track_shipment", "issue_refund", "get_returns_policy"], \
        f"definitions() must list the tools in registration order; got {[d.get('name') for d in defs] if isinstance(defs, list) else defs!r}"
    for d in defs:
        assert set(d) == {"name", "description", "input_schema"}, \
            f"each definition has exactly name, description and input_schema (never the function); {d.get('name')} has {sorted(d)}"
    defs.append("junk")
    assert len(reg.definitions()) == 4, "definitions() must return a fresh list each time (the registry must not change when the caller appends)"

    refund = reg.get("issue_refund").input_schema
    ok = {"order_id": "A-1001", "amount_cents": 2500, "reason": "duplicate"}
    got = mod.validate_args(refund, ok)
    assert got == [], f"valid arguments must give an empty list; got {got}"

    def one(bad, needle, label):
        errs = mod.validate_args(refund, bad)
        assert len(errs) == 1, f"{label}: expected exactly 1 problem, got {len(errs)}: {errs}"
        assert needle in errs[0], f"{label}: the problem should mention {needle!r}; got {errs[0]!r}"
        return errs[0]

    one({k: v for k, v in ok.items() if k != "reason"}, "reason", "missing argument")
    one({**ok, "amount_cents": "2500"}, "amount_cents", "string where integer needed")
    one({**ok, "amount_cents": True}, "amount_cents", "bool is not an integer (hint: isinstance(True, int) is True in Python)")
    one({**ok, "amount_cents": 25.5}, "amount_cents", "float is not an integer")
    assert "1" in one({**ok, "amount_cents": 0}, "amount_cents", "below minimum"), "name the bound that was broken (the minimum, 1)"
    assert "10000" in one({**ok, "amount_cents": 10001}, "amount_cents", "above maximum"), "name the bound that was broken (the maximum, 10000)"
    e = one({**ok, "reason": "refund"}, "reason", "value not in enum")
    assert all(v in e for v in ("duplicate", "damaged", "goodwill")), f"an enum problem must list the valid values; got {e!r}"
    e = one({**ok, "order_id": "1001"}, "order_id", "pattern mismatch")
    assert "A-1001" in e or "A-" in e, f"a pattern problem should show the pattern or an example; got {e!r}"
    one({**ok, "order_id": "A-10012"}, "order_id", "pattern must match the WHOLE string (re.fullmatch)")
    one({**ok, "order_id": "xA-1001"}, "order_id", "pattern must match from the start")
    e = one({**ok, "note": "hi"}, "note", "unexpected argument")
    assert "order_id" in e, f"an unexpected-argument problem should list the valid arguments; got {e!r}"

    multi = mod.validate_args(refund, {"amount_cents": "x", "note": 1, "reason": "nope"})
    assert len(multi) == 4, f"expected 4 problems (missing order_id, bad amount_cents type, bad reason, unexpected note); got {multi}"
    assert "order_id" in multi[0], f"missing required arguments come first; got {multi[0]!r} first"
    assert "amount_cents" in multi[1] and "reason" in multi[2] and "note" in multi[3], \
        f"then properties in schema order, then unexpected arguments; got {multi}"

    for bad in ("A-1001", None, ["A-1001"], 5):
        r = mod.validate_args(refund, bad)
        assert len(r) == 1, f"arguments that are not an object must give exactly one problem and not raise; {bad!r} gave {r}"
    assert mod.validate_args({}, {}) == [] and mod.validate_args({"type": "object", "properties": {}}, {}) == []
    num = {"type": "object", "properties": {"x": {"type": "number"}}}
    assert mod.validate_args(num, {"x": 3}) == [] and mod.validate_args(num, {"x": 2.5}) == [], "an int is a valid number"
    assert mod.validate_args(num, {"x": True}) and mod.validate_args(num, {"x": "3"}), "a bool or a string is not a number"

    # property: generate valid arguments for random schemas, break exactly one thing
    kinds = {"string": lambda r: r.choice(["a", "bb", "ccc"]), "integer": lambda r: r.randint(-5, 50),
             "number": lambda r: r.choice([0.5, 2, 7.25]), "boolean": lambda r: r.choice([True, False])}
    wrong = {"string": 7, "integer": "7", "number": "7", "boolean": "yes"}
    for s in seeds(range(60)):
        r = random.Random(s)
        props = {}
        for i in range(r.randint(1, 5)):
            t = r.choice(list(kinds))
            props[f"arg{i}"] = {"type": t}
        required = [k for k in props if r.random() < 0.6]
        schema = {"type": "object", "properties": props, "required": required}
        good = {k: kinds[v["type"]](r) for k, v in props.items() if k in required or r.random() < 0.5}
        assert mod.validate_args(schema, good) == [], f"seed {s}: valid arguments {good} were rejected for {schema}: {mod.validate_args(schema, good)}"
        victim = r.choice(list(props))
        broken = dict(good)
        broken[victim] = wrong[props[victim]["type"]]
        errs = mod.validate_args(schema, broken)
        assert len(errs) == 1 and victim in errs[0], f"seed {s}: one wrong-typed argument ({victim}) should give exactly one problem naming it; got {errs}"
        if required:
            gone = dict(good)
            gone.pop(required[0], None)
            errs = mod.validate_args(schema, gone)
            assert len(errs) == 1 and required[0] in errs[0], f"seed {s}: removing required {required[0]} should give one problem naming it; got {errs}"
    return ""


# =============================================================================
# Milestone 2: running one tool call
# =============================================================================
def m2():
    shop, reg = fresh()
    r = mod.run_tool(reg, call("get_order", {"order_id": "A-1001"}, id="abc"))
    assert r["type"] == "tool_result" and r["tool_use_id"] == "abc" and r["is_error"] is False, f"a good call gives a non-error tool_result with the call's id; got {r}"
    assert json.loads(r["content"])["carrier"] == "UPS", f"the content should be the tool's output; got {r['content']!r}"
    assert shop.executed == ["get_order"], f"the function should have run exactly once; ran {shop.executed}"

    shop, reg = fresh()
    r = mod.run_tool(reg, call("delete_everything", {}, id="u1"))
    assert r["is_error"] is True and r["tool_use_id"] == "u1", f"an unknown tool is an error result with the call's id; got {r}"
    assert "delete_everything" in r["content"] and "get_order" in r["content"], \
        f"say which name was unknown and list the available tools; got {r['content']!r}"
    assert shop.executed == []

    r = mod.run_tool(reg, call("issue_refund", {"order_id": "A-1001", "amount_cents": "lots", "reason": "nope"}))
    assert r["is_error"] and r["content"].startswith("Invalid arguments for issue_refund:"), \
        f"invalid arguments: content should start 'Invalid arguments for issue_refund:'; got {r['content']!r}"
    assert "amount_cents" in r["content"] and "reason" in r["content"], f"include EVERY problem from validate_args; got {r['content']!r}"
    assert shop.executed == [] and shop.refunds == [], "the function must NOT run when the arguments are invalid (a refund would be real money)"

    r = mod.run_tool(reg, call("get_order", {"order_id": "A-9999"}))
    assert r["is_error"] and r["content"] == "No order with id 'A-9999'. Order ids look like A-1001.", \
        f"a ToolError's message goes back verbatim; got {r['content']!r}"

    boom = mod.Registry([mod.Tool("boom", "Always fails.", {"type": "object", "properties": {}}, lambda: {}["secret_table"])])
    r = mod.run_tool(boom, call("boom", {}))
    assert r["is_error"] and "boom" in r["content"] and "KeyError" in r["content"], f"name the tool and the exception TYPE; got {r['content']!r}"
    assert "secret_table" not in r["content"], f"do not leak the exception's message into the context; got {r['content']!r}"

    structured = mod.Registry([mod.Tool("s", "Returns a dict.", {"type": "object", "properties": {}}, lambda: {"b": 1, "a": [1, 2]})])
    r = mod.run_tool(structured, call("s", {}))
    assert r["content"] == '{"a": [1, 2], "b": 1}', f"non-string results are json.dumps(..., sort_keys=True); got {r['content']!r}"

    shop, reg = fresh()
    full = mod.run_tool(reg, call("get_returns_policy", {}), max_result_chars=100000)["content"]
    cut = mod.run_tool(reg, call("get_returns_policy", {}), max_result_chars=300)["content"]
    assert cut.startswith(full[:300]) and len(cut) > 300, f"keep the first 300 characters and then add a note; got {cut[:60]!r}... ({len(cut)} chars)"
    assert "truncated" in cut and "300" in cut and str(len(full)) in cut, \
        f"the note must say 'truncated' and give the shown ({300}) and total ({len(full)}) lengths; got {cut[300:]!r}"
    assert len(cut) < 300 + 160, f"the note should be short; the result is {len(cut)} characters"
    assert mod.run_tool(reg, call("get_order", {"order_id": "A-1001"}), max_result_chars=10000)["content"] == json.dumps(shop.orders["A-1001"]), \
        "a short result must be returned untouched"
    long_err = mod.Registry([mod.Tool("e", "x", {"type": "object", "properties": {}}, lambda: (_ for _ in ()).throw(mod.ToolError("x" * 500)))])
    assert len(mod.run_tool(long_err, call("e", {}), max_result_chars=100)["content"]) == 500, "error messages are never truncated"

    for odd in ({"id": "z", "name": "get_order"}, {"type": "tool_use", "id": "z", "name": "get_order", "input": None},
                {"id": "z", "name": "get_order", "input": "A-1001"}, {"id": "z"}):
        r = mod.run_tool(reg, odd)
        assert r["is_error"] and r["tool_use_id"] == "z", f"malformed call {odd} must come back as an error result, not an exception; got {r}"

    names = ["get_order", "track_shipment", "issue_refund", "get_returns_policy", "nope"]
    for s in seeds(range(60)):
        rng = random.Random(s)
        shop, reg = fresh()
        c = call(rng.choice(names), rng.choice([{}, {"order_id": rng.choice(["A-1001", "A-9999", "x", 5, None])},
                                                 {"carrier": rng.choice(["UPS", "FedEx", 3])},
                                                 {"order_id": "A-1002", "amount_cents": rng.choice([5, 0, 99999, "5", 1e9]), "reason": rng.choice(["goodwill", "x"])}]),
                 id=f"id{s}")
        r = mod.run_tool(reg, c)
        assert isinstance(r, dict) and r.get("type") == "tool_result" and r.get("tool_use_id") == f"id{s}" and isinstance(r.get("is_error"), bool) \
            and isinstance(r.get("content"), str), f"seed {s}: run_tool({c}) must return a well-formed tool_result; got {r}"
        if r["is_error"] is False:
            continue
        assert shop.refunds == [] or c["name"] == "issue_refund", f"seed {s}: an error result must not leave side effects"
    return ""


# =============================================================================
# Milestone 3: stopping rules
# =============================================================================
def m3():
    Budget, Guard, Clock = mod.Budget, mod.LoopGuard, mod.FakeClock
    clock = Clock()
    g = Guard(Budget(max_iterations=3), clock)
    seen = []
    for _ in range(4):
        seen.append(g.before_model_call())
        g.after_model_call({"input_tokens": 10, "output_tokens": 5})
    assert seen == [None, None, None, "max_iterations"], f"with max_iterations=3 the 4th call must be refused; before_model_call() gave {seen}"
    assert g.iterations == 4 and g.input_tokens == 40, f"iterations and input_tokens must accumulate; got {g.iterations}, {g.input_tokens}"

    g = Guard(Budget(max_input_tokens=100), clock)
    g.after_model_call({"input_tokens": 100, "output_tokens": 0})
    assert g.before_model_call() is None, "exactly at the limit is still allowed (the rule is MORE than max_input_tokens)"
    g.after_model_call({"input_tokens": 1, "output_tokens": 0})
    assert g.before_model_call() == "token_budget", "101 > 100 tokens must give 'token_budget'"

    clock = Clock(1000.0)
    g = Guard(Budget(max_seconds=30), clock)
    clock.advance(30)
    assert g.before_model_call() is None, "exactly 30 s elapsed is still allowed; the guard measures from when it was created (1000.0 here, not from 0)"
    clock.advance(0.5)
    assert g.before_model_call() == "timeout", "30.5 s > 30 s must give 'timeout'"

    clock = Clock()
    g = Guard(Budget(max_iterations=1, max_input_tokens=5, max_seconds=1), clock)
    g.after_model_call({"input_tokens": 50})
    clock.advance(10)
    assert g.before_model_call() == "token_budget", "when several limits are exceeded, report token_budget first, then timeout, then max_iterations"
    g = Guard(Budget(max_iterations=1, max_seconds=1), clock)
    clock.advance(10)
    g.after_model_call({"input_tokens": 1})
    clock.advance(10)
    assert g.before_model_call() == "timeout", "timeout is reported before max_iterations"

    g = Guard(Budget(max_repeats=2), clock)
    a = {"name": "get_order", "input": {"order_id": "A-1001", "x": 1}}
    a2 = {"name": "get_order", "input": {"x": 1, "order_id": "A-1001"}}
    assert g.check_calls([a]) is None and g.check_calls([a2]) is None, "two identical calls are allowed when max_repeats=2 (key order of the input does not matter)"
    assert g.check_calls([{"name": "get_order", "input": {"order_id": "A-1002"}}]) is None, "a different input is a different call"
    assert g.check_calls([{"name": "track_shipment", "input": {"order_id": "A-1001", "x": 1}}]) is None, "a different tool name is a different call"
    assert g.check_calls([a]) == "repeated_call", "the THIRD identical call must give 'repeated_call' (counts persist across check_calls calls)"
    g = Guard(Budget(max_repeats=2), clock)
    assert g.check_calls([a, a, a]) == "repeated_call", "three identical calls in one turn also count"
    g = Guard(Budget(max_repeats=0), clock)
    assert g.check_calls([a]) == "repeated_call", "max_repeats=0 forbids even the first call"

    # property: compare with a naive oracle on random sequences of events
    for s in seeds(range(60)):
        rng = random.Random(s)
        b = Budget(max_iterations=rng.randint(1, 6), max_input_tokens=rng.randint(10, 300), max_repeats=rng.randint(1, 3), max_seconds=rng.randint(5, 60))
        clock = Clock(rng.random() * 100)
        g = Guard(b, clock)
        t0, its, toks, counts = clock(), 0, 0, {}
        for step in range(12):
            op = rng.choice(["model", "tick", "calls"])
            if op == "model":
                u = rng.randint(0, 120)
                g.after_model_call({"input_tokens": u, "output_tokens": 1})
                its += 1
                toks += u
            elif op == "tick":
                dt = rng.choice([0.5, 3, 11])
                clock.advance(dt)
            else:
                cs = [{"name": rng.choice("ab"), "input": {"k": rng.randint(0, 1)}} for _ in range(rng.randint(1, 3))]
                over = False
                for c in cs:
                    key = (c["name"], c["input"]["k"])
                    counts[key] = counts.get(key, 0) + 1
                    over = over or counts[key] > b.max_repeats
                got = g.check_calls(cs)
                assert got == ("repeated_call" if over else None), f"seed {s} step {step}: check_calls({cs}) gave {got!r}, expected {'repeated_call' if over else None!r} (counts {counts}, max_repeats {b.max_repeats})"
            want = "token_budget" if toks > b.max_input_tokens else "timeout" if clock() - t0 > b.max_seconds else "max_iterations" if its >= b.max_iterations else None
            got = g.before_model_call()
            assert got == want, f"seed {s} step {step}: before_model_call() gave {got!r}, expected {want!r} (iterations {its}, tokens {toks}, elapsed {clock() - t0:.1f}, budget {b})"
    return ""


# =============================================================================
# Milestone 4: the loop
# =============================================================================
def m4():
    P = mod.check_pairing
    u = lambda *r: {"role": "user", "content": list(r)}
    a = lambda *b: {"role": "assistant", "content": list(b)}
    res = lambda i, c="ok": {"type": "tool_result", "tool_use_id": i, "content": c, "is_error": False}
    good = [{"role": "user", "content": "q"}, a(call("get_order", {}, "t1"), call("get_order", {}, "t2")), u(res("t1"), res("t2")), a(text("done"))]
    assert P(good) == [], f"a valid history gives no problems; got {P(good)}"
    p = P(good[:2] + [u(res("t1"))] + good[3:])
    assert len(p) == 1 and "t2" in p[0] and p[0].startswith("message 1:"), f"a tool_use with no tool_result is reported against the assistant message ('message 1:'), naming the id; got {p}"
    p = P(good[:2] + [u(res("t1"), res("t2"), res("zz"))] + good[3:])
    assert len(p) == 1 and "zz" in p[0] and p[0].startswith("message 2:"), f"a tool_result that answers nothing is reported against its own message; got {p}"
    p = P(good[:2] + [u(res("t1"), res("t1"), res("t2"))] + good[3:])
    assert len(p) == 1 and "t1" in p[0], f"two tool_results for one id is a problem; got {p}"
    p = P(good[:2])
    assert len(p) == 1 and "t1" in p[0] and "t2" in p[0] or len(p) == 2, f"a history that ends on an unanswered tool_use is invalid; got {p}"
    assert P([{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]), "two user messages in a row are invalid"
    assert P([{"role": "assistant", "content": [text("hi")]}]), "a history must start with a user message"

    # the happy path from the chapter
    shop, reg = fresh()
    model = ScriptedModel([[tool_use("get_order", {"order_id": "A-1001"}, id="t1")], [tool_use("track_shipment", {"carrier": "UPS"}, id="t2")],
                           "Order A-1001 shipped with UPS and is out for delivery in Leeds."])
    r = mod.agent_loop(model, "Where is order A-1001?", reg, system="You are a support agent.")
    assert r.status == "done", f"status should be 'done'; got {r.status!r}"
    assert r.answer == "Order A-1001 shipped with UPS and is out for delivery in Leeds.", f"answer should be the final text; got {r.answer!r}"
    assert len(r.messages) == 6 and r.iterations == 3, f"3 model calls and 6 messages expected; got {r.iterations} and {len(r.messages)}"
    assert P(r.messages) == [], f"history must satisfy check_pairing; got {P(r.messages)}"
    assert shop.executed == ["get_order", "track_shipment"]
    assert model.calls[0]["system"] == "You are a support agent." and model.calls[0]["tools"] == reg.definitions(), "send the system prompt and registry.definitions() on every request"
    assert [len(c["messages"]) for c in model.calls] == [1, 3, 5], f"each request carries the whole history so far; sizes were {[len(c['messages']) for c in model.calls]}"
    assert r.input_tokens > 0, "RunResult.input_tokens is the summed input tokens of the model calls (from reply.usage)"

    # parallel calls: ONE user message with all results, in order
    shop, reg = fresh()
    model = ScriptedModel([[tool_use("get_order", {"order_id": "A-1001"}, id="ta"), tool_use("get_order", {"order_id": "A-1002"}, id="tb")], "Both found."])
    r = mod.agent_loop(model, "Status of A-1001 and A-1002?", reg)
    assert len(r.messages) == 4, f"two parallel calls make ONE assistant and ONE user message (4 in total); got {len(r.messages)}"
    ids = [b["tool_use_id"] for b in r.messages[2]["content"]]
    assert ids == ["ta", "tb"], f"results must be in the order of the calls, in one message; got {ids}"

    # failures are data: the loop survives an error and the model corrects itself
    shop, reg = fresh()
    model = ScriptedModel([[tool_use("get_order", {"order_id": "A-9999"}, id="t1")], [tool_use("get_order", {"order_id": "A-1002"}, id="t2")], "A-1002 is processing."])
    r = mod.agent_loop(model, "Check A-9999", reg)
    assert r.status == "done" and r.messages[2]["content"][0]["is_error"] is True, "the error must be in the history as an is_error tool_result and the run must go on"

    # forced stops: each returns a valid history, a reason and a useful answer
    shop, reg = fresh()
    r = mod.agent_loop(wanderer(), "Find an order", reg, budget=mod.Budget(max_iterations=3))
    assert r.status == "max_iterations" and r.iterations == 3, f"expected status 'max_iterations' after 3 calls; got {r.status!r} after {r.iterations}"
    assert r.answer == mod.STOP_MESSAGES["max_iterations"], f"a forced stop answers with STOP_MESSAGES[status]; got {r.answer!r}"
    assert P(r.messages) == [] and r.messages[-1]["role"] == "user", "the history after a forced stop must still be valid and end on the tool results"
    assert len(shop.executed) == 3, f"the tools of all 3 replies were run; ran {len(shop.executed)}"

    shop, reg = fresh()
    r = mod.agent_loop(wanderer(), "Find an order", reg, budget=mod.Budget(max_input_tokens=300, max_iterations=50))
    assert r.status == "token_budget" and r.input_tokens > 300 and P(r.messages) == [], f"expected 'token_budget' with a valid history; got {r.status!r}, {r.input_tokens} tokens, pairing {P(r.messages)}"
    assert r.iterations < 50, "the token budget must stop the run long before 50 calls"

    shop, reg = fresh()
    r = mod.agent_loop(stuck_model(), "Where is A-1001?", reg)
    assert r.status == "repeated_call" and r.iterations == 3, f"max_repeats=2 means the THIRD identical call stops the run (after 3 model calls); got {r.status!r} after {r.iterations}"
    assert shop.executed == ["get_order", "get_order"], f"the repeated third call must NOT run; executed {shop.executed}"
    last = r.messages[-1]["content"]
    assert P(r.messages) == [] and last[0]["is_error"] and last[0]["content"].startswith("Not run"), f"the unrun call must still get an error result starting 'Not run' so the history stays valid; got {last}"
    assert r.answer == mod.STOP_MESSAGES["repeated_call"]

    clock = mod.FakeClock()

    def slow(m, t, s):
        clock.advance(10)
        return [tool_use("get_order", {"order_id": f"A-{1000 + len(m)}"})]
    shop, reg = fresh()
    r = mod.agent_loop(ScriptedModel(slow), "slow", reg, budget=mod.Budget(max_seconds=25), clock=clock)
    assert r.status == "timeout" and r.iterations == 3, f"calls at t=0, 10, 20 are allowed; at t=30 > 25 the run must stop with 'timeout'. Got {r.status!r} after {r.iterations}"

    # a reply cut off by max_tokens
    shop, reg = fresh()
    r = mod.agent_loop(ScriptedModel([Response([text("The order is")], "max_tokens")]), "q", reg)
    assert r.status == "truncated" and r.answer == "The order is", f"a text reply cut off by max_tokens: status 'truncated' and the partial text as the answer; got {r.status!r}, {r.answer!r}"
    r = mod.agent_loop(ScriptedModel([Response([tool_use("issue_refund", {"order_id": "A-1001", "amount_cents": 100}, id="cut")], "max_tokens")]), "q", reg)
    assert r.status == "truncated" and shop.refunds == [] and P(r.messages) == [], \
        f"a tool call cut off by max_tokens must NOT be run, but must still be answered (is_error) so the history stays valid; got {r.status!r}, refunds {shop.refunds}, pairing {P(r.messages)}"

    # property: random scenarios keep every invariant
    for s in seeds(range(40)):
        rng = random.Random(s)
        shop, reg = fresh()
        pool = [("get_order", {"order_id": "A-1001"}), ("get_order", {"order_id": "A-9999"}), ("get_order", {"order_id": "bad"}),
                ("track_shipment", {"carrier": "DHL"}), ("track_shipment", {"carrier": "TNT"}), ("nope", {}), ("get_returns_policy", {})]
        script = []
        for _ in range(rng.randint(1, 9)):
            k = rng.choice([0, 1, 1, 2, 3])
            script.append([tool_use(*rng.choice(pool), id=f"s{s}-{len(script)}-{j}") for j in range(k)] or "ok")
        budget = mod.Budget(max_iterations=rng.randint(1, 6), max_repeats=rng.randint(1, 3))
        r = mod.agent_loop(ScriptedModel(script + ["final"] * 12), "q", reg, budget=budget)
        assert oracle_pairing(r.messages), f"seed {s}: the history is not valid: {P(r.messages) or 'your check_pairing says it is fine, so check_pairing is too lenient'}"
        assert r.iterations <= budget.max_iterations, f"seed {s}: {r.iterations} model calls with max_iterations={budget.max_iterations}"
        assert r.status in ("done", "max_iterations", "repeated_call"), f"seed {s}: unexpected status {r.status!r}"
        assert r.messages[0]["content"] == "q" and sum(1 for m in r.messages if m["role"] == "assistant") == r.iterations, f"seed {s}: one assistant message per model call"
        bad_ran = [n for n in shop.executed if n == "nope"]
        assert not bad_ran, f"seed {s}: an unknown tool 'ran'"
    return ""


# =============================================================================
# Milestone 5: logging and reading a trace
# =============================================================================
class Spy(Model):
    """Wraps a model and remembers every reply (to compare with what the trace says)."""
    name = "spy"

    def __init__(self, inner):
        self.inner, self.replies = inner, []

    def complete(self, messages, **kw):
        r = self.inner.complete(messages, **kw)
        self.replies.append(r)
        return r


def m5():
    clock = mod.FakeClock()

    def slow_lookup(order_id):
        clock.advance(2.5)
        return "found " + order_id
    reg = mod.Registry([mod.Tool("lookup", "Look up an order.", {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}, slow_lookup)])
    spy = Spy(ScriptedModel([[tool_use("lookup", {"order_id": "A-1"}, id="c1"), tool_use("lookup", {"order_id": 7}, id="c2")],
                             [tool_use("lookup", {"order_id": "A-1"}, id="c3")], "All done."]))
    trace = mod.Trace()
    r = mod.agent_loop(spy, "check", reg, trace=trace, clock=clock)
    kinds = [e["kind"] for e in trace.events]
    assert kinds == ["model_call", "tool_call", "tool_call", "model_call", "tool_call", "model_call", "stop"], \
        f"expected events model_call, tool_call, tool_call, model_call, tool_call, model_call, stop in that order; got {kinds}"
    mc = [e for e in trace.events if e["kind"] == "model_call"]
    assert [e["i"] for e in mc] == [1, 2, 3], f"model_call events carry the iteration number i=1,2,3; got {[e.get('i') for e in mc]}"
    assert [e["input_tokens"] for e in mc] == [x.usage["input_tokens"] for x in spy.replies], "model_call.input_tokens must be the usage the model reported"
    assert [e["output_tokens"] for e in mc] == [x.usage["output_tokens"] for x in spy.replies], "model_call.output_tokens must be the usage the model reported"
    assert mc[0]["stop_reason"] == "tool_use" and mc[2]["stop_reason"] == "end_turn" and mc[0]["tools"] == ["lookup", "lookup"], f"model_call needs stop_reason and tools (names requested); got {mc[0]}"
    tc = [e for e in trace.events if e["kind"] == "tool_call"]
    assert [(e["i"], e["id"], e["tool"], e["is_error"]) for e in tc] == [(1, "c1", "lookup", False), (1, "c2", "lookup", True), (2, "c3", "lookup", False)], \
        f"tool_call fields i, id, tool, is_error wrong; got {[(e.get('i'), e.get('id'), e.get('tool'), e.get('is_error')) for e in tc]}"
    assert tc[0]["input"] == {"order_id": "A-1"} and tc[0]["result_chars"] == len("found A-1"), f"input and result_chars; got {tc[0]}"
    assert [e["seconds"] for e in tc] == [2.5, 0.0, 2.5], f"seconds is how long run_tool took on the clock (the invalid call never ran: 0.0); got {[e['seconds'] for e in tc]}"
    assert trace.events[-1] == {"kind": "stop", "status": "done", "iterations": 3}, f"exactly one final stop event; got {trace.events[-1]}"
    json.dumps(trace.events)

    t2 = mod.Trace()
    mod.agent_loop(stuck_model(), "x", fresh()[1], trace=t2)
    assert [e["kind"] for e in t2.events].count("stop") == 1 and t2.events[-1]["status"] == "repeated_call", "a forced stop also ends the trace with one stop event carrying the reason"
    mod.agent_loop(ScriptedModel(["hi"]), "x", fresh()[1])      # trace=None must still work

    s = mod.summarise(trace.events)
    want = {"status": "done", "iterations": 3, "input_tokens": sum(x.usage["input_tokens"] for x in spy.replies),
            "output_tokens": sum(x.usage["output_tokens"] for x in spy.replies), "tool_calls": 3, "errors": 1,
            "calls_by_tool": {"lookup": 3}, "wasted_calls": 2, "seconds": 5.0}
    assert s == want, "summarise(events) wrong.\n  expected " + json.dumps(want) + "\n  got      " + json.dumps(s) + \
        "\n  hint: wasted_calls counts the error (1) plus the repeat of lookup A-1 (1)"
    assert r.iterations == s["iterations"] and r.input_tokens == s["input_tokens"], "the RunResult and the summary of its trace must agree"

    empty = mod.summarise([])
    assert empty == {"status": "", "iterations": 0, "input_tokens": 0, "output_tokens": 0, "tool_calls": 0, "errors": 0,
                     "calls_by_tool": {}, "wasted_calls": 0, "seconds": 0.0}, f"summarise([]) must be all zeros; got {empty}"
    hand = [{"kind": "tool_call", "i": 1, "id": "a", "tool": "x", "input": {"p": 1, "q": 2}, "is_error": True, "result_chars": 3, "seconds": 1.0},
            {"kind": "tool_call", "i": 1, "id": "b", "tool": "x", "input": {"q": 2, "p": 1}, "is_error": True, "result_chars": 3, "seconds": 1.0},
            {"kind": "tool_call", "i": 2, "id": "c", "tool": "y", "input": {}, "is_error": False, "result_chars": 3, "seconds": 0.25}]
    s = mod.summarise(hand)
    assert (s["errors"], s["wasted_calls"], s["calls_by_tool"], s["seconds"]) == (2, 2, {"x": 2, "y": 1}, 2.25), \
        f"two failed identical calls are 2 wasted calls (each event once; key order of the input is ignored); got {s}"

    # scenario: diagnose three failing runs from their traces alone
    out = []
    for label, model, budget in (("stuck", stuck_model(), mod.Budget()), ("wanderer", wanderer(), mod.Budget(max_iterations=5)),
                                 ("typo", ScriptedModel([[tool_use("get_order", {"order_id": "A-99"})], [tool_use("get_order", {"order_id": "A-1001"})], "ok"]), mod.Budget())):
        t = mod.Trace()
        res = mod.agent_loop(model, "q", fresh()[1], trace=t, budget=budget)
        sm = mod.summarise(t.events)
        out.append((label, res.status, sm))
    by = {k: (st, sm) for k, st, sm in out}
    assert by["stuck"][0] == "repeated_call" and by["stuck"][1]["wasted_calls"] == 1 and by["stuck"][1]["tool_calls"] == 2, f"stuck run: expected 2 tool calls, 1 wasted; got {by['stuck']}"
    assert by["wanderer"][0] == "max_iterations" and by["wanderer"][1]["tool_calls"] == 5, f"wanderer: 5 tool calls then the iteration cap; got {by['wanderer']}"
    assert by["typo"][1]["errors"] == 1 and by["typo"][1]["wasted_calls"] == 1 and by["typo"][0] == "done", f"typo run: one error, recovered; got {by['typo']}"
    return "\n".join(f"{k:9s} status={st:15s} calls={sm['tool_calls']} errors={sm['errors']} wasted={sm['wasted_calls']} input_tokens={sm['input_tokens']}" for k, st, sm in out)


# =============================================================================
# Milestone 6: the same loop with a text-only model
# =============================================================================
def m6():
    P = mod.parse_react
    r = P('Thought: I need the order.\nAction: get_order {"order_id": "A-1001"}')
    assert r == {"kind": "action", "thought": "I need the order.", "tool": "get_order", "input": {"order_id": "A-1001"}}, f"plain action; got {r}"
    r = P('Thought: look\nAction: get_order {"order_id": "A-1001"}\nObservation: shipped via UPS\nThought: now\nAction: track_shipment {"carrier": "UPS"}')
    assert r["kind"] == "action" and r["tool"] == "get_order" and r["input"] == {"order_id": "A-1001"}, \
        f"everything from the first 'Observation:' line on is the model inventing a result: cut it off BEFORE parsing; got {r}"
    assert P("Thought: guess\nObservation: it is 5\nFinal Answer: 5")["kind"] == "error", \
        "a reply that invents an Observation BEFORE any Action or Final Answer has nothing valid left after the cut: that is an error"
    assert P("Final Answer: 6 years\nObservation: made up")["answer"] == "6 years", "text from the first 'Observation:' line on is not part of the answer"
    r = P("Thought: I know it.\nFinal Answer: It shipped with UPS.\nand is on its way")
    assert r == {"kind": "final", "thought": "I know it.", "answer": "It shipped with UPS.\nand is on its way"}, f"final answer keeps everything after the marker; got {r}"
    assert P("Final Answer: hi") == {"kind": "final", "thought": "", "answer": "hi"}
    r = P('Thought: first\nstill thinking\nAction: get_returns_policy')
    assert r == {"kind": "action", "thought": "first\nstill thinking", "tool": "get_returns_policy", "input": {}}, f"no JSON means empty input; a thought can span lines; got {r}"
    r = P('Action: lookup {"a": {"b": [1, 2]}, "c": "x y"}')
    assert r["kind"] == "action" and r["input"] == {"a": {"b": [1, 2]}, "c": "x y"} and r["thought"] == "", f"nested JSON; got {r}"
    r = P('Action: get_order {"order_id": }')
    assert r["kind"] == "error" and "JSON" in r["message"], f"invalid JSON is an error with a message mentioning JSON; got {r}"
    assert P('Action: get_order ["A-1001"]')["kind"] == "error", "JSON that is not an object is an error"
    assert P("I think the order shipped.")["kind"] == "error", "a reply with neither marker is an error"
    assert P("Final Answer: ok\nAction: x {}")["kind"] == "final" and P('Action: x {}\nFinal Answer: ok')["kind"] == "action", "whichever marker comes first wins"
    assert P("  Action: x")["kind"] == "error", "markers must start a line"

    rng = random.Random(0)
    bits = ["Thought:", "Action:", "Final Answer:", "Observation:", "{", "}", '"', "\n", " ", "x", "get_order", "[", "]", ":", "\\", "é", "{\"a\": 1}"]
    for s in seeds(range(60)):
        rng = random.Random(s)
        junk = "".join(rng.choice(bits) for _ in range(rng.randint(0, 25)))
        try:
            out = P(junk)
        except Exception as e:
            raise AssertionError(f"seed {s}: parse_react({junk!r}) raised {type(e).__name__}: {e}; it must never raise") from None
        assert out["kind"] in ("action", "final", "error"), f"seed {s}: bad kind in {out}"
        if out["kind"] == "action":
            assert isinstance(out["input"], dict) and out["tool"], f"seed {s}: an action needs a tool name and a dict input; got {out}"

    msgs = [{"role": "user", "content": "Where is A-1001?"},
            {"role": "assistant", "content": [text("Need the order."), tool_use("get_order", {"order_id": "A-1001"}, id="t1")]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "{\"status\": \"shipped\"}", "is_error": False}]},
            {"role": "assistant", "content": [tool_use("get_returns_policy", {}, id="t2")]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "bad", "is_error": True}]},
            {"role": "assistant", "content": [text("It shipped.")]}]
    want = ('Question: Where is A-1001?\nThought: Need the order.\nAction: get_order {"order_id": "A-1001"}\n'
            'Observation: {"status": "shipped"}\nAction: get_returns_policy {}\nObservation: bad\nFinal Answer: It shipped.\n')
    got = mod.to_transcript(msgs)
    assert got == want, f"to_transcript wrong.\n  expected {want!r}\n  got      {got!r}"

    # ReActModel on its own
    inner = ScriptedModel(['Thought: look it up\nAction: get_order {"order_id": "A-1001"}'])
    resp = mod.ReActModel(inner).complete([{"role": "user", "content": "Where is A-1001?"}], tools=mod.make_registry(mod.Shop()).definitions())
    assert resp.stop_reason == "tool_use" and [b["type"] for b in resp.content] == ["text", "tool_use"], f"an action becomes [text(thought), tool_use] with stop_reason 'tool_use'; got {resp.content}, {resp.stop_reason}"
    assert resp.content[1]["id"] == "react-1" and resp.content[1]["input"] == {"order_id": "A-1001"}, f"tool_use id is f'react-{{n}}' with n = 1 + assistant messages so far; got {resp.content[1]}"
    sent = inner.calls[0]
    assert sent["messages"] == [{"role": "user", "content": "Question: Where is A-1001?\n"}] and "get_order" in (sent["system"] or ""), \
        f"the inner model gets ONE user message holding the transcript, and a system prompt that lists the tools; got {sent['messages']}, system={str(sent['system'])[:40]!r}"
    resp = mod.ReActModel(ScriptedModel(["Final Answer: Shipped."])).complete([{"role": "user", "content": "q"}], tools=[])
    assert resp.stop_reason == "end_turn" and resp.content == [text("Shipped.")], f"a final answer is text with stop_reason 'end_turn'; got {resp}"

    # format errors: the adapter shows the model its mistake, then asks again
    inner = ScriptedModel(['Action: get_order {"order_id": }', 'Action: get_order {"order_id": "A-1001"}'])
    resp = mod.ReActModel(inner).complete([{"role": "user", "content": "q"}], tools=[])
    assert resp.stop_reason == "tool_use" and len(inner.calls) == 2, f"one format error then a valid reply: 2 inner calls and a tool_use; got {len(inner.calls)} calls, {resp.stop_reason!r}"
    retry_prompt = inner.calls[1]["messages"][0]["content"]
    assert "Format error" in retry_prompt and '{"order_id": }' in retry_prompt, f"the retry prompt must contain the bad reply and an 'Observation: Format error: ...' line; got {retry_prompt!r}"
    u1 = ScriptedModel(["nonsense one", "nonsense two", "nonsense three"])
    resp = mod.ReActModel(u1, max_format_retries=2).complete([{"role": "user", "content": "q"}], tools=[])
    assert len(u1.calls) == 3 and resp.stop_reason == "end_turn" and text_of(resp) == "nonsense three", \
        f"after max_format_retries=2 retries give up and return the last raw reply as text; made {len(u1.calls)} calls, got {resp.content}"
    spy = Spy(ScriptedModel(["bad", "Final Answer: ok"]))
    summed = mod.ReActModel(spy).complete([{"role": "user", "content": "q"}], tools=[])
    for k in ("input_tokens", "output_tokens"):
        assert summed.usage[k] == sum(x.usage[k] for x in spy.replies) > 0, f"the usage of the returned Response must be the SUM over every inner call ({k}); got {summed.usage}"

    # end to end: the same task through a native model and through a text model
    question = "Where is order A-1001?"
    shop1, reg1 = fresh()
    native = ScriptedModel([[tool_use("get_order", {"order_id": "A-1001"}, id="t1")], [tool_use("track_shipment", {"carrier": "UPS"}, id="t2")],
                            "Order A-1001 shipped with UPS and is out for delivery in Leeds."])
    r1 = mod.agent_loop(native, question, reg1)
    shop2, reg2 = fresh()
    texts = ScriptedModel(['Thought: I need the order.\nAction: get_order {"order_id": "A-1001"}\nObservation: it shipped via FedEx',
                           'Thought: The carrier is UPS.\nAction: track_shipment {"carrier": "UPS"}',
                           "Thought: I have it.\nFinal Answer: Order A-1001 shipped with UPS and is out for delivery in Leeds."])
    r2 = mod.agent_loop(mod.ReActModel(texts), question, reg2)
    assert r2.status == "done" and r2.answer == r1.answer, f"the text model must reach the same answer; got {r2.status!r}, {r2.answer!r}"
    assert shop1.executed == shop2.executed == ["get_order", "track_shipment"], f"same tools in the same order; native {shop1.executed}, text {shop2.executed}"
    second = texts.calls[1]["messages"][0]["content"]
    assert '"status": "shipped"' in second and "FedEx" not in second, \
        f"the second prompt must contain the REAL observation from get_order and none of the invented one; got {second!r}"
    assert oracle_pairing(r2.messages), f"history invalid: {mod.check_pairing(r2.messages)}"

    # a text model that sends a bad argument is corrected by the validator, not by the adapter
    shop3, reg3 = fresh()
    bad = ScriptedModel(['Action: issue_refund {"order_id": "A-1001", "amount_cents": "all", "reason": "damaged"}',
                         'Action: issue_refund {"order_id": "A-1001", "amount_cents": 500, "reason": "damaged"}', "Final Answer: Refunded 5.00."])
    r3 = mod.agent_loop(mod.ReActModel(bad), "Refund A-1001 by 5.00, it was damaged", reg3)
    assert r3.status == "done" and shop3.refunds == [("A-1001", 500, "damaged")], f"the invalid call must not run, the corrected one must; refunds {shop3.refunds}"
    assert "Invalid arguments" in bad.calls[1]["messages"][0]["content"], "the model's second prompt should contain the validator's error as the observation"
    return f"text model and native model agree: {r2.answer!r}"


MILESTONES = [
    (1, "Milestone 1: tool schemas and argument validation", m1),
    (2, "Milestone 2: running one tool call, failures as data", m2),
    (3, "Milestone 3: budgets, deadline and repeated-call detection", m3),
    (4, "Milestone 4: the loop and its history", m4),
    (5, "Milestone 5: structured logging and reading a trace", m5),
    (6, "Milestone 6: the same loop with a text-only ReAct model", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 1 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
