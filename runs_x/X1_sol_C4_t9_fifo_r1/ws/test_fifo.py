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


def test_sell_rounds_once_half_up() -> None:
    inv = Inventory()
    inv.buy("A", 1, "1.005", date(2026, 1, 1))
    inv.buy("A", 1, "1.005", date(2026, 1, 2))
    inv.buy("B", 1, "2.345", date(2026, 1, 1))

    assert inv.sell("A", 2, date(2026, 1, 2)) == Decimal("2.01")
    assert inv.sell("B", 1, date(2026, 1, 1)) == Decimal("2.35")


def test_lots_follow_date_and_recording_order() -> None:
    inv = Inventory()
    inv.buy("A", 1, "3", date(2026, 1, 3))
    inv.buy("A", 1, "1", date(2026, 1, 1))
    inv.buy("A", 1, "2", date(2026, 1, 1))

    assert inv.lots("A") == [
        (date(2026, 1, 1), 1, Decimal("1")),
        (date(2026, 1, 1), 1, Decimal("2")),
        (date(2026, 1, 3), 1, Decimal("3")),
    ]
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("1.00")
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("2.00")


def test_sell_insufficient_eligible_stock_changes_nothing() -> None:
    inv = Inventory()
    inv.buy("A", 2, "1.235", date(2026, 1, 1))
    inv.buy("A", 10, "3", date(2026, 1, 3))
    before = inv.lots("A")
    value = inv.value()

    with TestCase().assertRaises(ValueError):
        inv.sell("A", 3, date(2026, 1, 2))

    assert inv.lots("A") == before
    assert inv.on_hand("A") == 12
    assert inv.value() == value
    assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("2.47")
    assert inv.lots("A") == [(date(2026, 1, 3), 10, Decimal("3"))]


def test_lots_snapshot_cannot_change_inventory() -> None:
    inv = Inventory()
    inv.buy("A", 2, 3, date(2026, 1, 1))
    snapshot = inv.lots("A")

    assert isinstance(snapshot[0], tuple)
    snapshot[0] = (date(2026, 1, 1), 100, Decimal("0"))
    snapshot.clear()

    assert inv.on_hand("A") == 2
    assert inv.value("A") == Decimal("6")


def test_sell_exhausted_lots_disappear() -> None:
    inv = Inventory()
    inv.buy("A", 2, "1.2345", date(2026, 1, 1))

    inv.sell("A", 2, date(2026, 1, 1))

    assert inv.lots("A") == []
    assert inv.on_hand("A") == 0
    assert inv.value("A") == Decimal(0)
    assert isinstance(inv.value("A"), Decimal)


def test_value_preserves_exact_cost_across_skus_and_partial_sales() -> None:
    inv = Inventory()
    inv.buy("A", 3, "1.2345", date(2026, 1, 1))
    inv.buy("B", 2, Decimal("2.335"), date(2026, 1, 1))

    inv.sell("A", 1, date(2026, 1, 1))

    assert inv.value("A") == Decimal("2.4690")
    assert inv.value() == Decimal("7.1390")


def test_unknown_sku_is_empty_and_sale_fails() -> None:
    inv = Inventory()

    with TestCase().assertRaises(ValueError):
        inv.sell("missing", 1, date(2026, 1, 1))

    assert inv.lots("missing") == []
    assert inv.on_hand("missing") == 0
    assert inv.value("missing") == Decimal(0)
    assert isinstance(inv.value(), Decimal)


def test_invalid_inputs_leave_inventory_unchanged() -> None:
    inv = Inventory()

    for qty in (0, -1):
        with TestCase().assertRaises(ValueError):
            inv.buy("A", qty, "1", date(2026, 1, 1))
        with TestCase().assertRaises(ValueError):
            inv.sell("A", qty, date(2026, 1, 1))
    for qty in (1.5, "1", True):
        with TestCase().assertRaises(TypeError):
            inv.buy("A", qty, "1", date(2026, 1, 1))
        with TestCase().assertRaises(TypeError):
            inv.sell("A", qty, date(2026, 1, 1))
    for cost in ("-1", "NaN", "Infinity", "-Infinity"):
        with TestCase().assertRaises(ValueError):
            inv.buy("A", 1, cost, date(2026, 1, 1))

    assert inv.lots("A") == []


def test_costs_remain_exact_beyond_decimal_context_precision() -> None:
    inv = Inventory()
    inv.buy("A", 2, "123456789012345678901234567890.005", date(2026, 1, 1))

    with localcontext() as context:
        context.prec = 6
        assert inv.value() == Decimal("246913578024691357802469135780.010")
        cogs = inv.sell("A", 1, date(2026, 1, 1))

    assert cogs == Decimal("123456789012345678901234567890.01")
    assert cogs.as_tuple().exponent == -2
    assert inv.value() == Decimal("123456789012345678901234567890.005")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
