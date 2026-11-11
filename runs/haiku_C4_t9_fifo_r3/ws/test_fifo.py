from datetime import date
from decimal import Decimal
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


def test_cogs_rounds_once_half_up():
    inv = Inventory()
    inv.buy("A", 1, "2.345", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("2.35")


def test_cogs_sums_lots_exactly_before_rounding():
    inv = Inventory()
    inv.buy("A", 1, "0.125", date(2026, 1, 1))
    inv.buy("A", 1, "0.125", date(2026, 1, 2))
    assert inv.sell("A", 2, date(2026, 1, 3)) == Decimal("0.25")


def test_sell_consumes_oldest_lot_first_when_bought_out_of_order():
    inv = Inventory()
    inv.buy("A", 1, "5.00", date(2026, 1, 5))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 9)) == Decimal("1.00")


def test_sell_not_enough_stock_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    try:
        inv.sell("A", 3, date(2026, 1, 2))
    except ValueError:
        pass
    else:
        raise AssertionError("oversell accepted")
    assert inv.on_hand("A") == 2
    assert inv.lots("A") == [(date(2026, 1, 1), 2, Decimal("1.00"))]


def test_sell_ignores_lots_dated_after_sale():
    inv = Inventory()
    inv.buy("A", 5, "1.00", date(2026, 1, 10))
    try:
        inv.sell("A", 1, date(2026, 1, 9))
    except ValueError:
        pass
    else:
        raise AssertionError("sold from a lot dated after the sale")


def test_sell_fully_used_lot_disappears():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.sell("A", 2, date(2026, 1, 2))
    assert inv.lots("A") == []


def test_lots_returns_copy_in_consumption_order():
    inv = Inventory()
    inv.buy("A", 1, "5.00", date(2026, 1, 5))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    listed = inv.lots("A")
    listed.clear()
    assert [when for when, _, _ in inv.lots("A")] == [date(2026, 1, 1), date(2026, 1, 5)]


def test_value_empty_returns_decimal_zero():
    assert Inventory().value() == Decimal("0")
    assert isinstance(Inventory().value("X"), Decimal)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
