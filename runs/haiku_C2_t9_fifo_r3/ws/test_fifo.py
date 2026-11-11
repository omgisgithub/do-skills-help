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
    inv.buy("A", 1, "0.125", date(2026, 1, 1))
    inv.buy("A", 1, "0.125", date(2026, 1, 2))
    assert inv.sell("A", 2, date(2026, 1, 3)) == Decimal("0.25")
    inv.buy("B", 1, "2.345", date(2026, 1, 1))
    assert inv.sell("B", 1, date(2026, 1, 3)) == Decimal("2.35")


def test_out_of_order_purchase_sold_oldest_first():
    inv = Inventory()
    inv.buy("A", 1, "5.00", date(2026, 1, 10))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 20)) == Decimal("1.00")
    assert inv.lots("A") == [(date(2026, 1, 10), 1, Decimal("5.00"))]


def test_same_date_lots_keep_recorded_order():
    inv = Inventory()
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    inv.buy("A", 1, "2.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("1.00")


def test_future_lots_not_sold_and_failed_sale_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 3, "1.00", date(2026, 1, 1))
    inv.buy("A", 5, "1.00", date(2026, 2, 1))
    try:
        inv.sell("A", 4, date(2026, 1, 15))
    except ValueError:
        pass
    else:
        raise AssertionError("sold future stock")
    assert inv.on_hand("A") == 8
    assert inv.lots("A")[0][1] == 3


def test_used_up_lots_disappear_and_lots_is_a_copy():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.sell("A", 2, date(2026, 1, 2))
    assert inv.lots("A") == []
    inv.buy("A", 1, "1.00", date(2026, 1, 3))
    inv.lots("A").clear()
    assert inv.on_hand("A") == 1


def test_value_is_decimal_for_unknown_sku():
    assert Inventory().value("NOPE") == Decimal("0")
    assert isinstance(Inventory().value(), Decimal)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
