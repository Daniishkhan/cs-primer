"""Shipping internals. It is handed the weight; it never asks the catalog or the orders."""
from . import _rates

_shipments = {}
_next_id = [0]


def reset():
    _shipments.clear()
    _next_id[0] = 0


def quote(grams):
    return _rates.cost_cents(grams)


def create_shipment(order_ref, address, grams):
    _next_id[0] += 1
    _shipments[_next_id[0]] = {"order": order_ref, "to": address, "grams": grams}
    return _next_id[0]
