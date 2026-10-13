"""Ordering internals. Ordering is the only module that talks to many others."""
from shop.cart import api as cart
from shop.catalog import api as catalog
from shop.payments import api as payments
from shop.shipping import api as shipping

_orders = {}
_next_id = [0]


def reset():
    _orders.clear()
    _next_id[0] = 0


def get_order(order_id):
    return dict(_orders[order_id])


def place_order(user, address):
    lines = cart.items(user)
    if not lines:
        raise ValueError("empty cart")
    total = sum(catalog.line_price(sku, qty) for sku, qty in lines)
    grams = sum(catalog.weight_of(sku) * qty for sku, qty in lines)
    taken = []
    try:
        for sku, qty in lines:
            catalog.take_stock(sku, qty)
            taken.append((sku, qty))
    except catalog.OutOfStock:
        for sku, qty in taken:
            catalog.put_back(sku, qty)
        raise
    _next_id[0] += 1
    order_id = _next_id[0]
    shipping_cost = shipping.quote(grams)
    _orders[order_id] = {"id": order_id, "user": user, "status": "PENDING", "total": total,
                         "shipping": shipping_cost, "items": lines, "address": address}
    try:
        payments.charge(order_id, user, total + shipping_cost)
    except payments.InsufficientFunds:
        for sku, qty in taken:
            catalog.put_back(sku, qty)
        _orders[order_id]["status"] = "PAYMENT_FAILED"
        return order_id
    shipping.create_shipment(order_id, address, grams)
    cart.clear(user)
    _orders[order_id]["status"] = "CONFIRMED"
    return order_id
