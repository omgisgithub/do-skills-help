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


def test_rounds_once_and_sells_fifo_by_date():
    inv = Inventory()
    inv.buy("A", 1, "2.335", date(2026, 1, 2))
    inv.buy("A", 1, "1.005", date(2026, 1, 1))
    assert inv.sell("A", 2, date(2026, 1, 3)) == Decimal("3.34")
    assert inv.on_hand("A") == 0


def test_failed_sale_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 3, "2.00", date(2026, 1, 3))
    before = inv.lots("A")
    try:
        inv.sell("A", 3, date(2026, 1, 2))
    except ValueError:
        pass
    else:
        raise AssertionError("sale without enough eligible stock succeeded")
    assert inv.lots("A") == before


def test_lots_returns_a_copy():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    returned = inv.lots("A")
    returned.clear()
    assert inv.on_hand("A") == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
