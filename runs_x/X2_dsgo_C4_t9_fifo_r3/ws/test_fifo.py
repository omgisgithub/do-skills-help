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


def test_cogs_rounds_once_at_the_end():
    inv = Inventory()
    inv.buy("A", 1, "1.004", date(2026, 1, 1))
    inv.buy("A", 1, "1.004", date(2026, 1, 2))
    assert inv.sell("A", 2, date(2026, 1, 3)) == Decimal("2.01")
    assert inv.on_hand("A") == 0


def test_sell_consumes_oldest_date_first_regardless_of_recording_order():
    inv = Inventory()
    inv.buy("A", 5, "9.00", date(2026, 1, 5))
    inv.buy("A", 5, "1.00", date(2026, 1, 1))
    assert inv.sell("A", 3, date(2026, 1, 6)) == Decimal("3.00")
    assert inv.on_hand("A") == 7


def test_sell_without_enough_stock_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 2, "2.00", date(2026, 1, 2))
    before = inv.lots("A")
    try:
        inv.sell("A", 5, date(2026, 1, 3))
    except ValueError:
        pass
    else:
        raise AssertionError("sold more than on hand")
    assert inv.on_hand("A") == 4
    assert inv.lots("A") == before
    assert inv.value("A") == Decimal("6.00")


def test_sell_ignores_lots_dated_after_sale():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 10))
    try:
        inv.sell("A", 1, date(2026, 1, 5))
    except ValueError:
        pass
    else:
        raise AssertionError("sold a future lot")
    assert inv.on_hand("A") == 2


def test_lots_returns_copy_in_consumption_order():
    inv = Inventory()
    inv.buy("A", 1, "3.00", date(2026, 1, 3))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    inv.buy("A", 1, "2.00", date(2026, 1, 2))
    returned = inv.lots("A")
    returned.append((date(2026, 1, 4), 99, Decimal("1.00")))
    returned[0] = (date(2026, 1, 9), 99, Decimal("1.00"))
    assert inv.lots("A") == [
        (date(2026, 1, 1), 1, Decimal("1.00")),
        (date(2026, 1, 2), 1, Decimal("2.00")),
        (date(2026, 1, 3), 1, Decimal("3.00")),
    ]
    assert inv.on_hand("A") == 3


def test_fully_used_lot_disappears():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 2, "2.00", date(2026, 1, 2))
    inv.sell("A", 2, date(2026, 1, 3))
    assert inv.lots("A") == [(date(2026, 1, 2), 2, Decimal("2.00"))]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
