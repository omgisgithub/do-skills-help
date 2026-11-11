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


def test_cogs_rounded_once():
    inv = Inventory()
    inv.buy("A", 1, "0.125", date(2026, 1, 1))
    inv.buy("A", 1, "0.125", date(2026, 1, 1))
    assert inv.sell("A", 2, date(2026, 1, 2)) == Decimal("0.25")


def test_oldest_lot_first_even_if_recorded_late():
    inv = Inventory()
    inv.buy("A", 1, "1", date(2026, 1, 5))
    inv.buy("A", 1, "5", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 6)) == Decimal("5.00")
    assert [lot[0] for lot in inv.lots("A")] == [date(2026, 1, 5)]


def test_failed_sell_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 3, "1", date(2026, 1, 1))
    inv.buy("A", 1, "1", date(2026, 2, 1))
    try:
        inv.sell("A", 5, date(2026, 1, 10))
    except ValueError:
        pass
    assert inv.on_hand("A") == 4


def test_used_up_lots_disappear_and_lots_is_a_copy():
    inv = Inventory()
    inv.buy("A", 2, "1", date(2026, 1, 1))
    inv.sell("A", 2, date(2026, 1, 2))
    assert inv.lots("A") == []
    inv.buy("A", 2, "1", date(2026, 1, 3))
    inv.lots("A")[0] = (date(2026, 1, 3), 99, Decimal("1"))
    assert inv.on_hand("A") == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
