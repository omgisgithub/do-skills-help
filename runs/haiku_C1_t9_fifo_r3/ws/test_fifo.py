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


def test_cogs_exact_sum_rounded_once_half_up():
    inv = Inventory()
    inv.buy("A", 1, "2.335", date(2026, 1, 1))
    inv.buy("A", 1, "2.335", date(2026, 1, 1))
    assert inv.sell("A", 2, date(2026, 1, 2)) == Decimal("4.67")
    inv.buy("B", 3, "0.005", date(2026, 1, 1))
    assert inv.sell("B", 1, date(2026, 1, 2)) == Decimal("0.01")


def test_fifo_by_date_not_insertion_order():
    inv = Inventory()
    inv.buy("A", 2, "5.00", date(2026, 1, 10))
    inv.buy("A", 2, "1.00", date(2026, 1, 1))  # late invoice for an earlier date
    assert inv.sell("A", 2, date(2026, 1, 20)) == Decimal("2.00")
    assert inv.lots("A") == [(date(2026, 1, 10), 2, Decimal("5.00"))]


def test_future_lots_not_sold():
    inv = Inventory()
    inv.buy("A", 5, "1.00", date(2026, 2, 1))
    try:
        inv.sell("A", 1, date(2026, 1, 15))
    except ValueError:
        pass
    else:
        raise AssertionError("sold from future lot")
    assert inv.on_hand("A") == 5


def test_failed_sell_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 2, "3.00", date(2026, 1, 1))
    try:
        inv.sell("A", 5, date(2026, 1, 2))
    except ValueError:
        pass
    else:
        raise AssertionError("oversold")
    assert inv.lots("A") == [(date(2026, 1, 1), 2, Decimal("1.00")), (date(2026, 1, 1), 2, Decimal("3.00"))]


def test_fully_used_lot_disappears():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 3, "2.00", date(2026, 1, 2))
    inv.sell("A", 2, date(2026, 1, 3))
    assert inv.lots("A") == [(date(2026, 1, 2), 3, Decimal("2.00"))]


def test_lots_is_a_copy():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.lots("A").clear()
    inv.lots("A")[0] = None
    assert inv.on_hand("A") == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
