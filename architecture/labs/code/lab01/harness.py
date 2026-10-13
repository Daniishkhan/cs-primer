"""harness.py: the characterisation-test harness (given; do not edit).

A characterisation test does not say what the code SHOULD do. It records what the code
DOES do, so a refactor can be proved to change nothing. This file:

  * defines the seeded catalogue and a fixed list of requests (hand-written edge cases
    plus 60 pseudo-random ones from random.Random(2005));
  * replays them against any handler and records every response, every payment charge,
    every email and the final stock levels;
  * holds `golden.json`, the recording made from legacy.py.

    python3 harness.py            # replay legacy.py and compare with golden.json
    python3 harness.py --record   # re-record golden.json (only if you change the scenario!)
"""
import json
import os
import random
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden.json")

# (sku, price_cents, stock)
PRODUCTS = [("mug", 1500, 40), ("pen", 250, 500), ("lamp", 6000, 12),
            ("desk", 45000, 5), ("sticker", 100, 30)]


def post(body):
    return {"method": "POST", "path": "/orders", "body": body if isinstance(body, str) else json.dumps(body)}


def get(path):
    return {"method": "GET", "path": path, "body": None}


def hand_written():
    """Edge cases, one per branch of the legacy code."""
    c = "ana@example.com"
    return [
        post({"customer": c, "items": [{"sku": "mug", "qty": 2}]}),                          # plain, shipping applies
        post({"customer": c, "items": [{"sku": "lamp", "qty": 1}], "coupon": "WELCOME5"}),   # coupon
        post({"customer": c, "items": [{"sku": "pen", "qty": 10}]}),                         # bulk discount
        post({"customer": c, "items": [{"sku": "pen", "qty": 100}, {"sku": "lamp", "qty": 1}]}),  # big basket 5%
        post({"customer": c, "items": [{"sku": "desk", "qty": 2}]}),                         # ON_HOLD, not charged
        post({"customer": "bob@example.com", "items": [{"sku": "mug", "qty": 1}], "card": "tok_decline"}),  # 402
        post({"customer": c, "items": [{"sku": "desk", "qty": 4}]}),                         # 409 stock (3 left)
        post({"customer": c, "items": [{"sku": "ghost", "qty": 1}]}),                        # unknown sku
        post({"customer": c, "items": []}),                                                  # empty
        post({"customer": "  ", "items": [{"sku": "mug", "qty": 1}]}),                       # blank customer
        post({"customer": c, "items": [{"sku": "mug", "qty": 0}]}),                          # invalid line
        post({"customer": c, "items": [{"sku": "mug", "qty": True}]}),                       # bool is not a qty
        post({"customer": c, "items": [{"sku": "mug", "qty": 1}, {"sku": "mug", "qty": 2}]}),  # duplicate sku
        post({"customer": c, "items": [{"sku": "mug", "qty": 1}], "coupon": "HALFOFF"}),     # unknown coupon
        post({"customer": c, "items": [{"sku": "mug", "qty": 1}], "coupon": 5}),             # bad coupon type
        post({"customer": c, "items": [{"sku": "mug", "qty": 1}], "card": 7}),               # bad card type
        post("{not json"),                                                                   # malformed
        post("[1, 2]"),                                                                      # JSON but not an object
        {"method": "POST", "path": "/orders", "body": None},                                 # no body
        {"method": "DELETE", "path": "/orders", "body": None},                               # 405
        {"method": "POST", "path": "/orders/1", "body": None},                               # 405
        get("/orders/1"), get("/orders/2"), get("/orders/5"), get("/orders/999"),            # reads
        get("/orders/abc"), get("/nowhere"),                                                 # 404 route
        post({"customer": c, "items": [{"sku": "sticker", "qty": 30}]}),                     # sells out sticker
        post({"customer": c, "items": [{"sku": "sticker", "qty": 1}]}),                      # now 409
    ]


def generated(n=60):
    rng = random.Random(2005)
    skus = [p[0] for p in PRODUCTS] + ["ghost"]
    out = []
    for i in range(n):
        picked = rng.sample(skus, rng.randint(1, 3))
        items = [{"sku": s, "qty": rng.choice([1, 1, 1, 2, 2, 3, 5, 10, 12])} for s in picked]
        body = {"customer": "user%d@example.com" % rng.randint(1, 6), "items": items}
        if rng.random() < 0.3:
            body["coupon"] = "WELCOME5"
        if rng.random() < 0.15:
            body["card"] = "tok_decline"
        out.append(post(body))
        if rng.random() < 0.3:
            out.append(get("/orders/%d" % rng.randint(1, 25)))
    return out


def requests():
    return hand_written() + generated()


def record(handle, reqs, charges, emails, stock):
    """Replay `reqs` through handle(request) -> (status, body).

    charges() -> list of (customer, cents), emails() -> list of (to, subject, body),
    stock() -> {sku: remaining}. Returns a JSON-friendly dict."""
    responses = []
    for r in reqs:
        status, body = handle(r)
        responses.append([status, body])
    return {"responses": json.loads(json.dumps(responses)),
            "charges": [list(c) for c in charges()],
            "emails": [list(e) for e in emails()],
            "stock": stock()}


def run_legacy(reqs=None, legacy=None):
    if legacy is None:
        import legacy
    del legacy.CHARGES[:], legacy.SENT_EMAILS[:]
    conn = sqlite3.connect(":memory:")
    legacy.init_db(conn, PRODUCTS)
    out = record(lambda r: legacy.handle_request(conn, r), reqs if reqs is not None else requests(),
                 lambda: legacy.CHARGES, lambda: legacy.SENT_EMAILS,
                 lambda: dict(conn.execute("SELECT sku, stock FROM products")))
    conn.close()
    return out


def first_difference(want, got, reqs=None):
    """Human-readable first mismatch between two recordings, or None."""
    reqs = reqs if reqs is not None else requests()
    for i, (w, g) in enumerate(zip(want["responses"], got["responses"])):
        if w != g:
            r = reqs[i] if i < len(reqs) else "?"
            return "request #%d %s %s\n    legacy : %s\n    yours  : %s" % (i, r["method"], r["path"], w, g)
    if len(want["responses"]) != len(got["responses"]):
        return "different number of responses"
    for key in ("charges", "emails", "stock"):
        if want[key] != got[key]:
            return "%s differ\n    legacy : %s\n    yours  : %s" % (key, want[key], got[key])
    return None


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    if "--record" in sys.argv:
        with open(GOLDEN, "w") as f:
            json.dump(run_legacy(), f, indent=1, sort_keys=True)
        print("recorded", GOLDEN)
    else:
        with open(GOLDEN) as f:
            want = json.load(f)
        got = run_legacy()
        diff = first_difference(want, got)
        codes = {}
        for s, _ in got["responses"]:
            codes[s] = codes.get(s, 0) + 1
        print("requests replayed:", len(got["responses"]))
        print("status codes     :", dict(sorted(codes.items())))
        print("payments charged :", len(got["charges"]), "  emails sent:", len(got["emails"]))
        print("legacy matches golden.json:", "yes" if diff is None else "NO\n  " + diff)
