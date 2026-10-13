"""Payments internals: wallets and the payment log. It knows nothing about orders."""


class InsufficientFunds(Exception):
    pass


_wallets = {}
_payments = {}
_next_id = [0]


def reset():
    _wallets.clear()
    _payments.clear()
    _next_id[0] = 0


def set_balance(user, cents):
    _wallets[user] = cents


def balance_of(user):
    return _wallets.get(user, 0)


def charge(order_ref, user, amount_cents):
    """Take amount_cents from user's wallet. order_ref is just a label we store."""
    if balance_of(user) < amount_cents:
        raise InsufficientFunds(user)
    _wallets[user] -= amount_cents
    _next_id[0] += 1
    _payments[_next_id[0]] = {"order": order_ref, "amount": amount_cents}
    return _next_id[0]
