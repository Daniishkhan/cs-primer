"""Shopping carts."""
from ..catalog import service as catalog
from shop.db import db


def add_item(user, sku, qty):
    if sku not in db["products"]:          # peeks at the catalog's table
        raise catalog.UnknownProduct(sku)
    lines = db["carts"].setdefault(user, {})
    lines[sku] = lines.get(sku, 0) + qty


def items(user):
    return sorted(db["carts"].get(user, {}).items())


def clear(user):
    db["carts"].pop(user, None)


def is_in_any_cart(sku):
    return any(sku in lines for lines in db["carts"].values())
