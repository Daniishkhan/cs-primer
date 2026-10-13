"""The entry point (composition root): wires the modules together, then offers a small facade."""
from shop.cart import api as cart
from shop.catalog import api as catalog
from shop.ordering import api as ordering
from shop.payments import api as payments
from shop.shipping import api as shipping


def reset():
    for module in (catalog, cart, ordering, payments, shipping):
        module.reset()
    # catalog must not import cart, so the wiring happens here, where everything may meet
    catalog.add_removal_guard(cart.is_in_any_cart)


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
    return ordering.get_order(order_id)


def stock(sku):
    return catalog.stock_of(sku)


def balance(user):
    return payments.balance_of(user)


def cart_items(user):
    return cart.items(user)
