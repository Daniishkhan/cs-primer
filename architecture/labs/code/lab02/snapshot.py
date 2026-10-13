"""snapshot.py: the v1 compatibility snapshot (given; do not edit).

`v1_snapshot.json` holds the exact answers the v1 API gave after milestone 3, before v2
existed. `run_scenario(app)` replays the same requests against any app; milestone 4 insists
the bytes are identical, because some client somewhere parses them (Hyrum's law).

    python3 snapshot.py solution     # replay solution.py against the snapshot
    python3 snapshot.py --record     # (maintainers only) rewrite the snapshot
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from testing import call  # noqa: E402

SNAPSHOT = os.path.join(HERE, "v1_snapshot.json")

ORDER = {"customer": "ana@example.com",
         "items": [{"sku": "mug", "qty": 2, "unit_price_cents": 1500}, {"sku": "pen", "qty": 3, "unit_price_cents": 199}]}
SCENARIO = [
    ("POST", "/v1/orders", ORDER, {"Idempotency-Key": "snap-1"}),
    ("POST", "/v1/orders", ORDER, {"Idempotency-Key": "snap-1"}),                       # replay
    ("POST", "/v1/orders", dict(ORDER, customer="bo@example.com"), None),
    ("POST", "/v1/orders", dict(ORDER, customer="cy@example.com", items=[{"sku": "lamp", "qty": 1, "unit_price_cents": 1999}]), None),
    ("GET", "/v1/orders/1", None, None),
    ("GET", "/v1/orders/3", None, None),
    ("GET", "/v1/orders/99", None, None),
    ("GET", "/v1/orders?limit=2", None, None),
    ("GET", "/v1/orders?limit=2&cursor=WzE3MDAwMDAxMjAsIDJd", None, None),
    ("GET", "/v1/orders?limit=0", None, None),
    ("GET", "/v1/orders?cursor=garbage", None, None),
    ("POST", "/v1/orders", {"customer": "", "items": [{"sku": "x", "qty": 0}]}, None),
    ("POST", "/v1/orders", "{oops", None),
    ("POST", "/v1/orders", dict(ORDER, customer="other"), {"Idempotency-Key": "snap-1"}),  # key reuse
    ("DELETE", "/v1/orders/1", None, None),
    ("GET", "/v1/nope", None, None),
]


def tick_clock():
    state = {"t": 1700000000}

    def clock():
        state["t"] += 60
        return state["t"]
    return clock


def run_scenario(make_app):
    with tempfile.TemporaryDirectory() as d:
        app = make_app(os.path.join(d, "snap.db"), tick_clock())
        out = []
        for method, path, body, headers in SCENARIO:
            r = call(app, method, path, body, headers)
            out.append({"request": "%s %s" % (method, path), "status": r.status,
                        "content_type": r.headers.get("content-type"), "location": r.headers.get("location"),
                        "body": r.body.decode()})
        return out


if __name__ == "__main__":
    import importlib
    if "--record" in sys.argv:
        mod = importlib.import_module("solution")
        with open(SNAPSHOT, "w") as f:
            json.dump(run_scenario(mod.make_app), f, indent=1)
        print("recorded", SNAPSHOT)
    else:
        mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "solution")
        want = json.load(open(SNAPSHOT))
        got = run_scenario(mod.make_app)
        bad = [(w["request"], w["body"], g["body"]) for w, g in zip(want, got) if w != g]
        print("v1 snapshot:", "identical" if not bad else "DIFFERENT: %s" % bad[0])
