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
    inv.buy("A", 1, "2.005", date(2026, 1, 1))
    inv.buy("A", 1, "2.005", date(2026, 1, 2))
    assert inv.sell("A", 2, date(2026, 1, 3)) == Decimal("4.01")


def test_out_of_order_purchases_consumed_oldest_first():
    inv = Inventory()
    inv.buy("A", 1, "9.00", date(2026, 1, 5))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    assert inv.lots("A") == [
        (date(2026, 1, 1), 1, Decimal("1.00")),
        (date(2026, 1, 5), 1, Decimal("9.00")),
    ]
    assert inv.sell("A", 1, date(2026, 1, 6)) == Decimal("1.00")


def test_insufficient_stock_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    before = inv.lots("A")
    try:
        inv.sell("A", 3, date(2026, 1, 5))
    except ValueError:
        pass
    else:
        raise AssertionError("oversell accepted")
    assert inv.lots("A") == before
    assert inv.on_hand("A") == 2


def test_lots_returns_defensive_copy():
    inv = Inventory()
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    result = inv.lots("A")
    result.append((date(2026, 1, 2), 5, Decimal("2.00")))
    result[0] = (date(2026, 1, 3), 9, Decimal("3.00"))
    assert inv.lots("A") == [(date(2026, 1, 1), 1, Decimal("1.00"))]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
