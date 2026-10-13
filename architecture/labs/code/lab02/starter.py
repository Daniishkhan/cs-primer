"""Lab 2 starter: an idempotent, paginated, versioned orders API.

The plumbing (routing, WSGI glue, helpers) is given. Fill in every function whose body is a
TODO / NotImplementedError, one milestone at a time, and run `python3 check.py`.

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
    """Return a list of {"field": ..., "message": ...} problems; [] means valid.

    Rules: body is an object; customer non-empty string; items non-empty list of objects with
    sku (non-empty str), qty (int >= 1, not a bool) and unit_price_cents (int >= 0, not a bool).
    Field names look like "items[0].qty". Milestone 4 adds: for version "v2", an optional
    currency must be 3 uppercase letters."""
    raise NotImplementedError("TODO milestone 1: validate_order")


def render_order(row, version):
    """Turn a sqlite3.Row into the dict for `version`.

    Both versions: id, customer, items (a list: json.loads(row["items"])), status, created_at
    (use iso(row["created_at"])).
    v1 (milestone 1): add "total" = row["total_cents"] / 100.
    v2 (milestone 4): NO "total"; add "amount_cents" = row["total_cents"] and "currency"."""
    raise NotImplementedError("TODO milestone 1: render_order")


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
    """POST /vN/orders. Return (status, headers, body_bytes).

    Milestone 1: parse_body (400 on bad JSON), validate_order (422 problem "invalid-order" with
    an "errors" list), insert_order, then 201 with Content-Type application/json, a Location
    header "/vN/orders/<id>" and the rendered order as dumps(...).
    Milestone 2: honour the Idempotency-Key header (req.headers["idempotency-key"]). See the
    lab page: one BEGIN IMMEDIATE transaction that INSERTs the key row first, so the UNIQUE
    constraint decides who wins; on IntegrityError compare fingerprints and replay or answer 422."""
    raise NotImplementedError("TODO milestone 1: create_order")


def get_order(ctx, version, req, order_id):
    """GET /vN/orders/<id>: 200 with the rendered order, or a 404 problem "order-not-found"."""
    raise NotImplementedError("TODO milestone 1: get_order")


# ---------------------------------------------------------------- milestone 3: cursor pagination
def encode_cursor(created_at, order_id):
    """Opaque cursor for (created_at, id): url-safe base64 of the JSON list, padding stripped."""
    raise NotImplementedError("TODO milestone 3: encode_cursor")


def decode_cursor(text):
    """Inverse of encode_cursor. Return (created_at, id), or raise ValueError for anything that is not
    a base64 JSON list of exactly two ints."""
    raise NotImplementedError("TODO milestone 3: decode_cursor")


def list_orders(ctx, version, req):
    """GET /vN/orders?limit=&cursor= : newest first, ordered by (created_at DESC, id DESC).

    limit defaults to DEFAULT_LIMIT, must be 1..MAX_LIMIT (else 400 "invalid-limit"). A bad
    cursor is a 400 "invalid-cursor". Use keyset pagination: WHERE (created_at, id) < (?, ?).
    Fetch limit+1 rows to learn whether there is a next page. Body:
    {"data": [rendered orders], "next": "/vN/orders?limit=L&cursor=C" or None}."""
    raise NotImplementedError("TODO milestone 3: list_orders")


# ---------------------------------------------------------------- milestone 5: deprecation and usage
DEPRECATION = "@1767225600"                    # RFC 9745: an sf-date, here 2026-01-01T00:00:00Z
SUNSET = "Fri, 01 Jan 2027 00:00:00 GMT"       # RFC 8594: an HTTP-date


def deprecation_headers(version):
    """Extra headers for every response of a deprecated version.

    Milestone 5, for "v1": Deprecation: DEPRECATION, Sunset: SUNSET and
    Link: </v2/orders>; rel="successor-version". Other versions: []."""
    # TODO milestone 5: return the three headers for "v1". Returning [] keeps milestones 1-4 working.
    return []


def count_usage(conn, version):
    """Called once per request to /v1/... or /v2/... (never for /admin).

    Milestone 5: bump the version's row in the `usage` table in one statement:
    INSERT ... ON CONFLICT (version) DO UPDATE SET count = count + 1."""
    pass     # TODO milestone 5


def usage_report(ctx, req):
    """GET /admin/usage -> 200 {"usage": {"v1": N, "v2": M}} read from the `usage` table."""
    raise NotImplementedError("TODO milestone 5: usage_report")


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
