"""Products, prices and stock."""
from shop.db import db
from shop.cart import service as cart


class UnknownProduct(Exception):
    pass


class OutOfStock(Exception):
    pass


class ProductInUse(Exception):
    pass


def _apply_discount(price_cents, qty):
    """Ten or more of the same item get 10% off."""
    total = price_cents * qty
    return total * 9 // 10 if qty >= 10 else total


def add_product(sku, name, price_cents, stock, weight_g):
    db["products"][sku] = {"name": name, "price": price_cents, "stock": stock, "weight": weight_g}


def remove_product(sku):
    if cart.is_in_any_cart(sku):
        raise ProductInUse(sku)
    db["products"].pop(sku, None)


def price_of(sku):
    if sku not in db["products"]:
        raise UnknownProduct(sku)
    return db["products"][sku]["price"]


def stock_of(sku):
    return db["products"][sku]["stock"]


def weight_of(sku):
    return db["products"][sku]["weight"]


def take_stock(sku, qty):
    product = db["products"][sku]
    if product["stock"] < qty:
        raise OutOfStock(sku)
    product["stock"] -= qty


def put_back(sku, qty):
    db["products"][sku]["stock"] += qty
