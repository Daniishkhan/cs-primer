"""Turning a cart into an order."""
from shop.db import db, next_id
from shop.cart import service as cart
from shop.catalog import service as catalog
from shop.catalog.service import _apply_discount
from shop.payments import service as payments
from shop.shipping import service as shipping


def get_order(order_id):
    return db["orders"][order_id]


def place_order(user, address):
    lines = cart.items(user)
    if not lines:
        raise ValueError("empty cart")
    total = sum(_apply_discount(catalog.price_of(sku), qty) for sku, qty in lines)
    taken = []
    try:
        for sku, qty in lines:
            catalog.take_stock(sku, qty)
            taken.append((sku, qty))
    except catalog.OutOfStock:
        for sku, qty in taken:
            catalog.put_back(sku, qty)
        raise
    order_id = next_id("order")
    db["orders"][order_id] = {"id": order_id, "user": user, "status": "PENDING", "total": total,
                              "shipping": 0, "items": lines, "address": address}
    shipping.quote_for_order(order_id)
    try:
        payments.charge(order_id)
    except payments.InsufficientFunds:
        for sku, qty in taken:
            catalog.put_back(sku, qty)
        db["orders"][order_id]["status"] = "PAYMENT_FAILED"
        return order_id
    shipping.create_shipment(order_id)
    cart.clear(user)
    db["orders"][order_id]["status"] = "CONFIRMED"
    return order_id
