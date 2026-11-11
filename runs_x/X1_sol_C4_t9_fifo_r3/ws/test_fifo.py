from datetime import date
from decimal import Decimal, localcontext
import unittest
from fifo import Inventory


def test_simple_sale() -> None:
    inv = Inventory()
    inv.buy("A", 10, "2.00", date(2026, 1, 1))
    assert inv.sell("A", 4, date(2026, 1, 5)) == Decimal("8.00")
    assert inv.on_hand("A") == 6


def test_two_lots() -> None:
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 5, "3.00", date(2026, 1, 2))
    assert inv.sell("A", 3, date(2026, 1, 3)) == Decimal("5.00")
    assert inv.on_hand("A") == 4


def test_float_rejected() -> None:
    inv = Inventory()
    try:
        inv.buy("A", 1, 1.5, date(2026, 1, 1))
    except TypeError:
        return
    raise AssertionError("float accepted")


class InventoryRegressionTests(unittest.TestCase):
    """Check costing and stock against the documented contract."""

    def test_sell_rounds_total_once_half_up(self) -> None:
        inv = Inventory()
        inv.buy("A", 1, "1.005", date(2026, 1, 1))
        inv.buy("A", 1, "1.005", date(2026, 1, 2))

        self.assertEqual(inv.sell("A", 2, date(2026, 1, 2)), Decimal("2.01"))
        inv.buy("A", 1, "2.345", date(2026, 1, 3))
        result = inv.sell("A", 1, date(2026, 1, 3))

        self.assertEqual(result, Decimal("2.35"))
        self.assertEqual(result.as_tuple().exponent, -2)

    def test_buy_sorts_dates_stably(self) -> None:
        inv = Inventory()
        inv.buy("A", 1, "3", date(2026, 1, 3))
        inv.buy("A", 1, "1", date(2026, 1, 1))
        inv.buy("A", 1, "2", date(2026, 1, 1))

        self.assertEqual([lot[2] for lot in inv.lots("A")],
                         [Decimal("1"), Decimal("2"), Decimal("3")])
        self.assertEqual(inv.sell("A", 2, date(2026, 1, 3)), Decimal("3.00"))
        self.assertEqual(inv.lots("A"), [(date(2026, 1, 3), 1, Decimal("3"))])

    def test_sell_insufficient_eligible_stock_leaves_everything_unchanged(self) -> None:
        inv = Inventory()
        inv.buy("A", 2, "1.25", date(2026, 1, 1))
        inv.buy("A", 10, "3", date(2026, 1, 3))
        inv.buy("B", 1, "7", date(2026, 1, 1))
        before = inv.lots("A")
        value = inv.value()

        with self.assertRaises(ValueError):
            inv.sell("A", 3, date(2026, 1, 2))

        self.assertEqual(inv.lots("A"), before)
        self.assertEqual(inv.on_hand("A"), 12)
        self.assertEqual(inv.value(), value)
        self.assertEqual(inv.sell("A", 2, date(2026, 1, 1)), Decimal("2.50"))
        self.assertEqual(inv.lots("A"), [(date(2026, 1, 3), 10, Decimal("3"))])

    def test_lots_returns_detached_list_of_tuples(self) -> None:
        inv = Inventory()
        inv.buy("A", 2, "1.25", date(2026, 1, 1))
        lots = inv.lots("A")

        self.assertIsInstance(lots[0], tuple)
        lots.clear()

        self.assertEqual(inv.on_hand("A"), 2)
        self.assertEqual(inv.value("A"), Decimal("2.50"))

    def test_value_is_exact_and_includes_all_skus(self) -> None:
        inv = Inventory()
        inv.buy("A", 3, "1.23456789", date(2026, 1, 1))
        inv.buy("B", 1, 2, date(2026, 1, 1))

        with localcontext() as context:
            context.prec = 4
            self.assertEqual(inv.value("A"), Decimal("3.70370367"))
            self.assertEqual(inv.value(), Decimal("5.70370367"))
            self.assertEqual(inv.sell("A", 2, date(2026, 1, 1)), Decimal("2.47"))
            self.assertEqual(inv.value("A"), Decimal("1.23456789"))

    def test_sell_partial_lots_preserves_exact_remaining_value(self) -> None:
        inv = Inventory()
        inv.buy("A", 2, "1.125", date(2026, 1, 1))
        inv.buy("A", 3, "2.335", date(2026, 1, 2))
        initial_value = inv.value()

        self.assertEqual(inv.sell("A", 3, date(2026, 1, 2)), Decimal("4.59"))

        self.assertEqual(inv.lots("A"), [(date(2026, 1, 2), 2, Decimal("2.335"))])
        self.assertEqual(inv.value(), Decimal("4.670"))
        self.assertEqual(initial_value - inv.value(), Decimal("4.585"))

    def test_unknown_sku_returns_empty_stock_and_decimal_value(self) -> None:
        inv = Inventory()

        self.assertEqual(inv.on_hand("missing"), 0)
        self.assertEqual(inv.lots("missing"), [])
        self.assertEqual(inv.value(), Decimal(0))
        self.assertIsInstance(inv.value("missing"), Decimal)
        with self.assertRaises(ValueError):
            inv.sell("missing", 1, date(2026, 1, 1))

    def test_invalid_quantities_and_cost_leave_stock_unchanged(self) -> None:
        inv = Inventory()
        inv.buy("A", 1, Decimal("0"), date(2026, 1, 1))

        for qty in (0, -1):
            with self.subTest(qty=qty):
                with self.assertRaises(ValueError):
                    inv.buy("A", qty, "1", date(2026, 1, 1))
                with self.assertRaises(ValueError):
                    inv.sell("A", qty, date(2026, 1, 1))
        with self.assertRaises(ValueError):
            inv.buy("A", 1, "-0.01", date(2026, 1, 1))

        self.assertEqual(inv.on_hand("A"), 1)
        self.assertEqual(inv.sell("A", 1, date(2026, 1, 1)), Decimal("0.00"))
        self.assertEqual(inv.lots("A"), [])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)

    unittest.main()
