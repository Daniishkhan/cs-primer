"""Self-check for Lab 2.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

No sockets: the app callable is invoked directly with built environ dicts (testing.py).
The only "concurrency" is a handful of threads calling the app at the same moment against a
temporary sqlite file, with timeouts so nothing can hang; the assertions are about the
outcome (exactly one order), which does not depend on timing. Prints a tick, a cross, or
"not implemented yet" for each milestone. Finishes in a few seconds.
"""
import base64
import email.utils
import importlib
import json
import os
import random
import re
import shutil
import sqlite3
import sys
import tempfile
import threading

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
from testing import call  # noqa: E402
import snapshot           # noqa: E402

results = []
TMP = tempfile.mkdtemp(prefix="lab02-")

ORDER = {"customer": "ana@example.com", "items": [{"sku": "mug", "qty": 2, "unit_price_cents": 1500}]}


def check(name, fn):
    try:
        fn()
        print("  \u2714 " + name)
        results.append(True)
    except NotImplementedError as e:
        print("  \u2026 %s: not implemented yet (%s)" % (name, e))
        results.append(False)
    except AssertionError as e:
        print("  \u2718 %s: %s" % (name, e))
        results.append(False)
    except Exception as e:
        print("  \u2718 %s: %s: %s" % (name, type(e).__name__, e))
        results.append(False)


class Fixture:
    """A fresh app on a fresh sqlite file, with a clock that ticks one minute per call."""
    n = 0

    def __init__(self, frozen=False):
        Fixture.n += 1
        self.path = os.path.join(TMP, "t%d.db" % Fixture.n)
        t = {"v": 1700000000}

        def clock():
            if not frozen:
                t["v"] += 60
            return t["v"]
        self.app = mod.make_app(self.path, clock)

    def call(self, *a, **kw):
        return call(self.app, *a, **kw)

    def post(self, body=ORDER, version="v1", key=None, **kw):
        return self.call("POST", "/%s/orders" % version, body, {"Idempotency-Key": key} if key else None)

    def count(self, table="orders"):
        c = sqlite3.connect(self.path)
        try:
            return c.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        finally:
            c.close()


def is_problem(r, status):
    assert r.status == status, "expected HTTP %d, got %d: %s" % (status, r.status, r.body[:120])
    assert r.headers.get("content-type", "").split(";")[0] == "application/problem+json", \
        "errors must use Content-Type application/problem+json, got %r" % r.headers.get("content-type")
    body = r.json()
    for f in ("type", "title", "status", "detail"):
        assert f in body, "problem+json (RFC 9457) needs a '%s' member, got %s" % (f, sorted(body))
    assert body["status"] == status, "the 'status' member must repeat the HTTP status (%d)" % status
    return body


def in_threads(fns, timeout=30):
    """Run callables simultaneously; return (results, errors). Never hangs."""
    out, errs = [None] * len(fns), []
    gate = threading.Barrier(len(fns))

    def run(i):
        try:
            gate.wait(10)
            out[i] = fns[i]()
        except BaseException as e:      # surface exceptions raised inside threads
            errs.append("%s: %s" % (type(e).__name__, e))

    ts = [threading.Thread(target=run, args=(i,), daemon=True) for i in range(len(fns))]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout)
    assert not any(t.is_alive() for t in ts), "a request thread did not finish within %ds" % timeout
    assert not errs, "exception inside a request thread: " + errs[0]
    return out


# ---------------------------------------------------------------------------- 1
def m1():
    f = Fixture()
    r = f.post()
    assert r.status == 201, "POST /v1/orders should answer 201 Created, got %d %s" % (r.status, r.body[:100])
    assert r.headers.get("content-type", "").startswith("application/json"), "Content-Type should be application/json"
    assert r.headers.get("location") == "/v1/orders/1", "201 needs Location: /v1/orders/1, got %r" % r.headers.get("location")
    body = r.json()
    assert body["id"] == 1 and body["customer"] == "ana@example.com" and body["status"] == "created", body
    assert body["total"] == 30.0, "v1 'total' is decimal units (2 x 15.00 = 30.0), got %r" % body.get("total")
    assert body["items"] == ORDER["items"], "items should be echoed back, got %r" % body.get("items")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", body["created_at"]), "created_at should be ISO 8601 UTC, got %r" % body["created_at"]
    g = f.call("GET", "/v1/orders/1")
    assert g.status == 200 and g.body == r.body, "GET /v1/orders/1 should return exactly what POST returned"
    p = is_problem(f.call("GET", "/v1/orders/99"), 404)
    assert p["type"].startswith("http"), "'type' should be a URI reference"
    p = is_problem(f.call("POST", "/v1/orders", "{oops"), 400)
    p = is_problem(f.call("POST", "/v1/orders", {"customer": "", "items": [{"sku": "x", "qty": 0, "unit_price_cents": 5}]}), 422)
    fields = {e.get("field") for e in p.get("errors", [])}
    assert {"customer", "items[0].qty"} <= fields, "422 should list every invalid field in an 'errors' array; got %s" % sorted(fields)
    for bad in ({"customer": "a", "items": []}, {"customer": "a", "items": [{"sku": "x", "qty": True, "unit_price_cents": 1}]},
                {"customer": "a", "items": [{"sku": "x", "qty": 1, "unit_price_cents": -1}]}, [1, 2]):
        is_problem(f.call("POST", "/v1/orders", bad), 422)
    assert f.count() == 1, "invalid requests must not create orders (found %d)" % f.count()
    r = f.call("DELETE", "/v1/orders/1")
    is_problem(r, 405)
    assert "GET" in r.headers.get("allow", ""), "405 must carry an Allow header"
    is_problem(f.call("GET", "/v1/nowhere"), 404)


# ---------------------------------------------------------------------------- 2
def m2():
    f = Fixture()
    a = f.post(key="k-1")
    assert a.status == 201, "first POST with a key should be 201, got %d" % a.status
    b = f.post(key="k-1")
    assert (b.status, b.body, b.headers.get("location")) == (a.status, a.body, a.headers.get("location")), \
        "a replay must return the SAME status, body and Location as the first answer"
    assert f.count() == 1, "a replay must not create a second order (found %d)" % f.count()
    c = f.post(dict(ORDER, customer="someone-else"), key="k-1")
    p = is_problem(c, 422)
    assert f.count() == 1, "key reuse with a different body must create nothing"
    assert "idempotency" in json.dumps(p).lower(), "the problem should mention the Idempotency-Key"
    f.post()
    f.post()
    assert f.count() == 3, "requests without a key are not deduplicated"
    is_problem(f.post({"customer": ""}, key="k-2"), 422)
    ok = f.post(key="k-2")
    assert ok.status == 201 and ok.headers.get("idempotent-replayed") is None, \
        "a request that failed validation must not use up its key"
    # canonical fingerprint: same JSON, different whitespace/order is still the same request
    x = f.call("POST", "/v1/orders", json.dumps(ORDER, indent=2), {"Idempotency-Key": "k-3"})
    y = f.call("POST", "/v1/orders", json.dumps(dict(reversed(list(ORDER.items())))), {"Idempotency-Key": "k-3"})
    assert x.status == 201 and y.body == x.body, "a retry with reordered keys / different spacing is the same request"
    # concurrency: 16 duplicates at the same instant -> exactly one order
    f = Fixture()
    outs = in_threads([lambda: f.post(key="race")] * 16)
    assert all(o.status == 201 for o in outs), "every duplicate should see 201, got %s" % sorted({o.status for o in outs})
    assert len({o.body for o in outs}) == 1, "all 16 duplicates must receive the identical response"
    assert f.count() == 1, "16 concurrent duplicates created %d orders; there must be exactly 1" % f.count()
    assert f.count("idempotency") == 1
    f = Fixture()
    outs = in_threads([(lambda i=i: f.post(key="k%d" % i)) for i in range(8)])
    assert f.count() == 8 and len({o.json()["id"] for o in outs}) == 8, "8 different keys should make 8 distinct orders"
    # the lock must be a UNIQUE constraint, not a Python variable
    c = sqlite3.connect(f.path)
    try:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'") if "idem" in r[0].lower()]
        assert tables, "keep the keys in a sqlite table whose name contains 'idem'"
        t = tables[0]
        unique = [r for r in c.execute("PRAGMA index_list(%s)" % t) if r[2]]
        pk = [r for r in c.execute("PRAGMA table_info(%s)" % t) if r[5]]
        assert unique or pk, "the idempotency table needs a UNIQUE / PRIMARY KEY on the key"
    finally:
        c.close()


# ---------------------------------------------------------------------------- 3
def ids(r):
    return [o["id"] for o in r.json()["data"]]


def walk(f, limit, between=None):
    """Follow `next` links to the end. Returns the list of ids seen, in order."""
    seen, url, pages = [], "/v1/orders?limit=%d" % limit, 0
    while url:
        r = f.call("GET", url)
        assert r.status == 200, "GET %s -> %d %s" % (url, r.status, r.body[:100])
        body = r.json()
        assert set(body) >= {"data", "next"}, "list body needs 'data' and 'next', got %s" % sorted(body)
        assert len(body["data"]) <= limit
        seen += ids(r)
        url, pages = body["next"], pages + 1
        assert pages < 100, "pagination never ended"
        if url and between:
            between(pages)
    return seen


def m3():
    f = Fixture()
    for _ in range(12):
        f.post()
    first = f.call("GET", "/v1/orders?limit=5")
    assert first.status == 200, first.body[:100]
    assert ids(first) == [12, 11, 10, 9, 8], "newest first: expected ids 12..8, got %s" % ids(first)
    nxt = first.json()["next"]
    assert isinstance(nxt, str) and nxt.startswith("/v1/orders?"), "'next' should be a relative link like /v1/orders?limit=5&cursor=..., got %r" % nxt
    cur = re.search(r"cursor=([^&]+)", nxt)
    assert cur, "'next' must carry a cursor parameter"
    assert not re.fullmatch(r"\d+", cur.group(1)), "the cursor should be opaque, not a bare number"
    try:
        base64.urlsafe_b64decode(cur.group(1) + "=" * (-len(cur.group(1)) % 4))
    except Exception:
        raise AssertionError("the cursor should be base64 (url-safe) of (created_at, id)")
    assert walk(f, 5) == list(range(12, 0, -1)), "walking all pages should give 12..1 exactly once each"
    last = f.call("GET", "/v1/orders?limit=12").json()
    assert last["next"] is None and len(last["data"]) == 12, "when the page holds everything, next must be null (no empty extra page)"
    # rows inserted mid-pagination
    f = Fixture()
    for _ in range(12):
        f.post()
    seen = []
    r = f.call("GET", "/v1/orders?limit=5")
    seen += ids(r)
    for _ in range(3):
        f.post()                                          # new orders arrive between page 1 and page 2
    url = r.json()["next"]
    while url:
        r = f.call("GET", url)
        seen += ids(r)
        url = r.json()["next"]
    assert len(seen) == len(set(seen)), "duplicates across pages: %s" % seen
    assert seen == list(range(12, 0, -1)), "rows inserted mid-pagination must not shift the pages: got %s" % seen
    assert walk(f, 5) == list(range(15, 0, -1)), "a fresh walk should now see all 15 orders"
    # seeded random inserts between every page
    rng, f = random.Random(2024), Fixture()
    for _ in range(20):
        f.post()
    started = ids(f.call("GET", "/v1/orders?limit=50"))
    seen = walk(f, 3, between=lambda n: [f.post() for _ in range(rng.randint(0, 3))])
    assert len(seen) == len(set(seen)), "duplicates with random inserts: %s" % seen
    assert seen == started, "skipped or extra rows with random inserts: %s" % seen
    # many rows share one created_at: the id breaks the tie
    f = Fixture(frozen=True)
    for _ in range(9):
        f.post()
    assert walk(f, 2) == list(range(9, 0, -1)), "with identical timestamps the id must break ties (no skips, no repeats)"
    for q in ("limit=0", "limit=51", "limit=abc", "cursor=%21%21", "cursor=" + base64.urlsafe_b64encode(b"[1]").decode(),
              "cursor=" + base64.urlsafe_b64encode(b'["a", "b"]').decode()):
        is_problem(f.call("GET", "/v1/orders?" + q), 400)


# ---------------------------------------------------------------------------- 4
def m4():
    want = json.load(open(snapshot.SNAPSHOT))
    got = snapshot.run_scenario(mod.make_app)
    for w, g in zip(want, got):
        assert w == g, ("v1 changed!  %s\n      was: %s %s\n      now: %s %s" %
                        (w["request"], w["status"], w["body"], g["status"], g["body"]))
    assert len(want) == len(got)
    f = Fixture()
    r = f.post(dict(ORDER, currency="EUR"), version="v2")
    assert r.status == 201 and r.headers.get("location") == "/v2/orders/1", "v2 POST: 201 and Location /v2/orders/1, got %d %s" % (r.status, r.headers.get("location"))
    body = r.json()
    assert set(body) == {"id", "customer", "items", "status", "created_at", "amount_cents", "currency"}, \
        "v2 fields should be id, customer, items, status, created_at, amount_cents, currency; got %s" % sorted(body)
    assert body["amount_cents"] == 3000 and isinstance(body["amount_cents"], int), "amount_cents is an integer number of cents"
    assert body["currency"] == "EUR"
    assert f.post(version="v2").json()["currency"] == "USD", "currency defaults to USD"
    p = is_problem(f.post(dict(ORDER, currency="eur"), version="v2"), 422)
    assert "currency" in {e.get("field") for e in p.get("errors", [])}, "422 should name the 'currency' field"
    v1 = f.post(version="v1").json()
    assert v1["total"] == 30.0 and "amount_cents" not in v1 and "currency" not in v1, "v1 must keep its old shape"
    via_v2 = f.call("GET", "/v2/orders/%d" % v1["id"]).json()
    assert via_v2["amount_cents"] == 3000 and "total" not in via_v2, "v2 can read an order created through v1"
    via_v1 = f.call("GET", "/v1/orders/1").json()
    assert via_v1["total"] == 30.0 and "currency" not in via_v1, "v1 can read an order created through v2, in the v1 shape"
    lst = f.call("GET", "/v2/orders?limit=2").json()
    assert all("amount_cents" in o for o in lst["data"]) and lst["next"].startswith("/v2/orders?"), "v2 lists use v2 shapes and v2 links"
    assert [o["id"] for o in f.call("GET", lst["next"]).json()["data"]] == [1], "v2 pagination works like v1"
    f2 = Fixture()
    f2.post(key="same")
    is_problem(f2.post(version="v2", key="same"), 422)      # same key on another version = a different request
    is_problem(f.call("GET", "/v3/orders"), 404)


# ---------------------------------------------------------------------------- 5
def m5():
    f = Fixture()
    u = f.call("GET", "/admin/usage")
    assert u.status == 200, "GET /admin/usage should answer 200, got %d" % u.status
    assert u.json() == {"usage": {}}, "before any traffic, usage is {} , got %s" % u.json()
    r1 = [f.post(), f.post(key="d"), f.post(key="d"), f.call("GET", "/v1/orders/1"), f.call("GET", "/v1/orders/77"),
          f.post({"customer": ""}), f.call("DELETE", "/v1/orders/1"), f.call("GET", "/v1/orders?limit=2")]
    r2 = [f.post(version="v2"), f.call("GET", "/v2/orders/1")]
    for r in r1:
        d, s = r.headers.get("deprecation"), r.headers.get("sunset")
        assert d and s, "every v1 response (even errors and replays) needs Deprecation and Sunset headers; missing on a %d" % r.status
        assert re.fullmatch(r"@\d+", d), "Deprecation is an RFC 9745 date: '@' + Unix seconds, e.g. @1767225600; got %r" % d
        sunset = email.utils.parsedate_to_datetime(s)
        assert s.endswith("GMT") and sunset is not None, "Sunset is an HTTP-date (RFC 8594), e.g. 'Fri, 01 Jan 2027 00:00:00 GMT'; got %r" % s
        assert sunset.timestamp() > int(d[1:]), "the Sunset date must come after the Deprecation date"
    for r in r2 + [u]:
        assert "deprecation" not in r.headers and "sunset" not in r.headers, "only v1 is deprecated"
    assert f.call("GET", "/admin/usage").json() == {"usage": {"v1": 8, "v2": 2}}, \
        "usage should count every /v1 and /v2 request (errors and replays too) and not /admin itself: got %s" % f.call("GET", "/admin/usage").json()
    f.call("GET", "/v3/orders")
    assert f.call("GET", "/admin/usage").json()["usage"] == {"v1": 8, "v2": 2}, "unknown versions are not counted"
    in_threads([lambda: f.call("GET", "/v1/orders/1")] * 20)
    assert f.call("GET", "/admin/usage").json()["usage"]["v1"] == 28, "20 concurrent requests must add exactly 20 to the counter"


print("Lab 2 checks against %s.py\n" % target)
check("Milestone 1: resource basics, status codes, problem+json", m1)
check("Milestone 2: idempotency keys, even under concurrent duplicates", m2)
check("Milestone 3: cursor pagination that survives inserts", m3)
check("Milestone 4: v2 beside an unchanged v1", m4)
check("Milestone 5: Deprecation, Sunset and /admin/usage", m5)
shutil.rmtree(TMP, ignore_errors=True)
print("\n%d/5 milestones passing" % sum(results))
sys.exit(0 if all(results) else 1)
