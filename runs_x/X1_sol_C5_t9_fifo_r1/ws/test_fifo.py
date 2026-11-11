from datetime import date
from decimal import Decimal, Inexact, Rounded, localcontext
import unittest
from fifo import Inventory


def test_simple_sale():
    inv = Inventory()
    inv.buy("A", 10, "2.00", date(2026, 1, 1))
    assert inv.sell("A", 4, date(2026, 1, 5)) == Decimal("8.00")
    assert inv.on_hand("A") == 6


def test_two_lots():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 5, "3.00", date(2026, 1, 2))
    assert inv.sell("A", 3, date(2026, 1, 3)) == Decimal("5.00")
    assert inv.on_hand("A") == 4


def test_float_rejected():
    inv = Inventory()
    try:
        inv.buy("A", 1, 1.5, date(2026, 1, 1))
    except TypeError:
        return
    raise AssertionError("float accepted")


def test_round_only_after_adding_lots():
    inv = Inventory()
    inv.buy("A", 1, "0.004", date(2026, 1, 1))
    inv.buy("A", 1, "0.004", date(2026, 1, 1))
    assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("0.01")


def test_half_up_rounding():
    inv = Inventory()
    inv.buy("A", 1, "2.345", date(2026, 1, 1))
    result = inv.sell("A", 1, date(2026, 1, 1))
    assert result == Decimal("2.35")
    assert result.as_tuple().exponent == -2


def test_fifo_uses_dates_and_stable_ties():
    inv = Inventory()
    inv.buy("A", 1, "9", date(2026, 1, 3))
    inv.buy("A", 1, "2", date(2026, 1, 1))
    inv.buy("A", 1, "4", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 3)) == Decimal("2.00")
    assert inv.sell("A", 1, date(2026, 1, 3)) == Decimal("4.00")


def test_failed_sale_is_atomic():
    inv = Inventory()
    inv.buy("A", 2, "2.335", date(2026, 1, 1))
    inv.buy("A", 10, "3", date(2026, 2, 1))
    before = [(date(2026, 1, 1), 2, Decimal("2.335")),
              (date(2026, 2, 1), 10, Decimal("3"))]
    with unittest.TestCase().assertRaises(ValueError):
        inv.sell("A", 3, date(2026, 1, 31))
    assert inv.on_hand("A") == 12
    assert inv.value("A") == Decimal("34.670")
    assert inv.lots("A") == before


def test_sale_date_is_inclusive_and_future_stock_is_preserved():
    inv = Inventory()
    inv.buy("A", 2, "3", date(2026, 2, 1))
    inv.buy("A", 1, "2", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("2.00")
    assert inv.lots("A") == [(date(2026, 2, 1), 2, Decimal("3"))]


def test_consumed_lots_disappear():
    inv = Inventory()
    inv.buy("A", 1, 0, date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("0.00")
    assert inv.lots("A") == []


def test_lots_returns_independent_list_of_tuples_in_fifo_order():
    inv = Inventory()
    inv.buy("A", 1, "9", date(2026, 1, 3))
    inv.buy("A", 2, "2.335", date(2026, 1, 1))
    lots = inv.lots("A")
    assert lots == [(date(2026, 1, 1), 2, Decimal("2.335")),
                    (date(2026, 1, 3), 1, Decimal("9"))]
    assert all(isinstance(lot, tuple) for lot in lots)
    lots.clear()
    assert inv.on_hand("A") == 3
    assert inv.value("A") == Decimal("13.670")


def test_decimal_arithmetic_is_exact_even_with_low_context_precision():
    inv = Inventory()
    inv.buy("A", 3, "1234567890123456789012345678.005", date(2026, 1, 1))
    inv.buy("B", 1, "0.001", date(2026, 1, 1))
    with localcontext() as context:
        context.prec = 6
        assert inv.value("A") == Decimal("3703703670370370367037037034.015")
        assert inv.value() == Decimal("3703703670370370367037037034.016")
        assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("2469135780246913578024691356.01")
        assert inv.value("A") == Decimal("1234567890123456789012345678.005")
        assert context.prec == 6


def test_invalid_quantities_leave_stock_unchanged():
    for qty in (0, -1, 1.5, Decimal("1.5"), "1", None):
        inv = Inventory()
        inv.buy("A", 2, "1", date(2026, 1, 1))
        error = ValueError if isinstance(qty, int) else TypeError
        with unittest.TestCase().assertRaises(error):
            inv.buy("A", qty, "1", date(2026, 1, 1))
        with unittest.TestCase().assertRaises(error):
            inv.sell("A", qty, date(2026, 1, 1))
        assert inv.on_hand("A") == 2


def test_money_operations_are_independent_of_caller_decimal_limits_and_traps():
    inv = Inventory()
    inv.buy("A", 2, "12.345", date(2026, 1, 1))
    with localcontext() as context:
        context.Emax = 0
        assert inv.value() == Decimal("24.690")
        assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("12.35")
    with localcontext() as context:
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("12.35")
        assert context.traps[Inexact]
        assert context.traps[Rounded]


def test_negative_cost_leaves_inventory_unchanged():
    inv = Inventory()
    with unittest.TestCase().assertRaises(ValueError):
        inv.buy("A", 1, "-0.001", date(2026, 1, 1))
    assert inv.on_hand("A") == 0
    assert inv.lots("A") == []


def test_unknown_sku_and_values_across_sales():
    inv = Inventory()
    assert inv.on_hand("missing") == 0
    assert inv.lots("missing") == []
    assert inv.value("missing") == 0
    with unittest.TestCase().assertRaises(ValueError):
        inv.sell("missing", 1, date(2026, 1, 1))
    inv.buy("A", 3, Decimal("2.335"), date(2026, 1, 1))
    inv.buy("B", 2, 4, date(2026, 1, 1))
    assert inv.value() == Decimal("15.005")
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("2.34")
    assert inv.value("A") == Decimal("4.670")
    assert inv.value() == Decimal("12.670")
    assert inv.on_hand("B") == 2


if __name__ == "__main__":
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn)
                               for name, fn in sorted(globals().items())
                               if name.startswith("test_"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
