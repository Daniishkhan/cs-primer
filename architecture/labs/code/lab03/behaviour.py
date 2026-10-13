"""Behaviour tests for the shop. Given: do not edit.

They talk only to shop.app, so they pass both before and after the refactor.
    python3 behaviour.py <dir-that-contains-shop>
"""
import os
import sys
import unittest

ROOT = sys.argv.pop(1) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True
from shop import app  # noqa: E402


class ShopBehaviour(unittest.TestCase):
    def setUp(self):
        app.reset()
        app.add_product("widget", "Widget", 1000, 20, 500)
        app.add_product("gadget", "Gadget", 2500, 3, 1200)
        app.set_balance("ana", 100000)

    def test_happy_path(self):
        app.add_to_cart("ana", "widget", 2)
        app.add_to_cart("ana", "gadget", 1)
        oid = app.checkout("ana", "1 Main St")
        o = app.order(oid)
        self.assertEqual(oid, 1)
        self.assertEqual(o["status"], "CONFIRMED")
        self.assertEqual(o["total"], 4500)
        self.assertEqual(o["shipping"], 940)           # 500 + 22 * 20
        self.assertEqual(app.stock("widget"), 18)
        self.assertEqual(app.stock("gadget"), 2)
        self.assertEqual(app.balance("ana"), 100000 - 4500 - 940)
        self.assertEqual(app.cart_items("ana"), [])

    def test_bulk_discount(self):
        app.add_to_cart("ana", "widget", 10)
        o = app.order(app.checkout("ana", "1 Main St"))
        self.assertEqual(o["total"], 9000)

    def test_out_of_stock_changes_nothing(self):
        app.add_to_cart("ana", "widget", 2)
        app.add_to_cart("ana", "gadget", 4)
        with self.assertRaises(Exception) as cm:
            app.checkout("ana", "1 Main St")
        self.assertEqual(type(cm.exception).__name__, "OutOfStock")
        self.assertEqual(app.stock("widget"), 20)
        self.assertEqual(app.stock("gadget"), 3)
        self.assertEqual(app.balance("ana"), 100000)
        self.assertEqual(app.cart_items("ana"), [("gadget", 4), ("widget", 2)])

    def test_payment_failure_puts_stock_back(self):
        app.set_balance("bo", 100)
        app.add_to_cart("bo", "widget", 3)
        o = app.order(app.checkout("bo", "2 Side St"))
        self.assertEqual(o["status"], "PAYMENT_FAILED")
        self.assertEqual(app.stock("widget"), 20)
        self.assertEqual(app.balance("bo"), 100)
        self.assertEqual(app.cart_items("bo"), [("widget", 3)])

    def test_empty_cart_is_rejected(self):
        with self.assertRaises(ValueError):
            app.checkout("ana", "1 Main St")

    def test_unknown_product_cannot_be_carted(self):
        with self.assertRaises(Exception) as cm:
            app.add_to_cart("ana", "ghost", 1)
        self.assertEqual(type(cm.exception).__name__, "UnknownProduct")

    def test_product_in_a_cart_cannot_be_removed(self):
        app.add_to_cart("ana", "widget", 1)
        with self.assertRaises(Exception) as cm:
            app.remove_product("widget")
        self.assertEqual(type(cm.exception).__name__, "ProductInUse")
        app.checkout("ana", "1 Main St")
        app.remove_product("widget")                    # the cart is empty now
        with self.assertRaises(Exception):
            app.stock("widget")

    def test_order_ids_count_up(self):
        for _ in range(2):
            app.add_to_cart("ana", "widget", 1)
            last = app.checkout("ana", "1 Main St")
        self.assertEqual(last, 2)


if __name__ == "__main__":
    unittest.main(verbosity=0)
