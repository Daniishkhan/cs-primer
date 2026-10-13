"""Lab 2 reference solution: an idempotent, paginated, versioned orders API.

A WSGI application using only the standard library. The app is a plain callable
`app(environ, start_response)`, so tests call it directly with an environ dict and no
sockets (see testing.py). To serve it for real, see the bottom of this file.
"""
import base64
import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs

JSON, PROBLEM = "application/json", "application/problem+json"
PHRASE = {200: "OK", 201: "Created", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed",
          422: "Unprocessable Content"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer TEXT NOT NULL, items TEXT NOT NULL,
    total_cents INTEGER NOT NULL, currency TEXT NOT NULL,
    status TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS orders_by_time ON orders (created_at, id);
CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,                    -- the UNIQUE constraint is the lock
    fingerprint TEXT NOT NULL,
    status INTEGER, location TEXT, body BLOB);
CREATE TABLE IF NOT EXISTS usage (version TEXT PRIMARY KEY, count INTEGER NOT NULL);
"""

VERSIONS = ("v1", "v2")
DEFAULT_LIMIT, MAX_LIMIT = 10, 50


# ---------------------------------------------------------------- plumbing
@dataclass
class Req:
    method: str
    path: str
    query: dict
    body: bytes
    headers: dict = field(default_factory=dict)      # lower-case names


def dumps(obj):
    """THE serialisation: sorted keys, no spaces. v1 clients may depend on every byte (Hyrum's law)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def result(status, obj, headers=()):
    return status, [("Content-Type", JSON)] + list(headers), dumps(obj)


def problem(status, slug, title, detail, instance, headers=(), **extra):
    """RFC 9457 problem details: type, title, status, detail, instance (+ extension members)."""
    body = {"type": "https://example.com/problems/" + slug, "title": title, "status": status,
            "detail": detail, "instance": instance}
    body.update(extra)
    return status, [("Content-Type", PROBLEM)] + list(headers), dumps(body)


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


# ---------------------------------------------------------------- milestone 1: resources
def validate_order(data, version):
    """Return a list of {"field", "message"} problems (empty list = valid)."""
    if not isinstance(data, dict):
        return [{"field": "(body)", "message": "must be a JSON object"}]
    errors = []
    if not isinstance(data.get("customer"), str) or not data["customer"].strip():
        errors.append({"field": "customer", "message": "required, non-empty string"})
    items = data.get("items")
    if not isinstance(items, list) or not items:
        errors.append({"field": "items", "message": "required, non-empty list"})
    else:
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                errors.append({"field": "items[%d]" % i, "message": "must be an object"})
                continue
            if not isinstance(it.get("sku"), str) or not it["sku"]:
                errors.append({"field": "items[%d].sku" % i, "message": "required, non-empty string"})
            q = it.get("qty")
            if not isinstance(q, int) or isinstance(q, bool) or q < 1:
                errors.append({"field": "items[%d].qty" % i, "message": "integer, at least 1"})
            p = it.get("unit_price_cents")
            if not isinstance(p, int) or isinstance(p, bool) or p < 0:
                errors.append({"field": "items[%d].unit_price_cents" % i, "message": "integer, 0 or more"})
    cur = data.get("currency")                       # milestone 4: v2 only; v1 clients never send it
    if version == "v2" and cur is not None and not (isinstance(cur, str) and re.fullmatch(r"[A-Z]{3}", cur)):
        errors.append({"field": "currency", "message": "optional, a 3-letter uppercase code such as USD"})
    return errors


def render_order(row, version):
    items = json.loads(row["items"])
    base = {"id": row["id"], "customer": row["customer"], "items": items, "status": row["status"],
            "created_at": iso(row["created_at"])}
    if version == "v1":
        base["total"] = row["total_cents"] / 100              # v1 shape, frozen forever: decimal units
    else:
        base["amount_cents"] = row["total_cents"]             # v2: integer minor units, plus the currency
        base["currency"] = row["currency"]
    return base


def parse_body(req):
    try:
        return json.loads(req.body.decode("utf-8")), None
    except (ValueError, UnicodeDecodeError):
        return None, problem(400, "malformed-json", "Malformed JSON", "The request body is not valid JSON.", req.path)


def insert_order(conn, clock, data, version):
    items = [{"sku": i["sku"], "qty": i["qty"], "unit_price_cents": i["unit_price_cents"]} for i in data["items"]]
    total = sum(i["qty"] * i["unit_price_cents"] for i in items)
    cur = conn.execute(
        "INSERT INTO orders (customer, items, total_cents, currency, status, created_at) VALUES (?,?,?,?,?,?)",
        (data["customer"], json.dumps(items), total, (data.get("currency") or "USD") if version == "v2" else "USD",
         "created", int(clock())))
    return cur.lastrowid


def create_order(ctx, version, req):
    conn = ctx.conn
    data, bad = parse_body(req)
    if bad:
        return bad
    errors = validate_order(data, version)
    if errors:
        return problem(422, "invalid-order", "Invalid order", "The order failed validation.", req.path, errors=errors)
    key = req.headers.get("idempotency-key")
    # ---- milestone 2: the key row and the order are written in ONE transaction
    fingerprint = hashlib.sha256(("POST %s\n" % req.path).encode() + dumps(data)).hexdigest()
    conn.execute("BEGIN IMMEDIATE")                 # writers queue here; waiting is bounded by the busy timeout
    try:
        if key:
            try:
                conn.execute("INSERT INTO idempotency (key, fingerprint) VALUES (?, ?)", (key, fingerprint))
            except sqlite3.IntegrityError:          # somebody already owns this key (and has committed)
                row = conn.execute("SELECT * FROM idempotency WHERE key = ?", (key,)).fetchone()
                conn.execute("ROLLBACK")
                if row["fingerprint"] != fingerprint:
                    return problem(422, "idempotency-key-reuse", "Idempotency key reuse",
                                   "That Idempotency-Key was already used with a different request.", req.path)
                return (row["status"], [("Content-Type", JSON), ("Location", row["location"]),
                                        ("Idempotent-Replayed", "true")], bytes(row["body"]))
        order_id = insert_order(conn, ctx.clock, data, version)
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        location = "/%s/orders/%d" % (version, order_id)
        body = dumps(render_order(row, version))
        if key:
            conn.execute("UPDATE idempotency SET status = 201, location = ?, body = ? WHERE key = ?",
                         (location, body, key))
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return 201, [("Content-Type", JSON), ("Location", location)], body


def get_order(ctx, version, req, order_id):
    row = ctx.conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        return problem(404, "order-not-found", "Order not found", "No order %d." % order_id, req.path)
    return result(200, render_order(row, version))


# ---------------------------------------------------------------- milestone 3: cursor pagination
def encode_cursor(created_at, order_id):
    raw = json.dumps([created_at, order_id]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(text):
    """Return (created_at, id) or raise ValueError."""
    try:
        pair = json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)))
    except (ValueError, TypeError):
        raise ValueError("bad cursor")
    if (not isinstance(pair, list) or len(pair) != 2
            or not all(isinstance(n, int) and not isinstance(n, bool) for n in pair)):
        raise ValueError("bad cursor")
    return pair[0], pair[1]


def list_orders(ctx, version, req):
    try:
        limit = int(req.query.get("limit", [str(DEFAULT_LIMIT)])[0])
        if not 1 <= limit <= MAX_LIMIT:
            raise ValueError
    except ValueError:
        return problem(400, "invalid-limit", "Invalid limit", "limit must be an integer from 1 to %d." % MAX_LIMIT, req.path)
    sql, args = "SELECT * FROM orders", []
    if "cursor" in req.query:
        try:
            after = decode_cursor(req.query["cursor"][0])
        except ValueError:
            return problem(400, "invalid-cursor", "Invalid cursor", "The cursor is not one this API issued.", req.path)
        sql += " WHERE (created_at, id) < (?, ?)"        # keyset: everything strictly "older" than the cursor
        args += list(after)
    rows = ctx.conn.execute(sql + " ORDER BY created_at DESC, id DESC LIMIT ?", args + [limit + 1]).fetchall()
    page = rows[:limit]
    nxt = None
    if len(rows) > limit:                                # there is at least one more row
        last = page[-1]
        nxt = "/%s/orders?limit=%d&cursor=%s" % (version, limit, encode_cursor(last["created_at"], last["id"]))
    return result(200, {"data": [render_order(r, version) for r in page], "next": nxt})


# ---------------------------------------------------------------- milestone 5: deprecation and usage
DEPRECATION = "@1767225600"                    # RFC 9745: an sf-date, here 2026-01-01T00:00:00Z
SUNSET = "Fri, 01 Jan 2027 00:00:00 GMT"       # RFC 8594: an HTTP-date


def deprecation_headers(version):
    """Headers to add to EVERY response of a deprecated version (errors and replays included)."""
    if version != "v1":
        return []
    return [("Deprecation", DEPRECATION), ("Sunset", SUNSET), ("Link", '</v2/orders>; rel="successor-version"')]


def count_usage(conn, version):
    conn.execute("INSERT INTO usage (version, count) VALUES (?, 1) "
                 "ON CONFLICT (version) DO UPDATE SET count = count + 1", (version,))


def usage_report(ctx, req):
    rows = ctx.conn.execute("SELECT version, count FROM usage ORDER BY version").fetchall()
    return result(200, {"usage": {r["version"]: r["count"] for r in rows}})


# ---------------------------------------------------------------- routing (given in the starter)
class Ctx:
    def __init__(self, db_path, clock):
        self.db_path, self.clock = db_path, clock
        self.conn = None


def dispatch(ctx, req):
    if req.path == "/admin/usage":
        if req.method != "GET":
            return problem(405, "method-not-allowed", "Method not allowed", "Allowed: GET.", req.path,
                           headers=[("Allow", "GET")])
        return usage_report(ctx, req)
    m = re.match(r"^/(v\d+)/orders(?:/(\d+))?$", req.path)
    if not m or m.group(1) not in VERSIONS:
        return problem(404, "not-found", "Not found", "No such route.", req.path)
    version, oid = m.group(1), m.group(2)
    count_usage(ctx.conn, version)
    status, headers, body = route(ctx, req, version, oid)
    return status, headers + deprecation_headers(version), body


def route(ctx, req, version, oid):
    allowed = "GET" if oid else "GET, POST"
    if req.method not in allowed.split(", "):
        return problem(405, "method-not-allowed", "Method not allowed", "Allowed: %s." % allowed,
                       req.path, headers=[("Allow", allowed)])
    if oid:
        return get_order(ctx, version, req, int(oid))
    return create_order(ctx, version, req) if req.method == "POST" else list_orders(ctx, version, req)


def make_app(db_path, clock=None):
    """Create the schema and return a WSGI callable. One sqlite connection per request."""
    clock = clock or time.time
    boot = sqlite3.connect(db_path)
    boot.executescript(SCHEMA)
    boot.commit()
    boot.close()

    def app(environ, start_response):
        length = int(environ.get("CONTENT_LENGTH") or 0)
        headers = {k[5:].replace("_", "-").lower(): v for k, v in environ.items() if k.startswith("HTTP_")}
        req = Req(environ["REQUEST_METHOD"], environ["PATH_INFO"], parse_qs(environ.get("QUERY_STRING", "")),
                  environ["wsgi.input"].read(length) if length else b"", headers)
        ctx = Ctx(db_path, clock)
        ctx.conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)   # we manage transactions
        ctx.conn.row_factory = sqlite3.Row
        try:
            status, hdrs, body = dispatch(ctx, req)
        finally:
            ctx.conn.close()
        hdrs = hdrs + [("Content-Length", str(len(body)))]
        start_response("%d %s" % (status, PHRASE.get(status, "Status")), hdrs)
        return [body]

    return app


if __name__ == "__main__":
    # Optional: serve it for real and poke it with curl (see the lab page).
    from wsgiref.simple_server import make_server
    with make_server("127.0.0.1", 8000, make_app("orders.db")) as httpd:
        print("serving on http://127.0.0.1:8000  (Ctrl-C to stop)")
        httpd.serve_forever()
