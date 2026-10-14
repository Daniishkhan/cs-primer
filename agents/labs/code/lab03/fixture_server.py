"""fixture_server.py: a tiny, deliberately minimal MCP-ish server used ONLY by check.py to test
your CLIENT (milestone 5) independently of your own server. Do not edit.

    python3 fixture_server.py             # behaves
    python3 fixture_server.py noisy       # prints a banner to STDOUT first (the classic mistake)
    python3 fixture_server.py hangup      # exits without answering initialize
    python3 fixture_server.py wrongid     # answers with the wrong id
    python3 fixture_server.py oldversion  # answers initialize with a version nobody speaks
It offers one tool, `echo`, and logs to stderr.
"""
import json
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else ""
if mode == "noisy":
    print("fixture server ready")           # not JSON-RPC, on the protocol channel

TOOL = {"name": "echo", "description": "Return the text it is given.",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}},
                        "required": ["text"], "additionalProperties": False}}


def reply(msg):
    method, params = msg["method"], msg.get("params") or {}
    if method == "initialize":
        version = "1999-01-01" if mode == "oldversion" else "2025-11-25"
        return {"protocolVersion": version, "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture", "version": "0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [TOOL]}
    if method == "tools/call":
        if params.get("name") != "echo":
            return {"code": -32602, "message": f"Unknown tool: {params.get('name')}"}
        text = (params.get("arguments") or {}).get("text")
        if not isinstance(text, str):
            return {"content": [{"type": "text", "text": "text is required"}], "isError": True}
        return {"content": [{"type": "text", "text": text}], "isError": False}
    return {"code": -32601, "message": f"Method not found: {method}"}


count = 0
for line in sys.stdin:
    msg = json.loads(line)
    count += 1
    if "id" not in msg:
        continue                              # a notification: never answered
    if mode == "hangup" and msg["method"] == "initialize":
        sys.exit(0)
    out = reply(msg)
    mid = msg["id"] + 100 if mode == "wrongid" else msg["id"]
    if "code" in out:
        print(json.dumps({"jsonrpc": "2.0", "id": mid, "error": out}), flush=True)
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": mid, "result": out}), flush=True)
print(f"fixture: stdin closed after {count} messages", file=sys.stderr)
