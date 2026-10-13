"""domain_tests.py: unit tests for domain.py (milestone 2). Given; read them, they are the spec.

No database, no JSON, no fakes: every test calls a pure function and looks at the answer.
check.py imports the domain module from the directory it is checking and passes it in."""
import unittest


def make_tests(domain):
    P = domain.Product
    CATALOG = {"mug": P("mug", 1500, 40), "pen": P("pen", 250, 500), "desk": P("desk", 45000, 5)}

    def req(items, coupon=None):
        return domain.OrderRequest("ana@example.com", tuple(items), coupon)

    def total(items, coupon=None):
        lines = domain.build_lines(items, CATALOG)
        return domain.price(lines, req(items, coupon))

    class ParseTests(unittest.TestCase):
        def test_valid_request(self):
            r = domain.parse_request({"customer": "a@b.c", "items": [{"sku": "mug", "qty": 2}]})
            self.assertEqual((r.customer, tuple(r.items), r.coupon, r.card),
                             ("a@b.c", (("mug", 2),), None, "tok_ok"))

        def test_rejections(self):
            bad = [({}, "customer is required"),
                   ({"customer": " ", "items": [{"sku": "x", "qty": 1}]}, "customer is required"),
                   ({"customer": "a", "items": []}, "an order needs at least one line"),
                   ({"customer": "a", "items": [{"sku": "x", "qty": 0}]}, "invalid line"),
                   ({"customer": "a", "items": [{"sku": "x", "qty": True}]}, "invalid line"),
                   ({"customer": "a", "items": [{"sku": "x", "qty": 1}, {"sku": "x", "qty": 1}]}, "duplicate sku 'x'"),
                   ({"customer": "a", "items": [{"sku": "x", "qty": 1}], "coupon": 3}, "invalid coupon"),
                   ({"customer": "a", "items": [{"sku": "x", "qty": 1}], "card": 3}, "invalid card")]
            for data, message in bad:
                with self.assertRaises(domain.ValidationError) as cm:
                    domain.parse_request(data)
                self.assertEqual(str(cm.exception), message)

    class StockTests(unittest.TestCase):
        def test_lines_carry_catalogue_prices(self):
            lines = domain.build_lines([("mug", 2), ("pen", 1)], CATALOG)
            self.assertEqual([(l.sku, l.qty, l.unit_price_cents) for l in lines],
                             [("mug", 2, 1500), ("pen", 1, 250)])

        def test_unknown_sku_is_a_validation_error(self):
            with self.assertRaises(domain.UnknownSku) as cm:
                domain.build_lines([("ghost", 1)], CATALOG)
            self.assertEqual(str(cm.exception), "unknown sku 'ghost'")
            self.assertTrue(issubclass(domain.UnknownSku, domain.ValidationError))

        def test_out_of_stock(self):
            with self.assertRaises(domain.OutOfStock) as cm:
                domain.build_lines([("desk", 6)], CATALOG)
            self.assertEqual(str(cm.exception), "insufficient stock for 'desk'")
            domain.build_lines([("desk", 5)], CATALOG)          # exactly the stock is fine

    class PricingTests(unittest.TestCase):
        def test_small_order_pays_shipping(self):
            p = total([("mug", 2)])                              # 30.00 < 50.00
            self.assertEqual((p.subtotal_cents, p.discount_cents, p.shipping_cents, p.total_cents),
                             (3000, 0, 499, 3499))

        def test_free_shipping_from_fifty(self):
            self.assertEqual(total([("mug", 4)]).total_cents, 6000)            # 60.00: no fee
            self.assertEqual(total([("mug", 3), ("pen", 2)]).total_cents, 5000)  # exactly 50.00: no fee
            self.assertEqual(total([("mug", 3), ("pen", 1)]).total_cents, 4750 + 499)

        def test_bulk_discount_on_lines_of_ten_or_more(self):
            p = total([("pen", 10)])                             # 25.00, 10% off = 2.50, then shipping
            self.assertEqual((p.discount_cents, p.total_cents), (250, 2250 + 499))
            self.assertEqual(total([("pen", 9)]).discount_cents, 0)

        def test_coupon_is_a_flat_500_but_never_below_zero(self):
            p = total([("mug", 4)], "WELCOME5")
            self.assertEqual((p.discount_cents, p.total_cents), (500, 5500))
            p = total([("pen", 1)], "WELCOME5")                  # coupon capped at the basket
            self.assertEqual((p.discount_cents, p.total_cents), (250, 499))
            with self.assertRaises(domain.ValidationError):
                total([("mug", 1)], "HALFOFF")

        def test_big_baskets_get_five_percent(self):
            self.assertEqual(total([("mug", 14)]).total_cents, 18900)   # bulk -> 189.00, under 200.00: no 5%
            p = total([("desk", 1), ("pen", 4)])                         # 460.00 -> 5% = 23.00
            self.assertEqual((p.discount_cents, p.total_cents), (2300, 43700))

        def test_hold_threshold(self):
            self.assertFalse(domain.requires_hold(49999))
            self.assertTrue(domain.requires_hold(50000))

        def test_confirmation_email(self):
            line = domain.Line("mug", 2, 1500)
            paid = domain.Order(7, "ana@example.com", (line,), 3499, "PAID")
            held = domain.Order(8, "ana@example.com", (line,), 90000, "ON_HOLD")
            self.assertEqual(domain.confirmation_email(paid),
                             ("Order #7 confirmed", "Thanks ana@example.com! We charged 34.99."))
            self.assertEqual(domain.confirmation_email(held),
                             ("Order #8 is on hold", "Thanks ana@example.com! Your order of 900.00 is being reviewed."))

    return unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c)
                              for c in (ParseTests, StockTests, PricingTests))
