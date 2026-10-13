"""Wallets and charges."""
from .. import db as _shared
from ..ordering import service as ordering


class InsufficientFunds(Exception):
    pass


def set_balance(user, cents):
    _shared.db["wallets"][user] = cents


def balance_of(user):
    return _shared.db["wallets"].get(user, 0)


def charge(order_id):
    order = ordering.get_order(order_id)
    amount = order["total"] + order["shipping"]
    if balance_of(order["user"]) < amount:
        raise InsufficientFunds(order["user"])
    _shared.db["wallets"][order["user"]] -= amount
    payment_id = _shared.next_id("payment")
    _shared.db["payments"][payment_id] = {"order": order_id, "amount": amount}
    _shared.db["orders"][order_id]["status"] = "PAID"      # writes into the ordering table
    return payment_id
