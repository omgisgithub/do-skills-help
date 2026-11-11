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


def test_cogs_rounded_once_half_up():
    inv = Inventory()
    inv.buy("A", 1, "2.345", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("2.35")


def test_cogs_summed_before_rounding():
    inv = Inventory()
    inv.buy("A", 1, "0.005", date(2026, 1, 1))
    inv.buy("A", 1, "0.005", date(2026, 1, 1))
    # exact sum 0.010 -> 0.01
    assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("0.01")


def test_oldest_lot_consumed_first_even_if_recorded_later():
    inv = Inventory()
    inv.buy("A", 5, "3.00", date(2026, 1, 2))
    inv.buy("A", 2, "1.00", date(2026, 1, 1))  # late invoice for an earlier date
    assert inv.sell("A", 2, date(2026, 1, 3)) == Decimal("2.00")
    assert inv.on_hand("A") == 5


def test_same_date_lots_in_recording_order():
    inv = Inventory()
    inv.buy("A", 1, "5.00", date(2026, 1, 1))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("5.00")


def test_future_lots_not_sold():
    inv = Inventory()
    inv.buy("A", 1, "1.00", date(2026, 2, 1))
    try:
        inv.sell("A", 1, date(2026, 1, 1))
    except ValueError:
        assert inv.on_hand("A") == 1
        return
    raise AssertionError("sold from future lot")


def test_insufficient_stock_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    try:
        inv.sell("A", 5, date(2026, 1, 1))
    except ValueError:
        assert inv.on_hand("A") == 4
        assert inv.lots("A") == [(date(2026, 1, 1), 2, Decimal("1.00")), (date(2026, 1, 1), 2, Decimal("1.00"))]
        return
    raise AssertionError("oversold")


def test_fully_used_lots_disappear():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 3, "1.00", date(2026, 1, 1))
    inv.sell("A", 2, date(2026, 1, 1))
    assert inv.lots("A") == [(date(2026, 1, 1), 3, Decimal("1.00"))]


def test_lots_returns_copy():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.lots("A").clear()
    inv.lots("A")[0] = None
    assert inv.on_hand("A") == 2


def test_value():
    inv = Inventory()
    assert inv.value() == Decimal("0")
    inv.buy("A", 3, "0.335", date(2026, 1, 1))
    inv.buy("B", 2, "1.10", date(2026, 1, 1))
    assert inv.value("A") == Decimal("1.005")
    assert inv.value() == Decimal("3.205")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
