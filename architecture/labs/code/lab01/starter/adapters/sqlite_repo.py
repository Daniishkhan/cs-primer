"""MILESTONE 4: the sqlite3 OrderRepository. ALL SQL in the system lives in this file.

class SqliteRepo(conn): create the three tables (products, orders, order_lines) if they
do not exist, and implement the same four methods as InMemoryRepo. save_order must write
the order, its lines and the stock change in ONE transaction (`with self._conn:`).
Same contract, same tests.
"""
from domain import Line, Order, Product


class SqliteRepo:
    def __init__(self, conn):
        raise NotImplementedError("TODO milestone 4: SqliteRepo.__init__ (create tables)")

    def add_product(self, product: Product) -> None:
        raise NotImplementedError("TODO milestone 4: SqliteRepo.add_product")

    def get_product(self, sku):
        raise NotImplementedError("TODO milestone 4: SqliteRepo.get_product")

    def save_order(self, order: Order) -> int:
        raise NotImplementedError("TODO milestone 4: SqliteRepo.save_order")

    def get_order(self, order_id):
        raise NotImplementedError("TODO milestone 4: SqliteRepo.get_order")
