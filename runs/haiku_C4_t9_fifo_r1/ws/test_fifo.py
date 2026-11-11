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
    inv.buy("A", 1, "1.173", date(2026, 1, 1))
    inv.buy("A", 1, "1.172", date(2026, 1, 1))
    assert inv.sell("A", 2, date(2026, 1, 2)) == Decimal("2.35")


def test_sell_consumes_oldest_date_first_despite_recording_order():
    inv = Inventory()
    inv.buy("A", 1, "5.00", date(2026, 1, 10))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 10)) == Decimal("1.00")


def test_sell_insufficient_stock_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    try:
        inv.sell("A", 3, date(2026, 1, 2))
    except ValueError:
        pass
    assert inv.on_hand("A") == 2
    assert inv.lots("A") == [(date(2026, 1, 1), 2, Decimal("1.00"))]


def test_sell_ignores_lots_dated_after_sale():
    inv = Inventory()
    inv.buy("A", 1, "1.00", date(2026, 1, 5))
    try:
        inv.sell("A", 1, date(2026, 1, 4))
    except ValueError:
        return
    raise AssertionError("sold from a future lot")


def test_sell_fully_used_lot_disappears():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.sell("A", 2, date(2026, 1, 2))
    assert inv.lots("A") == []


def test_lots_returned_copy_does_not_change_inventory():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.lots("A").clear()
    assert inv.on_hand("A") == 2


def test_value_empty_inventory_is_decimal_zero():
    assert Inventory().value() == Decimal("0")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
