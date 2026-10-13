"""legacy.py: the order service everybody is afraid to touch.

One function does everything: it parses a fake HTTP request, validates it, runs SQL,
applies the pricing rules, calls the payment provider, sends the email and builds the
response. It works. Your job (see lab-01-hexagonal.html) is to move it into a
domain / ports / app / adapters layout WITHOUT changing a single observable behaviour.

Request shape (a plain dict standing in for an HTTP request):
    {"method": "POST", "path": "/orders", "body": '{"customer": "ana@example.com", ...}'}
Response shape: (status_code, dict)
"""
import json
import re
import sqlite3

# The "payment provider" and the "mail server" are stubs that record what they were asked.
CHARGES = []        # (customer, amount_cents)
SENT_EMAILS = []    # (to, subject, body)


def init_db(conn, products):
    conn.execute("CREATE TABLE products (sku TEXT PRIMARY KEY, price_cents INTEGER, stock INTEGER)")
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, "
                 "status TEXT, total_cents INTEGER)")
    conn.execute("CREATE TABLE order_lines (order_id INTEGER, sku TEXT, qty INTEGER, unit_price_cents INTEGER)")
    conn.executemany("INSERT INTO products VALUES (?, ?, ?)", products)
    conn.commit()


def handle_request(conn, request):
    method, path = request["method"], request["path"]

    # ---- routing -------------------------------------------------------------------
    m = re.match(r"^/orders/(\d+)$", path)
    if path == "/orders":
        if method != "POST":
            return 405, {"error": "method not allowed"}
    elif m:
        if method != "GET":
            return 405, {"error": "method not allowed"}
        row = conn.execute("SELECT id, customer, status, total_cents FROM orders WHERE id = ?",
                           (int(m.group(1)),)).fetchone()
        if row is None:
            return 404, {"error": "order not found"}
        lines = conn.execute("SELECT sku, qty, unit_price_cents FROM order_lines "
                             "WHERE order_id = ? ORDER BY rowid", (row[0],)).fetchall()
        return 200, {"id": row[0], "customer": row[1], "status": row[2], "total_cents": row[3],
                     "lines": [{"sku": s, "qty": q, "unit_price_cents": u} for s, q, u in lines]}
    else:
        return 404, {"error": "no such route"}

    # ---- POST /orders: parse ---------------------------------------------------------
    try:
        data = json.loads(request.get("body") or "")
    except ValueError:
        return 400, {"error": "malformed request"}
    if not isinstance(data, dict):
        return 400, {"error": "malformed request"}

    customer = data.get("customer")
    if not isinstance(customer, str) or not customer.strip():
        return 422, {"error": "customer is required"}
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return 422, {"error": "an order needs at least one line"}
    items, seen = [], set()
    for it in raw_items:
        if (not isinstance(it, dict) or not isinstance(it.get("sku"), str)
                or not isinstance(it.get("qty"), int) or isinstance(it.get("qty"), bool)
                or it["qty"] < 1):
            return 422, {"error": "invalid line"}
        if it["sku"] in seen:
            return 422, {"error": "duplicate sku '%s'" % it["sku"]}
        seen.add(it["sku"])
        items.append((it["sku"], it["qty"]))
    coupon = data.get("coupon")
    if coupon is not None and not isinstance(coupon, str):
        return 422, {"error": "invalid coupon"}
    card = data.get("card", "tok_ok")
    if not isinstance(card, str):
        return 422, {"error": "invalid card"}

    # ---- catalogue + stock rules -----------------------------------------------------
    lines = []
    for sku, qty in items:
        row = conn.execute("SELECT price_cents, stock FROM products WHERE sku = ?", (sku,)).fetchone()
        if row is None:
            return 422, {"error": "unknown sku '%s'" % sku}
        if qty > row[1]:
            return 409, {"error": "insufficient stock for '%s'" % sku}
        lines.append((sku, qty, row[0]))

    # ---- pricing rules ---------------------------------------------------------------
    subtotal = sum(q * p for _, q, p in lines)
    bulk = sum((q * p) * 10 // 100 for _, q, p in lines if q >= 10)    # 10% off lines of 10+
    after = subtotal - bulk
    coupon_off = 0
    if coupon is not None:
        if coupon != "WELCOME5":
            return 422, {"error": "unknown coupon '%s'" % coupon}
        coupon_off = min(500, after)                                    # flat 5.00 off
    after -= coupon_off
    big_off = after * 5 // 100 if after >= 20000 else 0                 # 5% off big baskets
    after -= big_off
    shipping = 499 if after < 5000 else 0                               # free shipping at 50.00
    total = after + shipping

    # ---- payment (orders of 500.00+ are held for review and not charged yet) ---------
    status = "ON_HOLD" if total >= 50000 else "PAID"
    if status == "PAID":
        CHARGES.append((customer, total))
        if card == "tok_decline":
            return 402, {"error": "payment declined"}

    # ---- persistence ------------------------------------------------------------------
    cur = conn.execute("INSERT INTO orders (customer, status, total_cents) VALUES (?, ?, ?)",
                       (customer, status, total))
    order_id = cur.lastrowid
    for sku, qty, price in lines:
        conn.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?)", (order_id, sku, qty, price))
        conn.execute("UPDATE products SET stock = stock - ? WHERE sku = ?", (qty, sku))
    conn.commit()

    # ---- notification -----------------------------------------------------------------
    money = "%d.%02d" % (total // 100, total % 100)
    if status == "PAID":
        SENT_EMAILS.append((customer, "Order #%d confirmed" % order_id,
                            "Thanks %s! We charged %s." % (customer, money)))
    else:
        SENT_EMAILS.append((customer, "Order #%d is on hold" % order_id,
                            "Thanks %s! Your order of %s is being reviewed." % (customer, money)))

    return 201, {"id": order_id, "status": status, "total_cents": total}
