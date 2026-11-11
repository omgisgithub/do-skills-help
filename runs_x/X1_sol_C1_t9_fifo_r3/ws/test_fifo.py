from datetime import date
from decimal import Decimal, localcontext
from unittest import TestCase
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


def test_round_once_half_up():
    inv = Inventory()
    inv.buy("A", 1, "2.345", date(2026, 1, 1))
    result = inv.sell("A", 1, date(2026, 1, 1))
    assert result == Decimal("2.35")
    assert result.as_tuple().exponent == -2
    inv.buy("A", 1, "2.335", date(2026, 1, 1))
    inv.buy("A", 1, Decimal("2.335"), date(2026, 1, 1))
    assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("4.67")
    assert inv.lots("A") == []


def test_fifo_dates_and_stable_ties():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 1, 3)
    inv.buy("A", 1, "9", late)
    inv.buy("A", 1, "2", early)
    inv.buy("A", 1, "3", early)
    assert inv.lots("A") == [
        (early, 1, Decimal("2")),
        (early, 1, Decimal("3")),
        (late, 1, Decimal("9")),
    ]
    assert inv.sell("A", 1, early) == Decimal("2.00")
    assert inv.sell("A", 1, early) == Decimal("3.00")
    assert inv.lots("A") == [(late, 1, Decimal("9"))]


def test_shortage_is_atomic_and_future_stock_ineligible():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 2, 1)
    inv.buy("A", 2, "2.335", early)
    inv.buy("A", 10, "9", late)
    inv.buy("B", 1, 4, early)
    before = (inv.lots("A"), inv.lots("B"), inv.value())
    with TestCase().assertRaises(ValueError):
        inv.sell("A", 3, early)
    assert (inv.lots("A"), inv.lots("B"), inv.value()) == before
    assert inv.on_hand("A") == 12
    assert inv.sell("A", 2, early) == Decimal("4.67")
    with TestCase().assertRaises(ValueError):
        inv.sell("missing", 1, late)
    assert inv.on_hand("missing") == 0
    assert inv.lots("missing") == []


def test_lots_are_independent_tuples():
    inv = Inventory()
    when = date(2026, 1, 1)
    inv.buy("A", 2, "1.234", when)
    lots = inv.lots("A")
    assert isinstance(lots[0], tuple)
    with TestCase().assertRaises(TypeError):
        lots[0][1] = 99
    lots.clear()
    assert inv.lots("A") == [(when, 2, Decimal("1.234"))]


def test_validation_leaves_stock_unchanged():
    inv = Inventory()
    when = date(2026, 1, 1)
    for qty in (0, -1):
        with TestCase().assertRaises(ValueError):
            inv.buy("A", qty, "1", when)
        with TestCase().assertRaises(ValueError):
            inv.sell("A", qty, when)
    for qty in (1.5, Decimal("1"), "1", True):
        with TestCase().assertRaises(TypeError):
            inv.buy("A", qty, "1", when)
        with TestCase().assertRaises(TypeError):
            inv.sell("A", qty, when)
    with TestCase().assertRaises(ValueError):
        inv.buy("A", 1, "-0.01", when)
    with TestCase().assertRaises(TypeError):
        inv.buy("A", 1, 1.5, when)
    assert inv.lots("A") == []
    inv.buy("A", 1, 0, when)
    assert inv.sell("A", 1, when) == Decimal("0.00")


def test_exact_remaining_value_and_decimal_context():
    inv = Inventory()
    when = date(2026, 1, 1)
    assert inv.value() == Decimal(0)
    assert isinstance(inv.value("missing"), Decimal)
    inv.buy("A", 3, "2.335", when)
    inv.buy("B", 2, 4, when)
    assert inv.value("A") == Decimal("7.005")
    assert inv.value() == Decimal("15.005")
    assert inv.sell("A", 1, when) == Decimal("2.34")
    assert inv.value("A") == Decimal("4.670")
    assert inv.value() == Decimal("12.670")
    inv.buy("C", 1, "123456789012345678901234567890.005", when)
    with localcontext() as context:
        context.prec = 6
        assert inv.value("C") == Decimal("123456789012345678901234567890.005")
        assert inv.sell("C", 1, when) == Decimal("123456789012345678901234567890.01")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
