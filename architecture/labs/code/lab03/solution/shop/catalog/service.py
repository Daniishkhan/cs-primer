"""Catalog internals. Nobody outside this package imports this file."""


class UnknownProduct(Exception):
    pass


class OutOfStock(Exception):
    pass


class ProductInUse(Exception):
    pass


_products = {}            # this module's own table
_removal_guards = []      # callables(sku) -> bool: "is somebody still using this product?"


def reset():
    _products.clear()
    del _removal_guards[:]


def _apply_discount(price_cents, qty):
    """Ten or more of the same item get 10% off."""
    total = price_cents * qty
    return total * 9 // 10 if qty >= 10 else total


def add_product(sku, name, price_cents, stock, weight_g):
    _products[sku] = {"name": name, "price": price_cents, "stock": stock, "weight": weight_g}


def exists(sku):
    return sku in _products


def remove_product(sku):
    if any(guard(sku) for guard in _removal_guards):
        raise ProductInUse(sku)
    _products.pop(sku, None)


def _get(sku):
    if sku not in _products:
        raise UnknownProduct(sku)
    return _products[sku]


def price_of(sku):
    return _get(sku)["price"]


def line_price(sku, qty):
    return _apply_discount(_get(sku)["price"], qty)


def stock_of(sku):
    return _products[sku]["stock"]


def weight_of(sku):
    return _get(sku)["weight"]


def take_stock(sku, qty):
    product = _get(sku)
    if product["stock"] < qty:
        raise OutOfStock(sku)
    product["stock"] -= qty


def put_back(sku, qty):
    _get(sku)["stock"] += qty


def add_removal_guard(guard):
    _removal_guards.append(guard)
