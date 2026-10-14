"""Lab 3 starter: An MCP Server & Client.  THIS IS YOUR FILE.

Given: the constants, RpcError and ToolError, the order desk (ORDERS, the two tool functions,
TOOLS, TOOL_FUNCS and check_arguments), Server.dispatch, McpClient.__init__ and _send, and the
freshness table CACHE. Every function you write raises NotImplementedError until you replace it.
Work in order; run

    python3 check.py            # checks this file
    python3 check.py 3          # only milestone 3

  1. result_message, error_message, encode, parse_line, classify, serve, Server.handle_line
                                  messages on a line: framing, envelopes and error codes
  2. Server.on_initialize, on_notification, process      the handshake and version negotiation
  3. Server.list_tools, call_tool                        tools, and the two kinds of error
  4. Server.list_resources, read_resource                resources, then an error-code sweep
  5. McpClient (request, notify, connect, list_tools, call_tool, close), to_model_tools,
     run_tool_use                                        the client, and the bridge to a model
  6. Server.process_modern (and one branch in process)   the stateless 2026-07-28 style

The finished file is also a runnable server:  python3 starter.py  (stdin to stdout, one JSON
object per line, logs on stderr). Standard library only. llm.py is the shared stand-in model
module; do not edit it.
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
    raise NotImplementedError("TODO milestone 1: result_message")


def error_message(id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    """A JSON-RPC error response; `data` is included only when it is not None."""
    raise NotImplementedError("TODO milestone 1: error_message")


def encode(msg: Dict[str, Any]) -> str:
    """One message as one line: compact JSON, and no newline inside (json.dumps escapes them)."""
    raise NotImplementedError("TODO milestone 1: encode")


def parse_line(line: str) -> Dict[str, Any]:
    """Parse one line into a message dict, or raise RpcError.

    -32700 if the line is not JSON. -32600 if it is JSON but not a valid single message: an array
    (MCP does not allow batches), not an object, "jsonrpc" not "2.0", a "method" that is not a
    string, an "id" that is null, boolean, float or anything but a string or integer, "params"
    that is not an object, or an object with neither "method" nor "result" nor "error".
    When the id could be read, put it on the RpcError (id=...), otherwise leave it None.
    """
    raise NotImplementedError("TODO milestone 1: parse_line")


def classify(msg: Dict[str, Any]) -> str:
    """'request' (method and id), 'notification' (method, no id) or 'response' (no method)."""
    raise NotImplementedError("TODO milestone 1: classify")


def serve(server: "Server", infile, outfile) -> None:
    """The stdio transport: one reply line per request line, flushed at once, until input ends."""
    raise NotImplementedError("TODO milestone 1: serve")


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
        raise NotImplementedError("TODO milestone 1: Server.handle_line")

    # ---- milestone 2: the handshake -----------------------------------------
    def on_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate, negotiate and answer `initialize`.

        protocolVersion must be a string, capabilities and clientInfo objects, else -32602 (and no
        state change). Answer with the client's version if it is in LEGACY_VERSIONS, otherwise the
        newest one. Result: protocolVersion, capabilities (CAPABILITIES), serverInfo (SERVER_INFO).
        """
        raise NotImplementedError("TODO milestone 2: Server.on_initialize")

    def on_notification(self, method: str, params: Dict[str, Any]) -> None:
        """notifications/initialized completes the handshake (only after a good initialize).
        Every other notification, known or not, is ignored."""
        raise NotImplementedError("TODO milestone 2: Server.on_notification")

    def process(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the lifecycle rules, then dispatch.

        Modern requests (milestone 6) are handled first. For handshake-era requests: `initialize`
        when already initialised is -32600 "Already initialised"; anything except `initialize` and
        `ping` before the handshake has completed is -32600 "Server not initialised ...".
        """
        raise NotImplementedError("TODO milestone 2: Server.process")

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
        raise NotImplementedError("TODO milestone 3: Server.list_tools")

    def call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a tool. Protocol faults are RpcErrors (-32602: name missing or not a string, unknown
        tool, arguments not an object). Everything the model can fix is a normal result with
        isError true: arguments that fail check_arguments, or a ToolError from the tool. Any other
        exception from the tool propagates (it becomes -32603). Look tools up in TOOL_FUNCS at call
        time. Success: {"content": [{"type": "text", "text": ...}], "isError": False}.
        """
        raise NotImplementedError("TODO milestone 3: Server.call_tool")

    # ---- milestone 4: resources --------------------------------------------------
    def list_resources(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """{"resources": [{uri, name, title, mimeType}]}, one per order, in ORDERS order:
        uri "order://A-1001", name "order-A-1001", title "Order A-1001", mimeType "text/plain"."""
        raise NotImplementedError("TODO milestone 4: Server.list_resources")

    def read_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """{"contents": [{uri, mimeType, text}]} with text from describe_order. A uri that is
        missing or not a string is -32602; a string that names no order is -32002 with data {"uri": uri}."""
        raise NotImplementedError("TODO milestone 4: Server.read_resource")

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
        raise NotImplementedError("TODO milestone 6: Server.process_modern")


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
        raise NotImplementedError("TODO milestone 5: McpClient.request")

    def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Send a notification: no id, and no reply is read."""
        raise NotImplementedError("TODO milestone 5: McpClient.notify")

    def connect(self) -> Dict[str, Any]:
        """The handshake: initialize (newest of CLIENT_VERSIONS, empty capabilities, clientInfo),
        then notifications/initialized. If the server's protocolVersion is not one of CLIENT_VERSIONS,
        close and raise ValueError. Return the initialize result."""
        raise NotImplementedError("TODO milestone 5: McpClient.connect")

    def list_tools(self) -> List[Dict[str, Any]]:
        """The server's tool definitions."""
        raise NotImplementedError("TODO milestone 5: McpClient.list_tools")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Tuple[str, bool]:
        """tools/call; return (the text blocks joined with newlines, isError). McpError passes through."""
        raise NotImplementedError("TODO milestone 5: McpClient.call_tool")

    def close(self) -> str:
        """Polite stdio shutdown: close the server's stdin, wait up to 5 s (then kill), return its stderr."""
        raise NotImplementedError("TODO milestone 5: McpClient.close")


def to_model_tools(mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """MCP tool definitions to the model-facing shape of llm.py: name, description, input_schema."""
    raise NotImplementedError("TODO milestone 5: to_model_tools")


def run_tool_use(client: McpClient, block: Dict[str, Any]) -> Dict[str, Any]:
    """Route one model tool_use block through MCP and return the tool_result block for the model.
    A protocol error (McpError) becomes an is_error result reading "MCP error <code>: <message>"."""
    raise NotImplementedError("TODO milestone 5: run_tool_use")


if __name__ == "__main__":
    serve(Server(), sys.stdin, sys.stdout)
