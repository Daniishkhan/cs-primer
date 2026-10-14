"""Lab 3 solution: an MCP server and client, by hand.

The server speaks JSON-RPC 2.0 over stdio, one JSON object per line. It serves a small
order desk (the same orders as Lab 1) as two tools and a set of resources, in two eras of the
protocol at once: the handshake-based revisions (2025-06-18 and 2025-11-25) and the stateless
revision 2026-07-28, where every request carries its own version and capabilities.

Run it as a server:   python3 solution.py          (reads stdin, writes stdout, logs to stderr)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from llm import tool_result

# =============================================================================
# Given: constants
# =============================================================================
LEGACY_VERSIONS = ["2025-11-25", "2025-06-18"]       # handshake era, newest first
MODERN_VERSIONS = ["2026-07-28"]                     # stateless era
K_VERSION = "io.modelcontextprotocol/protocolVersion"
K_CAPS = "io.modelcontextprotocol/clientCapabilities"
K_SERVER = "io.modelcontextprotocol/serverInfo"
SERVER_INFO = {"name": "orders-desk", "version": "0.1.0"}
CAPABILITIES = {"tools": {}, "resources": {}}

# JSON-RPC error codes used in this lab
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603
RESOURCE_NOT_FOUND = -32002                          # 2025-11-25 and earlier
UNSUPPORTED_VERSION = -32022                         # 2026-07-28


def log(*a: Any) -> None:
    """Diagnostics go to STDERR. STDOUT is the protocol channel and must carry only messages."""
    print(*a, file=sys.stderr, flush=True)


class RpcError(Exception):
    """Raise inside a handler to send a JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Any = None, id: Any = None):
        super().__init__(message)
        self.code, self.message, self.data, self.id = code, message, data, id


class ToolError(Exception):
    """Raise inside a tool for a failure the MODEL should read (becomes isError: true)."""


# =============================================================================
# Given: the order desk, its tools and a small argument checker
# =============================================================================
ORDERS = {
    "A-1001": {"status": "shipped", "total_cents": 4250, "carrier": "UPS"},
    "A-1002": {"status": "processing", "total_cents": 1999, "carrier": None},
    "A-1003": {"status": "delivered", "total_cents": 12900, "carrier": "DHL"},
    "A-1004": {"status": "shipped", "total_cents": 800, "carrier": "UPS"},
    "A-1005": {"status": "shipped", "total_cents": 2300, "carrier": "DHL"},
}
STATUSES = ["shipped", "processing", "delivered", "cancelled"]


def describe_order(order_id: str) -> str:
    o = ORDERS[order_id]
    return f"{order_id}: {o['status']}, {o['total_cents']} cents, carrier {o['carrier'] or 'none yet'}"


def order_lookup(args: Dict[str, Any]) -> str:
    oid = args["order_id"]
    if oid not in ORDERS:
        raise ToolError(f"No order {oid!r}. Ids look like A-1001; use orders_search to find one.")
    return describe_order(oid)


def orders_search(args: Dict[str, Any]) -> str:
    status, limit = args["status"], args.get("limit", 3)
    hits = [describe_order(i) for i, o in ORDERS.items() if o["status"] == status][:limit]
    return "\n".join(hits) or f"No {status} orders."


TOOLS: List[Dict[str, Any]] = [
    {"name": "order_lookup",
     "description": "Look up one order by id. Returns its status, total in cents and carrier.",
     "inputSchema": {"type": "object", "properties": {
         "order_id": {"type": "string", "pattern": r"^A-\d{4}$", "description": "An order id such as A-1001."}},
         "required": ["order_id"], "additionalProperties": False}},
    {"name": "orders_search",
     "description": "List orders with a given status, up to `limit` of them (1 to 10, default 3).",
     "inputSchema": {"type": "object", "properties": {
         "status": {"type": "string", "enum": STATUSES, "description": "Which status to list."},
         "limit": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Maximum orders, default 3."}},
         "required": ["status"], "additionalProperties": False}},
]
TOOL_FUNCS = {"order_lookup": order_lookup, "orders_search": orders_search}


def check_arguments(schema: Dict[str, Any], args: Dict[str, Any]) -> List[str]:
    """The problems with `args` against a (small subset of) JSON Schema, as sentences a model can act on."""
    problems = []
    props = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in args:
            problems.append(f"missing required argument '{name}'")
    for name, value in args.items():
        spec = props.get(name)
        if spec is None:
            if schema.get("additionalProperties") is False:
                problems.append(f"unexpected argument '{name}'")
            continue
        kind = spec.get("type")
        if kind == "string" and not isinstance(value, str):
            problems.append(f"'{name}' must be a string, got {type(value).__name__}")
        elif kind == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            problems.append(f"'{name}' must be an integer, got {type(value).__name__}")
        elif "enum" in spec and value not in spec["enum"]:
            problems.append(f"'{name}' must be one of {', '.join(spec['enum'])}; got {value!r}")
        elif kind == "integer" and not spec.get("minimum", value) <= value <= spec.get("maximum", value):
            problems.append(f"'{name}' must be between {spec.get('minimum')} and {spec.get('maximum')}; got {value}")
        elif "pattern" in spec and not re.search(spec["pattern"], value):
            problems.append(f"'{name}' must match {spec['pattern']}; got {value!r}")
    return problems


# =============================================================================
# Milestone 1: messages on a line
# =============================================================================
def result_message(id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    """A JSON-RPC success response."""
    return {"jsonrpc": "2.0", "id": id, "result": result}


def error_message(id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    """A JSON-RPC error response; `data` is included only when it is not None."""
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": err}


def encode(msg: Dict[str, Any]) -> str:
    """One message as one line: compact JSON, and no newline inside (json.dumps escapes them)."""
    return json.dumps(msg, separators=(",", ":"))


def parse_line(line: str) -> Dict[str, Any]:
    """Parse one line into a message dict, or raise RpcError.

    -32700 if the line is not JSON. -32600 if it is JSON but not a valid single message: an array
    (MCP does not allow batches), not an object, "jsonrpc" not "2.0", a "method" that is not a
    string, an "id" that is null, boolean, float or anything but a string or integer, "params"
    that is not an object, or an object with neither "method" nor "result" nor "error".
    When the id could be read, put it on the RpcError (id=...), otherwise leave it None.
    """
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        raise RpcError(PARSE_ERROR, "Parse error") from None
    if isinstance(msg, list):
        raise RpcError(INVALID_REQUEST, "Invalid Request: batches are not supported")
    if not isinstance(msg, dict):
        raise RpcError(INVALID_REQUEST, "Invalid Request: a message must be a JSON object")
    mid = msg.get("id")
    readable = mid if isinstance(mid, (str, int)) and not isinstance(mid, bool) else None
    if msg.get("jsonrpc") != "2.0":
        raise RpcError(INVALID_REQUEST, 'Invalid Request: "jsonrpc" must be "2.0"', id=readable)
    if "id" in msg and readable is None:
        raise RpcError(INVALID_REQUEST, "Invalid Request: id must be a string or an integer")
    if "method" in msg:
        if not isinstance(msg["method"], str):
            raise RpcError(INVALID_REQUEST, "Invalid Request: method must be a string", id=readable)
        if "params" in msg and not isinstance(msg["params"], dict):
            raise RpcError(INVALID_REQUEST, "Invalid Request: params must be an object", id=readable)
    elif "result" not in msg and "error" not in msg:
        raise RpcError(INVALID_REQUEST, "Invalid Request: no method", id=readable)
    return msg


def classify(msg: Dict[str, Any]) -> str:
    """'request' (method and id), 'notification' (method, no id) or 'response' (no method)."""
    if "method" not in msg:
        return "response"
    return "request" if "id" in msg else "notification"


def serve(server: "Server", infile, outfile) -> None:
    """The stdio transport: one reply line per request line, flushed at once, until input ends."""
    for line in infile:
        reply = server.handle_line(line)
        if reply is not None:
            outfile.write(reply + "\n")
            outfile.flush()


# Given: freshness hints for the modern era: method -> (ttlMs, cacheScope)
CACHE = {"server/discover": (3_600_000, "public"), "tools/list": (60_000, "public"),
         "resources/list": (60_000, "public"), "resources/read": (5_000, "private")}


# =============================================================================
# The server
# =============================================================================
class Server:
    def __init__(self) -> None:
        self.state = "new"                  # new -> initialising -> ready (legacy handshake only)
        self.client_info: Optional[dict] = None

    # ---- milestone 1: the envelope ------------------------------------------
    def handle_line(self, line: str) -> Optional[str]:
        """One input line in, one output line (or None) out. Never raises.

        Blank lines and client responses get no reply. Notifications go to on_notification and
        get no reply. Requests go to process(method, params): its dict becomes a success response,
        an RpcError an error response (keeping code, message and data), and any other exception a
        -32603 "Internal error" response, with the server still alive for the next line.
        """
        if not line.strip():
            return None
        try:
            msg = parse_line(line)
        except RpcError as e:
            return encode(error_message(e.id, e.code, e.message, e.data))
        kind = classify(msg)
        if kind == "response":
            return None
        method, params = msg["method"], msg.get("params") or {}
        if kind == "notification":
            try:
                self.on_notification(method, params)
            except Exception as e:                   # a notification has nobody to tell
                log("error in notification", method, repr(e))
            return None
        try:
            return encode(result_message(msg["id"], self.process(method, params)))
        except RpcError as e:
            return encode(error_message(msg["id"], e.code, e.message, e.data))
        except Exception as e:
            log("internal error in", method, repr(e))
            return encode(error_message(msg["id"], INTERNAL_ERROR, "Internal error"))

    # ---- milestone 2: the handshake -----------------------------------------
    def on_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate, negotiate and answer `initialize`.

        protocolVersion must be a string, capabilities and clientInfo objects, else -32602 (and no
        state change). Answer with the client's version if it is in LEGACY_VERSIONS, otherwise the
        newest one. Result: protocolVersion, capabilities (CAPABILITIES), serverInfo (SERVER_INFO).
        """
        ver = params.get("protocolVersion")
        if not isinstance(ver, str) or not isinstance(params.get("capabilities"), dict) \
                or not isinstance(params.get("clientInfo"), dict):
            raise RpcError(INVALID_PARAMS, "initialize needs protocolVersion, capabilities and clientInfo")
        self.client_info = params["clientInfo"]
        self.state = "initialising"
        return {"protocolVersion": ver if ver in LEGACY_VERSIONS else LEGACY_VERSIONS[0],
                "capabilities": CAPABILITIES, "serverInfo": SERVER_INFO}

    def on_notification(self, method: str, params: Dict[str, Any]) -> None:
        """notifications/initialized completes the handshake (only after a good initialize).
        Every other notification, known or not, is ignored."""
        if method == "notifications/initialized" and self.state == "initialising":
            self.state = "ready"

    def process(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the lifecycle rules, then dispatch.

        Modern requests (milestone 6) are handled first. For handshake-era requests: `initialize`
        when already initialised is -32600 "Already initialised"; anything except `initialize` and
        `ping` before the handshake has completed is -32600 "Server not initialised ...".
        """
        meta = params.get("_meta")
        if isinstance(meta, dict) and (K_VERSION in meta or K_CAPS in meta):
            return self.process_modern(method, params, meta)
        if method == "initialize" and self.state != "new":
            raise RpcError(INVALID_REQUEST, "Already initialised")
        if method not in ("initialize", "ping") and self.state != "ready":
            raise RpcError(INVALID_REQUEST, "Server not initialised: send initialize, then notifications/initialized")
        return self.dispatch(method, params)

    def dispatch(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Given: the method table. Unknown methods are -32601."""
        handlers = {"initialize": self.on_initialize, "ping": lambda p: {},
                    "tools/list": self.list_tools, "tools/call": self.call_tool,
                    "resources/list": self.list_resources, "resources/read": self.read_resource}
        handler = handlers.get(method)
        if handler is None:
            raise RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
        return handler(params)

    # ---- milestone 3: tools ----------------------------------------------------
    def list_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """{"tools": [...]}: TOOLS sorted by name (a stable order helps caches)."""
        return {"tools": sorted(TOOLS, key=lambda t: t["name"])}

    def call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a tool. Protocol faults are RpcErrors (-32602: name missing or not a string, unknown
        tool, arguments not an object). Everything the model can fix is a normal result with
        isError true: arguments that fail check_arguments, or a ToolError from the tool. Any other
        exception from the tool propagates (it becomes -32603). Look tools up in TOOL_FUNCS at call
        time. Success: {"content": [{"type": "text", "text": ...}], "isError": False}.
        """
        name = params.get("name")
        if not isinstance(name, str):
            raise RpcError(INVALID_PARAMS, "tools/call needs a string 'name'")
        tool = next((t for t in TOOLS if t["name"] == name), None)
        if tool is None:
            raise RpcError(INVALID_PARAMS, f"Unknown tool: {name}")
        args = params.get("arguments", {})
        if not isinstance(args, dict):
            raise RpcError(INVALID_PARAMS, "'arguments' must be an object")

        def block(text: str, is_error: bool) -> Dict[str, Any]:
            return {"content": [{"type": "text", "text": text}], "isError": is_error}

        problems = check_arguments(tool["inputSchema"], args)
        if problems:
            return block(f"Invalid arguments for {name}: " + "; ".join(problems), True)
        try:
            return block(TOOL_FUNCS[name](args), False)
        except ToolError as e:
            return block(str(e), True)

    # ---- milestone 4: resources --------------------------------------------------
    def list_resources(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """{"resources": [{uri, name, title, mimeType}]}, one per order, in ORDERS order:
        uri "order://A-1001", name "order-A-1001", title "Order A-1001", mimeType "text/plain"."""
        return {"resources": [{"uri": f"order://{i}", "name": f"order-{i}", "title": f"Order {i}",
                               "mimeType": "text/plain"} for i in ORDERS]}

    def read_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """{"contents": [{uri, mimeType, text}]} with text from describe_order. A uri that is
        missing or not a string is -32602; a string that names no order is -32002 with data {"uri": uri}."""
        uri = params.get("uri")
        if not isinstance(uri, str):
            raise RpcError(INVALID_PARAMS, "resources/read needs a string 'uri'")
        oid = uri[len("order://"):] if uri.startswith("order://") else None
        if oid not in ORDERS:
            raise RpcError(RESOURCE_NOT_FOUND, "Resource not found", {"uri": uri})
        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": describe_order(oid)}]}

    # ---- milestone 6: the stateless era ----------------------------------------------
    def process_modern(self, method: str, params: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
        """Serve one 2026-07-28 request. It touches no state: nothing here reads or writes self.state.

        - version (K_VERSION) must be a string and capabilities (K_CAPS) an object, else -32602
          "Missing required _meta fields".
        - a version not in MODERN_VERSIONS is -32022 "Unsupported protocol version" with
          data {"supported": MODERN_VERSIONS, "requested": version}.
        - methods: server/discover, tools/list, tools/call, resources/list, resources/read. Anything
          else (initialize and ping included) is -32601.
        - every result gets "resultType": "complete" and "_meta": {K_SERVER: SERVER_INFO}; the list and
          read results and server/discover also carry "ttlMs" and "cacheScope" (see CACHE).
        - a resource that does not exist is -32602 in this era (data still {"uri": uri}).
        - server/discover result: supportedVersions (MODERN_VERSIONS) and capabilities (CAPABILITIES).
        """
        version, caps = meta.get(K_VERSION), meta.get(K_CAPS)
        if not isinstance(version, str) or not isinstance(caps, dict):
            raise RpcError(INVALID_PARAMS, "Missing required _meta fields", {"required": [K_VERSION, K_CAPS]})
        if version not in MODERN_VERSIONS:
            raise RpcError(UNSUPPORTED_VERSION, "Unsupported protocol version",
                           {"supported": MODERN_VERSIONS, "requested": version})
        if method == "server/discover":
            result: Dict[str, Any] = {"supportedVersions": MODERN_VERSIONS, "capabilities": CAPABILITIES}
        elif method in CACHE or method == "tools/call":
            try:
                result = dict(self.dispatch(method, params))
            except RpcError as e:
                if e.code == RESOURCE_NOT_FOUND:
                    raise RpcError(INVALID_PARAMS, e.message, e.data) from None
                raise
        else:
            raise RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
        if method in CACHE:
            result["ttlMs"], result["cacheScope"] = CACHE[method]
        return {"resultType": "complete", **result, "_meta": {K_SERVER: SERVER_INFO}}


# =============================================================================
# Milestone 5: the client
# =============================================================================
CLIENT_VERSIONS = ["2025-11-25", "2025-06-18"]


class McpError(Exception):
    """The server answered a request with a JSON-RPC error."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.data = code, message, data


class McpClient:
    """Starts a server as a subprocess and speaks to it over its stdin and stdout."""

    def __init__(self, cmd: List[str]):
        import os
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        self.next_id = 1
        self.trace: List[str] = []          # "--> {...}" and "<-- {...}" lines, for debugging

    def _send(self, msg: Dict[str, Any]) -> None:
        """Given: write one message as one line and remember it in the trace."""
        line = encode(msg)
        self.trace.append("--> " + line)
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a request with the next id, read ONE line, and return its result.

        - no line (end of file): ConnectionError
        - a line that is not JSON: ValueError mentioning "non-JSON"
        - a reply whose id differs from the request's: ValueError mentioning "id"
        - an error reply: McpError(code, message, data)
        Add "<-- " plus the raw line (stripped) to self.trace.
        """
        mid, self.next_id = self.next_id, self.next_id + 1
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)
        line = self.proc.stdout.readline()
        if not line:
            raise ConnectionError(f"server closed its output before answering {method}")
        self.trace.append("<-- " + line.strip())
        try:
            reply = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError(f"server wrote non-JSON to stdout: {line.strip()!r}") from None
        if reply.get("id") != mid:
            raise ValueError(f"reply has id {reply.get('id')!r} but the request had id {mid}")
        if "error" in reply:
            e = reply["error"]
            raise McpError(e["code"], e["message"], e.get("data"))
        return reply["result"]

    def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Send a notification: no id, and no reply is read."""
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)

    def connect(self) -> Dict[str, Any]:
        """The handshake: initialize (newest of CLIENT_VERSIONS, empty capabilities, clientInfo),
        then notifications/initialized. If the server's protocolVersion is not one of CLIENT_VERSIONS,
        close and raise ValueError. Return the initialize result."""
        result = self.request("initialize", {"protocolVersion": CLIENT_VERSIONS[0], "capabilities": {},
                                             "clientInfo": {"name": "lab-client", "version": "0.1.0"}})
        if result.get("protocolVersion") not in CLIENT_VERSIONS:
            self.close()
            raise ValueError(f"server chose protocol version {result.get('protocolVersion')!r}, which this client does not speak")
        self.notify("notifications/initialized")
        return result

    def list_tools(self) -> List[Dict[str, Any]]:
        """The server's tool definitions."""
        return self.request("tools/list")["tools"]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Tuple[str, bool]:
        """tools/call; return (the text blocks joined with newlines, isError). McpError passes through."""
        res = self.request("tools/call", {"name": name, "arguments": arguments})
        text = "\n".join(b["text"] for b in res["content"] if b.get("type") == "text")
        return text, bool(res.get("isError", False))

    def close(self) -> str:
        """Polite stdio shutdown: close the server's stdin, wait up to 5 s (then kill), return its stderr."""
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        return self.proc.stderr.read()


def to_model_tools(mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """MCP tool definitions to the model-facing shape of llm.py: name, description, input_schema."""
    return [{"name": t["name"], "description": t.get("description", ""), "input_schema": t["inputSchema"]}
            for t in mcp_tools]


def run_tool_use(client: McpClient, block: Dict[str, Any]) -> Dict[str, Any]:
    """Route one model tool_use block through MCP and return the tool_result block for the model.
    A protocol error (McpError) becomes an is_error result reading "MCP error <code>: <message>"."""
    try:
        text, is_error = client.call_tool(block["name"], block["input"])
    except McpError as e:
        return tool_result(block["id"], f"MCP error {e.code}: {e.message}", is_error=True)
    return tool_result(block["id"], text, is_error=is_error)


if __name__ == "__main__":
    serve(Server(), sys.stdin, sys.stdout)
