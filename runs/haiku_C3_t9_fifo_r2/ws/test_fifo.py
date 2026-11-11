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


def test_oldest_date_consumed_first():
    inv = Inventory()
    inv.buy("A", 1, "5.00", date(2026, 2, 1))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 3, 1)) == Decimal("1.00")


def test_rounds_once_at_end_half_up():
    inv = Inventory()
    for _ in range(3):
        inv.buy("A", 1, "0.125", date(2026, 1, 1))
    assert inv.sell("A", 3, date(2026, 1, 2)) == Decimal("0.38")


def test_half_up_example():
    inv = Inventory()
    inv.buy("A", 1, "2.345", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 2)) == Decimal("2.35")


def test_failed_sell_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 2, "3.00", date(2026, 1, 5))
    try:
        inv.sell("A", 5, date(2026, 1, 6))
    except ValueError:
        pass
    else:
        raise AssertionError("oversell accepted")
    assert inv.on_hand("A") == 4
    assert inv.lots("A") == [
        (date(2026, 1, 1), 2, Decimal("1.00")),
        (date(2026, 1, 5), 2, Decimal("3.00")),
    ]


def test_sell_ignores_lots_after_date():
    inv = Inventory()
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    inv.buy("A", 5, "9.00", date(2026, 2, 1))
    try:
        inv.sell("A", 2, date(2026, 1, 15))
    except ValueError:
        pass
    else:
        raise AssertionError("sold from a future lot")
    assert inv.on_hand("A") == 6


def test_fully_used_lot_disappears():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.sell("A", 2, date(2026, 1, 2))
    assert inv.lots("A") == []


def test_lots_returns_copy():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.lots("A").append((date(2026, 1, 9), 1, Decimal("1")))
    assert inv.on_hand("A") == 2
    assert len(inv.lots("A")) == 1


def test_value_exact():
    inv = Inventory()
    inv.buy("A", 3, "0.333", date(2026, 1, 1))
    inv.buy("B", 1, "1.5", date(2026, 1, 1))
    assert inv.value("A") == Decimal("0.999")
    assert inv.value() == Decimal("2.499")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
