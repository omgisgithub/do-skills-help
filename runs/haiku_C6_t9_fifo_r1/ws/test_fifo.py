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
    assert inv.sell("A", 1, date(2026, 1, 2)) == Decimal("2.35")


def test_cogs_exact_sum_not_per_lot_rounding():
    inv = Inventory()
    inv.buy("A", 3, "0.10", date(2026, 1, 1))
    inv.buy("A", 3, "0.10", date(2026, 1, 1))
    assert inv.sell("A", 6, date(2026, 1, 2)) == Decimal("0.60")


def test_oldest_date_consumed_first_even_if_bought_later():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 5))
    inv.buy("A", 2, "9.00", date(2026, 1, 1))
    assert inv.sell("A", 2, date(2026, 1, 5)) == Decimal("18.00")


def test_same_date_lots_consumed_in_recorded_order():
    inv = Inventory()
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    inv.buy("A", 1, "5.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("1.00")


def test_sell_only_from_lots_dated_on_or_before():
    inv = Inventory()
    inv.buy("A", 1, "1.00", date(2026, 1, 10))
    try:
        inv.sell("A", 1, date(2026, 1, 9))
    except ValueError:
        pass
    else:
        raise AssertionError("sold from a future lot")
    assert inv.on_hand("A") == 1


def test_failed_sell_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    try:
        inv.sell("A", 5, date(2026, 1, 2))
    except ValueError:
        pass
    else:
        raise AssertionError("oversold")
    assert inv.lots("A") == [(date(2026, 1, 1), 2, Decimal("1.00"))]


def test_fully_used_lots_disappear():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 2, "2.00", date(2026, 1, 2))
    inv.sell("A", 2, date(2026, 1, 3))
    assert inv.lots("A") == [(date(2026, 1, 2), 2, Decimal("2.00"))]


def test_lots_returns_copy():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.lots("A").clear()
    assert inv.on_hand("A") == 2


def test_string_cost_must_be_valid():
    inv = Inventory()
    for bad in ["abc", "NaN", "Infinity"]:
        try:
            inv.buy("A", 1, bad, date(2026, 1, 1))
        except ValueError:
            continue
        raise AssertionError("accepted " + bad)


def test_bad_qty_types_rejected():
    inv = Inventory()
    for bad in [1.0, True, "1"]:
        try:
            inv.buy("A", bad, "1.00", date(2026, 1, 1))
        except TypeError:
            continue
        raise AssertionError("buy accepted qty " + repr(bad))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
