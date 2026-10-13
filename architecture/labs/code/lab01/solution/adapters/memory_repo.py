"""An in-memory OrderRepository: fast, for tests and demos."""
from dataclasses import replace

from domain import Order, Product


class InMemoryRepo:
    def __init__(self):
        self._products = {}
        self._orders = {}
        self._next_id = 1

    def add_product(self, product: Product) -> None:       # set-up helper, not part of the port
        self._products[product.sku] = product

    def get_product(self, sku):
        return self._products.get(sku)

    def save_order(self, order: Order) -> int:
        order_id, self._next_id = self._next_id, self._next_id + 1
        self._orders[order_id] = replace(order, id=order_id)
        for line in order.lines:
            p = self._products[line.sku]
            self._products[line.sku] = replace(p, stock=p.stock - line.qty)
        return order_id

    def get_order(self, order_id):
        return self._orders.get(order_id)
