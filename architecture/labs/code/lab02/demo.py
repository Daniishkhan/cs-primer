"""demo.py: call the finished API directly, no server. Try it with the solution, then with your starter.

    python3 demo.py                # uses solution.py
    python3 demo.py starter
"""
import importlib
import os
import sys
import tempfile

from testing import call

mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "solution")
with tempfile.TemporaryDirectory() as d:
    app = mod.make_app(os.path.join(d, "demo.db"), clock=lambda: 1700000000)
    order = {"customer": "ana@example.com", "items": [{"sku": "mug", "qty": 2, "unit_price_cents": 1500}]}
    key = {"Idempotency-Key": "demo-1"}

    a = call(app, "POST", "/v2/orders", order, key)
    print(a.status, a.headers["location"])
    print(a.body.decode())
    b = call(app, "POST", "/v2/orders", order, key)
    print(b.status, b.headers.get("idempotent-replayed"), b.body == a.body)
    c = call(app, "POST", "/v2/orders", dict(order, customer="bo@example.com"), key)
    print(c.status, c.headers["content-type"])
    print(c.body.decode())
