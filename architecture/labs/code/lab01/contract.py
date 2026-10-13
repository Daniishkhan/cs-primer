"""contract.py: one test suite that EVERY OrderRepository must pass (milestone 4). Given.

If the in-memory repo and the sqlite repo both pass it, the use case cannot tell them
apart, which is exactly what "interchangeable adapter" means."""
import unittest


def make_contract(domain, factory, label):
    """factory(products) -> a repository seeded with those Product objects."""
    P, Line, Order = domain.Product, domain.Line, domain.Order
    SEED = [P("mug", 1500, 10), P("pen", 250, 100)]

    def order(customer="ana@example.com", lines=(Line("mug", 2, 1500),), total=3499, status="PAID"):
        return Order(None, customer, tuple(lines), total, status)

    class Contract(unittest.TestCase):
        def setUp(self):
            self.repo = factory(SEED)

        def test_get_product(self):
            self.assertEqual(self.repo.get_product("mug"), P("mug", 1500, 10))
            self.assertIsNone(self.repo.get_product("ghost"))

        def test_ids_start_at_one_and_grow(self):
            self.assertEqual(self.repo.save_order(order()), 1)
            self.assertEqual(self.repo.save_order(order()), 2)

        def test_round_trip(self):
            o = order(lines=(Line("mug", 2, 1500), Line("pen", 3, 250)), total=4249, status="ON_HOLD")
            oid = self.repo.save_order(o)
            got = self.repo.get_order(oid)
            self.assertEqual(got.id, oid)
            self.assertEqual((got.customer, got.total_cents, got.status), (o.customer, 4249, "ON_HOLD"))
            self.assertEqual([tuple((l.sku, l.qty, l.unit_price_cents)) for l in got.lines],
                             [("mug", 2, 1500), ("pen", 3, 250)])      # order of lines preserved

        def test_missing_order_is_none(self):
            self.assertIsNone(self.repo.get_order(1))
            self.repo.save_order(order())
            self.assertIsNone(self.repo.get_order(99))

        def test_saving_decrements_stock(self):
            self.repo.save_order(order(lines=(Line("mug", 2, 1500), Line("pen", 5, 250))))
            self.assertEqual(self.repo.get_product("mug").stock, 8)
            self.assertEqual(self.repo.get_product("pen").stock, 95)
            self.repo.save_order(order(lines=(Line("mug", 8, 1500),)))
            self.assertEqual(self.repo.get_product("mug").stock, 0)

        def test_prices_in_a_saved_order_are_a_snapshot(self):
            oid = self.repo.save_order(order())
            self.assertEqual(self.repo.get_order(oid).lines[0].unit_price_cents, 1500)

    Contract.__name__ = Contract.__qualname__ = "Contract_" + label
    return Contract
