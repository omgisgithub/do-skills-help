from datetime import date
from decimal import Decimal
import unittest

from fifo import Inventory


D1, D2, D3 = date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)


class TestSpecExamples(unittest.TestCase):
    def test_half_up_rounding_once_at_end(self):
        # 2.335 -> 2.34 (float would give 2.33)
        inv = Inventory()
        inv.buy("A", 1, "2.335", D1)
        self.assertEqual(inv.sell("A", 1, D2), Decimal("2.34"))

    def test_sum_is_exact_then_rounded(self):
        # 2.345 -> 2.35 half up
        inv = Inventory()
        inv.buy("A", 1, "2.345", D1)
        self.assertEqual(inv.sell("A", 1, D2), Decimal("2.35"))

    def test_return_has_two_decimals(self):
        inv = Inventory()
        inv.buy("A", 10, 2, D1)
        result = inv.sell("A", 3, D2)
        self.assertEqual(result, Decimal("6.00"))
        self.assertEqual(str(result), "6.00")

    def test_out_of_order_purchase_consumed_oldest_first(self):
        inv = Inventory()
        inv.buy("A", 1, "5.00", D2)
        inv.buy("A", 1, "1.00", D1)  # late invoice for an earlier date
        self.assertEqual(inv.sell("A", 1, D3), Decimal("1.00"))
        self.assertEqual(inv.sell("A", 1, D3), Decimal("5.00"))

    def test_same_date_lots_in_recorded_order(self):
        inv = Inventory()
        inv.buy("A", 1, "1.00", D1)
        inv.buy("A", 1, "2.00", D1)
        self.assertEqual(inv.sell("A", 1, D1), Decimal("1.00"))

    def test_lots_dated_after_sale_not_used(self):
        inv = Inventory()
        inv.buy("A", 5, "1.00", D3)
        with self.assertRaises(ValueError):
            inv.sell("A", 1, D1)
        self.assertEqual(inv.on_hand("A"), 5)

    def test_failed_sale_leaves_inventory_unchanged(self):
        inv = Inventory()
        inv.buy("A", 2, "1.00", D1)
        inv.buy("A", 2, "3.00", D2)
        with self.assertRaises(ValueError):
            inv.sell("A", 5, D3)
        self.assertEqual(inv.on_hand("A"), 4)
        self.assertEqual(inv.lots("A"), [(D1, 2, Decimal("1.00")), (D2, 2, Decimal("3.00"))])

    def test_fully_used_lots_disappear(self):
        inv = Inventory()
        inv.buy("A", 2, "1.00", D1)
        inv.buy("A", 2, "3.00", D2)
        inv.sell("A", 2, D2)
        self.assertEqual(inv.lots("A"), [(D2, 2, Decimal("3.00"))])

    def test_on_hand_unknown_sku(self):
        self.assertEqual(Inventory().on_hand("nope"), 0)

    def test_value_exact_and_not_rounded(self):
        inv = Inventory()
        inv.buy("A", 3, "1.335", D1)
        inv.buy("B", 2, "0.5", D1)
        self.assertEqual(inv.value("A"), Decimal("4.005"))
        self.assertEqual(inv.value(), Decimal("5.005"))
        self.assertEqual(Inventory().value(), Decimal("0"))

    def test_lots_returns_copy(self):
        inv = Inventory()
        inv.buy("A", 2, "1.00", D1)
        view = inv.lots("A")
        view.clear()
        view.append((D1, 99, Decimal("9")))
        self.assertEqual(inv.on_hand("A"), 2)
        self.assertEqual(inv.lots("A"), [(D1, 2, Decimal("1.00"))])


class TestMustFail(unittest.TestCase):
    def test_buy_zero_qty(self):
        with self.assertRaises(ValueError):
            Inventory().buy("A", 0, "1", D1)

    def test_buy_negative_qty(self):
        with self.assertRaises(ValueError):
            Inventory().buy("A", -1, "1", D1)

    def test_buy_negative_cost(self):
        with self.assertRaises(ValueError):
            Inventory().buy("A", 1, "-0.01", D1)

    def test_buy_float_cost(self):
        with self.assertRaises(TypeError):
            Inventory().buy("A", 1, 2.5, D1)

    def test_buy_float_qty(self):
        with self.assertRaises(TypeError):
            Inventory().buy("A", 1.0, "1", D1)

    def test_buy_garbage_cost(self):
        with self.assertRaises(ValueError):
            Inventory().buy("A", 1, "abc", D1)

    def test_buy_nan_cost(self):
        with self.assertRaises(ValueError):
            Inventory().buy("A", 1, "NaN", D1)

    def test_sell_zero_qty(self):
        inv = Inventory()
        inv.buy("A", 1, "1", D1)
        with self.assertRaises(ValueError):
            inv.sell("A", 0, D1)

    def test_sell_negative_qty(self):
        inv = Inventory()
        inv.buy("A", 1, "1", D1)
        with self.assertRaises(ValueError):
            inv.sell("A", -1, D1)

    def test_sell_float_qty(self):
        inv = Inventory()
        inv.buy("A", 1, "1", D1)
        with self.assertRaises(TypeError):
            inv.sell("A", 1.0, D1)

    def test_sell_unknown_sku(self):
        with self.assertRaises(ValueError):
            Inventory().sell("A", 1, D1)

    def test_sell_more_than_on_hand(self):
        inv = Inventory()
        inv.buy("A", 1, "1", D1)
        with self.assertRaises(ValueError):
            inv.sell("A", 2, D1)
        self.assertEqual(inv.on_hand("A"), 1)


if __name__ == "__main__":
    unittest.main()
