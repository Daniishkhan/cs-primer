"""Self-check for Lab 3: An MCP Server & Client.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 3       # only milestone 3
    python3 check.py solution 6 7     # milestone 6, replaying ONLY the random case of seed 7

The server is driven with raw JSON lines and its replies are compared field by field with the
2025-11-25 and 2026-07-28 specifications' shapes. The client is tested against fixture_server.py
(a tiny, separate server, so a bug in your server cannot hide a bug in your client) and then
end to end against your own server through real pipes. No network and no clock; a few seconds.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import io
import json
import os
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
MODULE_PATH = os.path.join(HERE, target + ".py")
FIXTURE = os.path.join(HERE, "fixture_server.py")
results = []
sys.stderr = open(os.devnull, "w")


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


# =============================================================================
# Helpers
# =============================================================================
V, C = "io.modelcontextprotocol/protocolVersion", "io.modelcontextprotocol/clientCapabilities"
SERVER_KEY = "io.modelcontextprotocol/serverInfo"
INIT = {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "1"}}


def line_of(msg):
    return msg if isinstance(msg, str) else json.dumps(msg)


def send(server, msg):
    """Feed one message (dict or raw string) to the server; return the parsed reply or None."""
    out = server.handle_line(line_of(msg))
    if out is None:
        return None
    assert isinstance(out, str) and "\n" not in out, f"handle_line must return ONE line without a newline inside; got {out!r}"
    return json.loads(out)


def req(mid, method, params=None):
    m = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        m["params"] = params
    return m


def note(method, params=None):
    m = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        m["params"] = params
    return m


def ready():
    s = mod.Server()
    r = send(s, req(1, "initialize", INIT))
    assert r and "result" in r, f"initialize should succeed on a new server; got {r}"
    assert send(s, note("notifications/initialized")) is None, "a notification must get no reply"
    return s


class Open(mod.Server):
    """Skips the lifecycle gate, so milestones 3 and 4 can be tested without milestone 2."""

    def process(self, method, params):
        return self.dispatch(method, params)


def expect_error(r, code, what, mid=None):
    assert r is not None and "error" in r and "result" not in r, f"{what}: expected a JSON-RPC error response, got {r}"
    assert r["error"]["code"] == code, f"{what}: expected error code {code}, got {r['error']['code']} ({r['error'].get('message')!r})"
    assert isinstance(r["error"]["message"], str) and r["error"]["message"], f"{what}: an error needs a message string"
    if mid is not False:
        assert r["id"] == mid, f"{what}: the error must carry id {mid!r}, got {r['id']!r}"
    return r["error"]


def expect_result(r, what, mid=None):
    assert r is not None and "result" in r and "error" not in r, f"{what}: expected a success response, got {r}"
    if mid is not False:
        assert r["id"] == mid, f"{what}: the response must carry id {mid!r}, got {r['id']!r}"
    return r["result"]


# =============================================================================
# Milestone 1: messages on a line
# =============================================================================
class Probe(mod.Server):
    """A server whose lifecycle and methods are fixed, so only the envelope is under test."""

    def __init__(self):
        super().__init__()
        self.notes = []

    def process(self, method, params):
        if method == "ping":
            return {}
        if method == "echo":
            return {"params": params}
        if method == "boom":
            raise RuntimeError("kaboom")
        if method == "fail":
            raise mod.RpcError(-32002, "Resource not found", {"uri": "x://y"})
        raise mod.RpcError(-32601, f"Method not found: {method}")

    def on_notification(self, method, params):
        self.notes.append((method, params))


def m1():
    s = Probe()
    out = s.handle_line('{"jsonrpc":"2.0","id":1,"method":"ping"}')
    assert out == '{"jsonrpc":"2.0","id":1,"result":{}}', \
        f"a ping should be answered by exactly '{{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{{}}}}' (compact JSON, no trailing newline); got {out!r}"
    assert s.handle_line('{"jsonrpc":"2.0","id":"abc","method":"ping"}') == '{"jsonrpc":"2.0","id":"abc","result":{}}', "string ids must come back as strings"
    r = send(s, req(2, "echo", {"text": "line one\nline two ✓"}))
    assert expect_result(r, "echo", 2) == {"params": {"text": "line one\nline two ✓"}}, "params must reach process() unchanged"
    # notifications
    n = s.handle_line('{"jsonrpc":"2.0","method":"notifications/initialized"}')
    assert n is None, f"a notification must get no reply at all (not even an error); got {n!r}"
    send(s, note("notifications/progress", {"p": 1}))
    assert s.notes == [("notifications/initialized", {}), ("notifications/progress", {"p": 1})], \
        f"on_notification(method, params) must be called with params {{}} when absent; got {s.notes}"
    assert s.handle_line("") is None and s.handle_line("  \n") is None, "blank lines are skipped without a reply"
    assert s.handle_line('{"jsonrpc":"2.0","id":9,"result":{}}') is None, "a response from the peer needs no reply"
    # errors
    e = expect_error(send(s, req(3, "nope")), -32601, "unknown method", 3)
    e = expect_error(send(s, req(4, "fail")), -32002, "RpcError keeps its code", 4)
    assert e.get("data") == {"uri": "x://y"}, f"an RpcError's data must reach the response; got {e}"
    e = expect_error(send(s, req(5, "boom")), -32603, "an unexpected exception", 5)
    assert "kaboom" not in json.dumps(e), "do not leak exception text to the client in a -32603 message"
    assert send(s, req(6, "ping")) == {"jsonrpc": "2.0", "id": 6, "result": {}}, "the server must keep working after an internal error"
    expect_error(send(s, '{"jsonrpc":"2.0","id":1,"meth'), -32700, "truncated JSON", None)
    expect_error(send(s, "not json at all"), -32700, "not JSON", None)
    bad = [("an empty array", "[]", None), ("a batch", '[{"jsonrpc":"2.0","id":1,"method":"ping"}]', None),
           ("a bare string", '"hello"', None), ("a number", "42", None),
           ("no jsonrpc member", '{"id":1,"method":"ping"}', 1), ("wrong version", '{"jsonrpc":"1.0","id":2,"method":"ping"}', 2),
           ("null id", '{"jsonrpc":"2.0","id":null,"method":"ping"}', None), ("boolean id", '{"jsonrpc":"2.0","id":true,"method":"ping"}', None),
           ("float id", '{"jsonrpc":"2.0","id":1.5,"method":"ping"}', None), ("method not a string", '{"jsonrpc":"2.0","id":5,"method":7}', 5),
           ("neither method nor result", '{"jsonrpc":"2.0","id":6}', 6), ("params an array", '{"jsonrpc":"2.0","id":7,"method":"ping","params":[1]}', 7)]
    for what, text, mid in bad:
        expect_error(send(s, text), -32600, f"invalid request ({what})", mid)
    # builders and encoding
    assert mod.result_message(3, {"a": 1}) == {"jsonrpc": "2.0", "id": 3, "result": {"a": 1}}, "result_message shape"
    assert mod.error_message(3, -32601, "m") == {"jsonrpc": "2.0", "id": 3, "error": {"code": -32601, "message": "m"}}, \
        "error_message without data must have only code and message"
    assert mod.error_message(None, -32700, "p", {"x": 0})["error"]["data"] == {"x": 0}, "error_message keeps data when given"
    assert mod.error_message(None, -32700, "p", 0)["error"].get("data") == 0, "data=0 is data (only None means absent)"
    line = mod.encode({"jsonrpc": "2.0", "id": 1, "result": {"t": "a\nb\u2028c"}})
    assert "\n" not in line and json.loads(line)["result"]["t"] == "a\nb\u2028c", "encode must never contain a raw newline and must round-trip"
    assert mod.encode({"a": [1, 2]}) == '{"a":[1,2]}', "encode uses compact separators"
    for m_, kind in ((req(1, "x"), "request"), (note("x"), "notification"), ({"jsonrpc": "2.0", "id": 1, "result": {}}, "response"),
                     ({"jsonrpc": "2.0", "id": 1, "error": {"code": 1, "message": "m"}}, "response")):
        assert mod.classify(m_) == kind, f"classify({m_}) should be {kind!r}, got {mod.classify(m_)!r}"
    # serve over a text stream
    class Out(io.StringIO):
        flushes = 0

        def flush(self):
            Out.flushes += 1
    inp = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"ping"}\n{"jsonrpc":"2.0","method":"x"}\n\n{bad\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n')
    out = Out()
    mod.serve(Probe(), inp, out)
    lines = out.getvalue().split("\n")
    assert lines[-1] == "" and len(lines) == 4, f"serve must write one newline-terminated line per reply (3 here); got {out.getvalue()!r}"
    got = [json.loads(x) for x in lines[:3]]
    assert [g.get("id") for g in got] == [1, None, 2] and "error" in got[1], f"replies must come in order; got {got}"
    assert Out.flushes >= 3, "flush after every reply: a client reading a pipe would otherwise wait for ever"
    # property: ids are echoed exactly, whatever their type
    for seed in seeds(range(1, 41)):
        rnd = random.Random(seed)
        mid = rnd.choice([rnd.randint(-5, 10**9), "".join(rnd.choice("abcXYZ-_09") for _ in range(rnd.randint(1, 12))), 0, ""])
        r = send(Probe(), req(mid, "ping"))
        assert r is not None and r["id"] == mid and type(r["id"]) is type(mid), \
            f"seed {seed}: id {mid!r} must come back unchanged, got {None if r is None else r['id']!r}"
    # property: every truncation of a valid line is a parse error, never an exception
    valid = json.dumps(req(7, "echo", {"text": "héllo", "n": [1, 2, {"k": None}]}))
    for cut in range(1, len(valid)):
        r = send(Probe(), valid[:cut])
        assert r is not None and r["error"]["code"] == -32700 and r["id"] is None, \
            f"cutting the line at {cut} ({valid[:cut]!r}) should give a -32700 with id null; got {r}"
    return "framing, envelopes, id echo, notifications and every truncation of a valid line behave"


# =============================================================================
# Milestone 2: the handshake
# =============================================================================
class Gated(mod.Server):
    """Real lifecycle, but dispatch is replaced, so only the handshake rules are under test."""

    def dispatch(self, method, params):
        if method == "initialize":
            return self.on_initialize(params)
        if method == "ping":
            return {}
        return {"ok": method}


def m2():
    s = Gated()
    expect_error(send(s, req(1, "tools/list")), -32600, "tools/list before the handshake", 1)
    expect_result(send(s, req(2, "ping")), "ping works before the handshake", 2)
    r = send(s, req(3, "initialize", INIT))
    assert expect_result(r, "initialize", 3) == {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}, "resources": {}},
                                                 "serverInfo": {"name": "orders-desk", "version": "0.1.0"}}, f"initialize result is wrong: {r['result']}"
    e = expect_error(send(s, req(4, "tools/list")), -32600, "between initialize and notifications/initialized", 4)
    assert "initialis" in e["message"].lower() or "initializ" in e["message"].lower(), f"say why it was refused; got {e['message']!r}"
    assert send(s, note("notifications/initialized")) is None
    assert expect_result(send(s, req(5, "tools/list")), "after the handshake", 5) == {"ok": "tools/list"}, "after notifications/initialized requests are served"
    expect_error(send(s, req(6, "initialize", INIT)), -32600, "a second initialize", 6)
    assert expect_result(send(s, req(7, "tools/list")), "still ready after a refused second initialize", 7) == {"ok": "tools/list"}
    # version negotiation
    for asked, want in (("2025-06-18", "2025-06-18"), ("2025-11-25", "2025-11-25"), ("2024-11-05", "2025-11-25"),
                        ("9999-01-01", "2025-11-25"), ("latest", "2025-11-25")):
        r = send(Gated(), req(1, "initialize", {**INIT, "protocolVersion": asked}))
        got = expect_result(r, f"initialize asking for {asked}", 1)["protocolVersion"]
        assert got == want, f"a client asking for {asked!r} should be answered with {want!r} (their version if we speak it, else our newest); got {got!r}"
    # invalid initialize leaves the state alone
    s = Gated()
    for what, p in (("no protocolVersion", {"capabilities": {}, "clientInfo": {}}), ("integer protocolVersion", {**INIT, "protocolVersion": 20251125}),
                    ("capabilities a list", {**INIT, "capabilities": []}), ("no clientInfo", {"protocolVersion": "2025-11-25", "capabilities": {}})):
        expect_error(send(s, req(1, "initialize", p)), -32602, f"initialize with {what}", 1)
    send(s, note("notifications/initialized"))
    expect_error(send(s, req(2, "tools/list")), -32600, "a refused initialize must not start the handshake", 2)
    expect_result(send(s, req(3, "initialize", INIT)), "a good initialize after bad ones", 3)
    # notifications out of order or unknown
    s = Gated()
    send(s, note("notifications/initialized"))
    expect_error(send(s, req(1, "tools/list")), -32600, "notifications/initialized before initialize must do nothing", 1)
    for n in (note("notifications/cancelled", {"requestId": 5}), note("notifications/roots/list_changed"), note("something/else", {"a": 1})):
        assert send(s, n) is None, "unknown notifications are ignored silently"
    assert send(s, req(2, "ping"))["result"] == {}, "the server must survive unknown notifications"
    # property: compare with a plain state machine over random message sequences
    pool = [("initialize", INIT), ("tools/list", None), ("ping", None), ("tools/call", {"name": "x"}), ("initialize", {"protocolVersion": "x"})]
    for seed in seeds(range(1, 31)):
        rnd = random.Random(seed)
        srv, state, trace = Gated(), "new", []
        for step in range(14):
            if rnd.random() < 0.3:
                send(srv, note("notifications/initialized"))
                trace.append("note")
                if state == "initialising":
                    state = "ready"
                continue
            method, params = rnd.choice(pool)
            ok_params = params is None or params is INIT or method != "initialize"
            if method == "initialize":
                want = "ok" if (state == "new" and params is INIT) else ("-32602" if (state == "new") else "-32600")
                if state != "new":
                    want = "-32600"
                if want == "ok":
                    state = "initialising"
            elif method == "ping":
                want = "ok"
            else:
                want = "ok" if state == "ready" else "-32600"
            r = send(srv, req(step, method, params))
            got = "ok" if "result" in r else str(r["error"]["code"])
            trace.append(f"{method}->{got}")
            assert got == want, f"seed {seed}: after {trace[:-1]} a {method} should be {want}, got {got}"
    s1, s2 = Gated(), Gated()
    send(s1, req(1, "initialize", INIT))
    expect_result(send(s2, req(1, "initialize", INIT)), "a second Server instance has its own state", 1)
    return "handshake order, version negotiation, refusals and 30 random message sequences match a plain state machine"


# =============================================================================
# Milestone 3: tools
# =============================================================================
def tool_text(r, what, is_error, mid=False):
    assert not (r and "error" in r) or is_error is None, \
        f"{what}: a mistake the model can fix must come back as a normal result with isError true, not as a JSON-RPC error; got {r}"
    res = expect_result(r, what, mid)
    assert set(res) == {"content", "isError"}, f"{what}: a tool result has exactly 'content' and 'isError'; got keys {sorted(res)}"
    assert res["isError"] is is_error, f"{what}: isError should be {is_error}; got {res['isError']!r} with {res['content']}"
    assert len(res["content"]) == 1 and res["content"][0]["type"] == "text", f"{what}: expect one text block; got {res['content']}"
    return res["content"][0]["text"]


def m3():
    s = Open()
    res = expect_result(send(s, req(1, "tools/list")), "tools/list", 1)
    tools = res["tools"]
    assert list(res) == ["tools"], f"tools/list returns only 'tools' here; got keys {list(res)}"
    assert [t["name"] for t in tools] == ["order_lookup", "orders_search"], f"tools must be listed sorted by name; got {[t['name'] for t in tools]}"
    for t in tools:
        assert re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", t["name"]), f"tool name {t['name']!r} breaks the naming rule"
        assert t["description"] and t["inputSchema"]["type"] == "object", f"{t['name']}: needs a description and an object inputSchema"
        assert "input_schema" not in t, "MCP spells it inputSchema; input_schema is the model-facing shape (milestone 5)"
    json.loads(json.dumps(tools))
    tools[0]["name"] = "mutated"
    assert [t["name"] for t in mod.TOOLS] == ["order_lookup", "orders_search"], "do not hand out (and let callers mutate) the TOOLS list itself"
    call = lambda mid, name, arguments=None: send(s, req(mid, "tools/call", {"name": name} if arguments is None else {"name": name, "arguments": arguments}))
    assert tool_text(call(2, "order_lookup", {"order_id": "A-1001"}), "lookup", False, 2) == "A-1001: shipped, 4250 cents, carrier UPS"
    assert tool_text(call(3, "order_lookup", {"order_id": "A-1002"}), "lookup", False, 3) == "A-1002: processing, 1999 cents, carrier none yet"
    t = tool_text(call(4, "orders_search", {"status": "shipped", "limit": 2}), "search with limit", False, 4)
    assert t.splitlines() == ["A-1001: shipped, 4250 cents, carrier UPS", "A-1004: shipped, 800 cents, carrier UPS"], f"search output wrong: {t!r}"
    assert len(tool_text(call(5, "orders_search", {"status": "shipped"}), "default limit", False, 5).splitlines()) == 3, "limit defaults to 3"
    assert tool_text(call(6, "orders_search", {"status": "cancelled"}), "no match", False, 6) == "No cancelled orders.", "no hits is a normal answer, not an error"
    # errors the model can fix: isError true, a message that says how
    t = tool_text(call(7, "order_lookup", {}), "missing argument", True, 7)
    assert "order_id" in t, f"name the missing argument; got {t!r}"
    t = tool_text(call(8, "orders_search", {"status": "shipped", "limit": "many"}), "wrong type", True, 8)
    assert "limit" in t and "integer" in t, f"say which argument and what type was expected; got {t!r}"
    t = tool_text(call(9, "orders_search", {"status": "lost"}), "not in the enum", True, 9)
    assert "shipped" in t and "processing" in t, f"list the valid values; got {t!r}"
    t = tool_text(call(10, "order_lookup", {"order_id": "Z-9"}), "bad id", True, 10)
    assert "Z-9" in t, f"an invalid argument message should echo the bad value; got {t!r}"
    t = tool_text(call(11, "order_lookup", {"order_id": "A-9999"}), "unknown order", True, 11)
    assert "A-9999" in t and "orders_search" in t, f"the ToolError text must reach the model verbatim; got {t!r}"
    t = tool_text(call(12, "orders_search"), "arguments omitted", True, 12)
    assert "status" in t, f"absent arguments are treated as {{}}; the message should name 'status'; got {t!r}"
    # faults of the protocol: JSON-RPC errors
    e = expect_error(call(13, "no_such_tool", {}), -32602, "unknown tool", 13)
    assert "no_such_tool" in e["message"], f"the message should name the tool; got {e['message']!r}"
    expect_error(send(s, req(14, "tools/call", {})), -32602, "no name", 14)
    expect_error(send(s, req(15, "tools/call", {"name": 7})), -32602, "name not a string", 15)
    expect_error(send(s, req(16, "tools/call", {"name": "order_lookup", "arguments": ["A-1001"]})), -32602, "arguments not an object", 16)
    # a crash inside a tool, and a ToolError raised by a tool
    saved = dict(mod.TOOL_FUNCS)
    try:
        def boom(a):
            raise ZeroDivisionError("inside the tool")
        def refuse(a):
            raise mod.ToolError("Try again with a smaller limit.")
        mod.TOOL_FUNCS["orders_search"] = boom
        expect_error(call(17, "orders_search", {"status": "shipped"}), -32603, "a bug inside a tool", 17)
        mod.TOOL_FUNCS["orders_search"] = refuse
        assert tool_text(call(18, "orders_search", {"status": "shipped"}), "ToolError", True, 18) == "Try again with a smaller limit."
    finally:
        mod.TOOL_FUNCS.clear()
        mod.TOOL_FUNCS.update(saved)
    # property: random arguments never crash the server and are classified correctly
    for seed in seeds(range(1, 61)):
        rnd = random.Random(seed)
        status = rnd.choice(["shipped", "processing", "delivered", "cancelled", "lost", 7])
        limit = rnd.choice([None, None, rnd.randint(-3, 14), "5", 2.5, True])
        a = {"status": status}
        if limit is not None:
            a["limit"] = limit
        valid = status in ("shipped", "processing", "delivered", "cancelled") and (limit is None or (type(limit) is int and 1 <= limit <= 10))
        r = send(s, req(seed, "tools/call", {"name": "orders_search", "arguments": a}))
        assert r is not None and "result" in r, f"seed {seed}: arguments {a} must give a normal result (isError true if invalid), never a JSON-RPC error; got {r}"
        assert r["result"]["isError"] is (not valid), f"seed {seed}: arguments {a} are {'valid' if valid else 'invalid'} but isError is {r['result']['isError']}"
        if valid:
            n = sum(1 for o in mod.ORDERS.values() if o["status"] == status)
            want = min(limit or 3, n)
            got = len([x for x in r["result"]["content"][0]["text"].splitlines() if x.startswith("A-")])
            assert got == want, f"seed {seed}: expected {want} orders for {a}, got {got}"
    return "list, call, both error routes, a crashing tool, and 60 random argument sets behave"


# =============================================================================
# Milestone 4: resources, and an error-code sweep
# =============================================================================
def m4():
    s = Open()
    res = expect_result(send(s, req(1, "resources/list")), "resources/list", 1)
    rs = res["resources"]
    assert [r["uri"] for r in rs] == [f"order://{i}" for i in mod.ORDERS], f"one resource per order, in ORDERS order; got {[r['uri'] for r in rs]}"
    assert rs[0] == {"uri": "order://A-1001", "name": "order-A-1001", "title": "Order A-1001", "mimeType": "text/plain"}, f"first resource is wrong: {rs[0]}"
    r = expect_result(send(s, req(2, "resources/read", {"uri": "order://A-1002"})), "read", 2)
    assert r == {"contents": [{"uri": "order://A-1002", "mimeType": "text/plain", "text": "A-1002: processing, 1999 cents, carrier none yet"}]}, f"read result is wrong: {r}"
    e = expect_error(send(s, req(3, "resources/read", {"uri": "order://Z-9"})), -32002, "unknown order", 3)
    assert e.get("data") == {"uri": "order://Z-9"}, f"-32002 must carry the uri in data; got {e.get('data')}"
    expect_error(send(s, req(4, "resources/read", {"uri": "https://example.com/a"})), -32002, "a uri we do not serve", 4)
    expect_error(send(s, req(5, "resources/read", {"uri": "order://"})), -32002, "an empty order id", 5)
    expect_error(send(s, req(6, "resources/read", {})), -32602, "no uri", 6)
    expect_error(send(s, req(7, "resources/read", {"uri": 5})), -32602, "uri not a string", 7)
    for item in rs:                                           # resources and the lookup tool tell the same story
        text = send(s, req(8, "resources/read", {"uri": item["uri"]}))["result"]["contents"][0]["text"]
        tool = send(s, req(9, "tools/call", {"name": "order_lookup", "arguments": {"order_id": item["uri"][8:]}}))["result"]["content"][0]["text"]
        assert text == tool, f"the resource {item['uri']} and order_lookup disagree: {text!r} vs {tool!r}"
    # the sweep: a real, handshaken server and every kind of mistake
    srv = ready()
    sweep = [
        ("garbage", "}{", -32700), ("truncated", '{"jsonrpc":"2.0","id":2,"meth', -32700),
        ("batch", '[{"jsonrpc":"2.0","id":1,"method":"ping"}]', -32600), ("no jsonrpc", '{"id":3,"method":"ping"}', -32600),
        ("null id", '{"jsonrpc":"2.0","id":null,"method":"ping"}', -32600),
        ("unknown method", req(4, "prompts/list"), -32601), ("unknown method 2", req(5, "completion/complete", {}), -32601),
        ("unknown tool", req(6, "tools/call", {"name": "refund_order", "arguments": {}}), -32602),
        ("tools/call without name", req(7, "tools/call", {}), -32602), ("resource missing", req(8, "resources/read", {"uri": "order://A-0000"}), -32002),
        ("resource uri missing", req(9, "resources/read", {}), -32602),
        ("initialize again", req(10, "initialize", INIT), -32600),
        ("model's mistake", req(11, "tools/call", {"name": "orders_search", "arguments": {"status": "shipped", "limit": 99}}), "isError"),
        ("model's other mistake", req(12, "tools/call", {"name": "order_lookup", "arguments": {"order_id": 1001}}), "isError"),
        ("fine", req(13, "tools/call", {"name": "order_lookup", "arguments": {"order_id": "A-1003"}}), "ok"),
    ]
    rows = []
    for what, m_, want in sweep:
        r = send(srv, m_)
        assert r is not None and r["jsonrpc"] == "2.0" and ("result" in r) != ("error" in r), f"{what}: exactly one of result and error, with jsonrpc '2.0'; got {r}"
        if isinstance(want, int):
            expect_error(r, want, what, False)
            got = str(want)
        else:
            assert "result" in r, f"{what}: a mistake the model can fix is a normal result with isError true, not a JSON-RPC error; got {r}"
            assert r["result"]["isError"] is (want == "isError"), f"{what}: isError should be {want == 'isError'}"
            got = want
        rows.append(f"{what:24s}{got}")
    return "every kind of mistake gets the right code:\n" + "\n".join(rows[:4]) + "\n..."


# =============================================================================
# Milestone 5: the client
# =============================================================================
def fixture(mode=""):
    return mod.McpClient([sys.executable, FIXTURE] + ([mode] if mode else []))


def m5():
    c = fixture()
    try:
        info = c.connect()
        assert info["protocolVersion"] == "2025-11-25" and info["serverInfo"]["name"] == "fixture", f"connect() returns the initialize result; got {info}"
        sent = [json.loads(t[4:]) for t in c.trace if t.startswith("--> ")]
        assert [m.get("method") for m in sent] == ["initialize", "notifications/initialized"], f"connect sends initialize, then notifications/initialized; sent {[m.get('method') for m in sent]}"
        assert sent[0]["id"] == 1 and sent[0]["params"]["protocolVersion"] == "2025-11-25" and "clientInfo" in sent[0]["params"] \
            and sent[0]["params"]["capabilities"] == {}, f"initialize params are wrong: {sent[0]}"
        assert "id" not in sent[1], "notifications/initialized is a notification: no id"
        assert [t[:4] for t in c.trace] == ["--> ", "<-- ", "--> "], f"the notification gets no reply and the client must not wait for one; trace {c.trace}"
        assert c.request("ping") == {} and c.request("ping") == {}, "request() returns the result object"
        ids = [json.loads(t[4:])["id"] for t in c.trace if t.startswith("--> ") and "id" in json.loads(t[4:])]
        assert ids == [1, 2, 3], f"ids must be 1, 2, 3 ...; got {ids}"
        tools = c.list_tools()
        assert [t["name"] for t in tools] == ["echo"], f"list_tools returns the tool definitions; got {tools}"
        assert c.call_tool("echo", {"text": "héllo\nwörld"}) == ("héllo\nwörld", False), "call_tool returns (text, isError)"
        text, is_error = c.call_tool("echo", {})
        assert (text, is_error) == ("text is required", True), f"a tool failure is data, not an exception; got {(text, is_error)}"
        try:
            c.call_tool("nope", {})
            raise AssertionError("a JSON-RPC error response must raise McpError")
        except mod.McpError as e:
            assert e.code == -32602 and "nope" in e.message and e.data is None, f"McpError must carry code, message and data; got {e.code}, {e.message!r}, {e.data!r}"
        try:
            c.request("resources/list")
            raise AssertionError("method not found must raise McpError")
        except mod.McpError as e:
            assert e.code == -32601
        assert c.request("ping") == {}, "the client must still work after an McpError"
        err = c.close()
        assert c.proc.poll() == 0, f"close() must close stdin and wait; the fixture exits 0 when its input ends (exit code {c.proc.poll()})"
        assert "stdin closed after" in err, f"close() returns the server's stderr; got {err!r}"
    finally:
        if c.proc.poll() is None:
            c.proc.kill()
    # the failure modes
    for mode, exc, needle in (("noisy", ValueError, "non-JSON"), ("wrongid", ValueError, "id"), ("hangup", ConnectionError, ""), ("oldversion", ValueError, "1999-01-01")):
        c = fixture(mode)
        try:
            c.connect()
            raise AssertionError(f"mode {mode}: connect() should have raised {exc.__name__}")
        except exc as e:
            assert needle in str(e), f"mode {mode}: the message should mention {needle!r}; got {str(e)!r}"
        except AssertionError:
            raise
        except Exception as e:
            raise AssertionError(f"mode {mode}: expected {exc.__name__}, got {type(e).__name__}: {e}")
        finally:
            c.proc.kill()
            c.proc.wait()
    # the bridge to a model (chapter 7's host)
    from llm import ScriptedModel, text_of, tool_calls, tool_use
    c = fixture()
    try:
        c.connect()
        mt = mod.to_model_tools(c.list_tools())
        assert mt == [{"name": "echo", "description": "Return the text it is given.", "input_schema": c.list_tools()[0]["inputSchema"]}], f"to_model_tools shape: {mt}"
        model = ScriptedModel([[tool_use("echo", {"text": "ping"}, id="t1")], [tool_use("nope", {}, id="t2")], "done"])
        msgs = [{"role": "user", "content": "go"}]
        seen = []
        for _ in range(5):
            rep = model.complete(msgs, tools=mt)
            msgs.append(rep.as_message())
            calls = tool_calls(rep)
            if not calls:
                break
            results = [mod.run_tool_use(c, b) for b in calls]
            seen.append(results[0])
            msgs.append({"role": "user", "content": results})
        assert text_of(rep) == "done" and len(seen) == 2, "the loop should run two tool calls and then finish"
        assert seen[0] == {"type": "tool_result", "tool_use_id": "t1", "content": "ping", "is_error": False}, f"a good call becomes a plain tool_result; got {seen[0]}"
        assert seen[1]["tool_use_id"] == "t2" and seen[1]["is_error"] is True and seen[1]["content"].startswith("MCP error -32602: "), \
            f"a protocol error becomes an is_error tool_result starting 'MCP error -32602: '; got {seen[1]}"
        c.close()
    finally:
        if c.proc.poll() is None:
            c.proc.kill()
    # end to end: your client against YOUR server, over real pipes
    c = mod.McpClient([sys.executable, MODULE_PATH])
    try:
        try:
            info = c.connect()
            assert info["serverInfo"]["name"] == "orders-desk" and info["protocolVersion"] == "2025-11-25", f"end to end: unexpected initialize result {info}"
            assert [t["name"] for t in c.list_tools()] == ["order_lookup", "orders_search"], "end to end: list_tools"
            assert c.call_tool("order_lookup", {"order_id": "A-1001"}) == ("A-1001: shipped, 4250 cents, carrier UPS", False), "end to end: call_tool"
            assert c.call_tool("order_lookup", {"order_id": "A-9999"})[1] is True, "end to end: a ToolError is isError"
            for method, params, code in (("tools/call", {"name": "x", "arguments": {}}, -32602), ("resources/read", {"uri": "order://Z"}, -32002), ("nope", None, -32601)):
                try:
                    c.request(method, params)
                    raise AssertionError(f"end to end: {method} should raise McpError {code}")
                except mod.McpError as e:
                    assert e.code == code, f"end to end: {method} gave {e.code}, expected {code}"
        except (ConnectionError, BrokenPipeError):
            err = c.close()
            if "NotImplementedError" in err:
                raise NotImplementedError("the end-to-end run needs your server (milestones 1 to 4)")
            raise AssertionError("end to end: your server stopped answering; its stderr says:\n" + err[-600:])
        except ValueError as e:
            if "non-JSON" in str(e):
                raise AssertionError(f"end to end: your server wrote something that is not a message to stdout ({e}). Log to stderr.")
            raise
        err = c.close()
        assert c.proc.returncode == 0, f"end to end: your server should exit 0 when its stdin closes; got {c.proc.returncode}. stderr: {err[-300:]}"
    finally:
        if c.proc.poll() is None:
            c.proc.kill()
    return "handshake, ids, errors, three failure modes, the model bridge, and a real end-to-end run pass"


# =============================================================================
# Milestone 6: the stateless 2026-07-28 style
# =============================================================================
def mreq(mid, method, params=None, version="2026-07-28", caps=None, **extra):
    meta = {V: version, C: {} if caps is None else caps, **extra}
    meta = {k: v for k, v in meta.items() if v is not None}
    return req(mid, method, {**(params or {}), "_meta": meta})


def m6():
    SI = {"name": "orders-desk", "version": "0.1.0"}
    s = mod.Server()                                           # a brand-new server: no handshake at all
    r = expect_result(send(s, mreq(1, "server/discover", extra={"io.modelcontextprotocol/clientInfo": {"name": "c", "version": "1"}})), "server/discover", 1)
    assert r == {"resultType": "complete", "supportedVersions": ["2026-07-28"], "capabilities": {"tools": {}, "resources": {}},
                 "_meta": {SERVER_KEY: SI}, "ttlMs": 3_600_000, "cacheScope": "public"}, f"server/discover result is wrong: {r}"
    r = expect_result(send(s, mreq(2, "tools/list")), "tools/list", 2)
    legacy = expect_result(send(ready(), req(1, "tools/list")), "legacy tools/list", 1)
    assert r["tools"] == legacy["tools"] and r["resultType"] == "complete" and r["_meta"] == {SERVER_KEY: SI}, f"modern tools/list = legacy tools plus resultType and _meta; got keys {sorted(r)}"
    assert isinstance(r["ttlMs"], int) and r["ttlMs"] > 0 and r["cacheScope"] in ("public", "private"), "list results need ttlMs (int, ms) and cacheScope"
    r = expect_result(send(s, mreq(3, "tools/call", {"name": "order_lookup", "arguments": {"order_id": "A-1001"}})), "tools/call", 3)
    assert r["resultType"] == "complete" and r["isError"] is False and r["content"][0]["text"] == "A-1001: shipped, 4250 cents, carrier UPS", f"tools/call: {r}"
    assert "ttlMs" not in r, "tools/call results are not cacheable: no ttlMs"
    r = expect_result(send(s, mreq(4, "tools/call", {"name": "order_lookup", "arguments": {"order_id": "A-9999"}})), "unknown order", 4)
    assert r["isError"] is True and r["resultType"] == "complete", "a tool failure is still a complete result with isError"
    expect_error(send(s, mreq(5, "tools/call", {"name": "nope", "arguments": {}})), -32602, "unknown tool", 5)
    r = expect_result(send(s, mreq(6, "resources/list")), "resources/list", 6)
    assert len(r["resources"]) == 5 and "ttlMs" in r and "cacheScope" in r, "resources/list is cacheable"
    r = expect_result(send(s, mreq(7, "resources/read", {"uri": "order://A-1003"})), "resources/read", 7)
    assert r["contents"][0]["text"] == "A-1003: delivered, 12900 cents, carrier DHL" and "ttlMs" in r and r["cacheScope"] in ("public", "private"), f"resources/read: {r}"
    e = expect_error(send(s, mreq(8, "resources/read", {"uri": "order://Z-9"})), -32602, "not found is -32602 in this era (it was -32002)", 8)
    assert e.get("data") == {"uri": "order://Z-9"}, f"keep the uri in data; got {e.get('data')}"
    # the required fields
    e = expect_error(send(s, req(9, "tools/list", {"_meta": {V: "2026-07-28"}})), -32602, "capabilities missing", 9)
    e = expect_error(send(s, req(10, "tools/list", {"_meta": {C: {}}})), -32602, "version missing", 10)
    expect_error(send(s, mreq(11, "tools/list", version=20260728)), -32602, "version not a string", 11)
    for bad in ("2025-11-25", "1900-01-01", "2026-07-29"):
        e = expect_error(send(s, mreq(12, "tools/list", version=bad)), -32022, f"version {bad}", 12)
        assert e.get("data") == {"supported": ["2026-07-28"], "requested": bad}, f"-32022 must list what you support and what was asked; got {e.get('data')}"
    for m_ in ("ping", "initialize", "logging/setLevel"):
        expect_error(send(s, mreq(13, m_, INIT if m_ == "initialize" else None)), -32601, f"{m_} does not exist in the modern era", 13)
    r = expect_result(send(s, mreq(14, "tools/list", extra={"traceparent": "00-0af7651916cd43dd8448eb211c80319c-00f067aa0ba902b7-01", "progressToken": "p1"})), "extra _meta keys", 14)
    assert C not in json.dumps(r), "never echo the client's capabilities back"
    # statelessness: the answer depends on the request alone
    pool = [mreq(0, "server/discover"), mreq(0, "tools/list"), mreq(0, "tools/call", {"name": "orders_search", "arguments": {"status": "shipped", "limit": 2}}),
            mreq(0, "tools/call", {"name": "order_lookup", "arguments": {"order_id": "Z-1"}}), mreq(0, "resources/list"),
            mreq(0, "resources/read", {"uri": "order://A-1005"}), mreq(0, "resources/read", {"uri": "order://nope"}),
            mreq(0, "tools/call", {"name": "ghost"}), mreq(0, "tools/list", version="2025-11-25"), mreq(0, "ping")]
    for seed in seeds(range(1, 21)):
        rnd = random.Random(seed)
        seq = [dict(rnd.choice(pool), id=i) for i in range(1, 25)]
        one = mod.Server()
        a = [send(one, m_) for m_ in seq]                                   # one long-lived server
        b = [send(mod.Server(), m_) for m_ in seq]                          # a brand-new server per request
        shuffled = list(range(len(seq)))
        rnd.shuffle(shuffled)
        other, d = mod.Server(), {}
        for i in shuffled:                                                  # another server, another order
            d[i] = send(other, seq[i])
            if rnd.random() < 0.2:                                          # with a legacy handshake thrown in
                send(other, req(999, "initialize", INIT))
        for i, m_ in enumerate(seq):
            assert a[i] == b[i] == d[i], f"seed {seed}: the reply to {m_['method']} (#{i}) depended on other traffic or on the server instance:\n  long-lived {a[i]}\n  fresh      {b[i]}\n  shuffled   {d[i]}"
    # the two eras do not leak into each other
    s = mod.Server()
    send(s, mreq(1, "tools/list"))
    expect_error(send(s, req(2, "tools/list")), -32600, "a modern request must not complete a legacy handshake", 2)
    expect_result(send(s, req(3, "initialize", INIT)), "a legacy handshake after modern traffic", 3)
    send(s, note("notifications/initialized"))
    expect_result(send(s, req(4, "tools/list")), "legacy session works", 4)
    expect_result(send(s, mreq(5, "tools/list")), "and modern requests still work beside it", 5)
    # over real pipes, the way a stdio client probes (server/discover first, then the legacy fallback if it fails)
    p = subprocess.Popen([sys.executable, MODULE_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    try:
        def talk(m_):
            p.stdin.write(line_of(m_) + "\n")
            p.stdin.flush()
            return json.loads(p.stdout.readline())
        assert "result" in talk(mreq(1, "server/discover")), "the stdio probe: server/discover must succeed on a fresh process"
        assert talk(mreq(2, "tools/call", {"name": "order_lookup", "arguments": {"order_id": "A-1004"}}))["result"]["content"][0]["text"].startswith("A-1004: shipped"), "a modern call over a real pipe"
        assert "result" in talk(req(3, "initialize", INIT)), "the same process still answers a legacy initialize"
        p.stdin.close()
        p.wait(timeout=5)
    finally:
        if p.poll() is None:
            p.kill()
        p.stdout.close()
        p.stderr.close()
    return "stateless requests, version errors, caching hints, era isolation and 20 random request mixes agree"


MILESTONES = [
    (1, "Milestone 1: messages on a line, framing and error envelopes", m1),
    (2, "Milestone 2: the handshake and version negotiation", m2),
    (3, "Milestone 3: tools, and the two kinds of error", m3),
    (4, "Milestone 4: resources, and an error-code sweep", m4),
    (5, "Milestone 5: the client, and the bridge to a model", m5),
    (6, "Milestone 6: the stateless 2026-07-28 style", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 3 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
