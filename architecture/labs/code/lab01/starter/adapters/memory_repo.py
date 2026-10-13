"""MILESTONE 4: an in-memory OrderRepository.

class InMemoryRepo with
    add_product(product)      set-up helper used by the tests (not part of the port)
    get_product(sku), save_order(order) -> id, get_order(order_id)
Ids start at 1. save_order must also reduce stock. Run `python3 check.py` to see the
shared contract tests (contract.py) it has to pass.
"""
from domain import Order, Product


class InMemoryRepo:
    def add_product(self, product: Product) -> None:
        raise NotImplementedError("TODO milestone 4: InMemoryRepo.add_product")

    def get_product(self, sku):
        raise NotImplementedError("TODO milestone 4: InMemoryRepo.get_product")

    def save_order(self, order: Order) -> int:
        raise NotImplementedError("TODO milestone 4: InMemoryRepo.save_order")

    def get_order(self, order_id):
        raise NotImplementedError("TODO milestone 4: InMemoryRepo.get_order")
