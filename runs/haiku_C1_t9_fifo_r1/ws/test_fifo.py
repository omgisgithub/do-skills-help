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


def test_cogs_rounded_once_on_exact_sum():
    inv = Inventory()
    for _ in range(3):
        inv.buy("A", 1, "0.335", date(2026, 1, 1))
    assert inv.sell("A", 3, date(2026, 1, 2)) == Decimal("1.01")


def test_out_of_order_purchase_consumed_oldest_first():
    inv = Inventory()
    inv.buy("A", 1, "5.00", date(2026, 1, 1))
    inv.buy("A", 1, "1.00", date(2025, 12, 1))
    assert inv.sell("A", 1, date(2026, 1, 2)) == Decimal("1.00")
    assert [l[0] for l in inv.lots("A")] == [date(2026, 1, 1)]


def test_same_date_lots_keep_recording_order():
    inv = Inventory()
    inv.buy("A", 1, "2.00", date(2026, 1, 1))
    inv.buy("A", 1, "3.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("2.00")


def test_failed_sell_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 1, "1.00", date(2026, 2, 1))
    try:
        inv.sell("A", 5, date(2026, 3, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("oversell accepted")
    assert inv.on_hand("A") == 3


def test_future_lots_not_sellable():
    inv = Inventory()
    inv.buy("A", 1, "1.00", date(2026, 2, 1))
    try:
        inv.sell("A", 1, date(2026, 1, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("sold from a future lot")
    assert inv.on_hand("A") == 1


def test_fully_used_lot_disappears():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.sell("A", 2, date(2026, 1, 1))
    assert inv.lots("A") == []
    assert inv.on_hand("A") == 0


def test_lots_returns_copy():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.lots("A")[0] = (date(2026, 1, 1), 99, Decimal("1.00"))
    inv.lots("A").clear()
    assert inv.on_hand("A") == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
