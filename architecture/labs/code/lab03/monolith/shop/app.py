"""The entry point: a small facade the behaviour tests (and a web layer, one day) call."""
import shop.catalog.service as catalog
from shop.cart import service as cart
from shop.ordering import service as ordering
from shop.payments import service as payments
from shop import db as _shared


def reset():
    _shared.reset()


def add_product(sku, name, price_cents, stock, weight_g):
    catalog.add_product(sku, name, price_cents, stock, weight_g)


def remove_product(sku):
    catalog.remove_product(sku)


def set_balance(user, cents):
    payments.set_balance(user, cents)


def add_to_cart(user, sku, qty):
    cart.add_item(user, sku, qty)


def checkout(user, address):
    return ordering.place_order(user, address)


def order(order_id):
    return dict(ordering.get_order(order_id))


def stock(sku):
    return catalog.stock_of(sku)


def balance(user):
    return payments.balance_of(user)


def cart_items(user):
    return cart.items(user)
