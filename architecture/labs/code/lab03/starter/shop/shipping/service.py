"""Quotes and shipments."""
from . import _rates
from shop.db import db, next_id
from shop.catalog.service import weight_of


def _grams(order):
    return sum(weight_of(sku) * qty for sku, qty in order["items"])


def quote_for_order(order_id):
    order = db["orders"][order_id]
    order["shipping"] = _rates.cost_cents(_grams(order))
    return order["shipping"]


def create_shipment(order_id):
    from shop.ordering import service as ordering      # imported late to dodge the circular import
    order = ordering.get_order(order_id)
    shipment_id = next_id("shipment")
    db["shipments"][shipment_id] = {"order": order_id, "to": order["address"], "grams": _grams(order)}
    order["status"] = "SHIPPED"
    return shipment_id
