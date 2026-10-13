"""Cart internals."""
from shop.catalog import api as catalog

_carts = {}               # this module's own table


def reset():
    _carts.clear()


def add_item(user, sku, qty):
    if not catalog.exists(sku):
        raise catalog.UnknownProduct(sku)
    lines = _carts.setdefault(user, {})
    lines[sku] = lines.get(sku, 0) + qty


def items(user):
    return sorted(_carts.get(user, {}).items())


def clear(user):
    _carts.pop(user, None)


def is_in_any_cart(sku):
    return any(sku in lines for lines in _carts.values())
