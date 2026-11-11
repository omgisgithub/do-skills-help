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


def test_sell_out_of_order_purchase_consumes_oldest_first():
    inv = Inventory()
    inv.buy("A", 1, "5.00", date(2026, 1, 10))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 10)) == Decimal("1.00")


def test_sell_same_date_lots_consumed_in_recorded_order():
    inv = Inventory()
    inv.buy("A", 1, "4.00", date(2026, 1, 1))
    inv.buy("A", 1, "9.00", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("4.00")


def test_sell_rounds_exact_sum_once_half_up():
    inv = Inventory()
    inv.buy("A", 1, "0.335", date(2026, 1, 1))
    inv.buy("A", 1, "0.335", date(2026, 1, 1))
    inv.buy("A", 1, "0.335", date(2026, 1, 1))
    assert inv.sell("A", 3, date(2026, 1, 2)) == Decimal("1.01")


def test_sell_half_cent_rounds_up_not_float_truncation():
    inv = Inventory()
    inv.buy("A", 1, "2.335", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 2)) == Decimal("2.34")


def test_sell_insufficient_stock_leaves_inventory_unchanged():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    try:
        inv.sell("A", 5, date(2026, 1, 2))
    except ValueError:
        pass
    else:
        raise AssertionError("oversell accepted")
    assert inv.on_hand("A") == 2
    assert inv.lots("A") == [(date(2026, 1, 1), 2, Decimal("1.00"))]


def test_sell_ignores_lots_dated_after_sale():
    inv = Inventory()
    inv.buy("A", 3, "1.00", date(2026, 2, 1))
    try:
        inv.sell("A", 1, date(2026, 1, 31))
    except ValueError:
        pass
    else:
        raise AssertionError("sold from a lot dated after the sale")
    assert inv.on_hand("A") == 3


def test_sell_fully_used_lot_disappears():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 5, "3.00", date(2026, 1, 2))
    inv.sell("A", 2, date(2026, 1, 3))
    assert inv.lots("A") == [(date(2026, 1, 2), 5, Decimal("3.00"))]


def test_lots_returned_list_mutation_does_not_change_inventory():
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    returned = inv.lots("A")
    returned.clear()
    assert inv.on_hand("A") == 2
    assert inv.lots("A") == [(date(2026, 1, 1), 2, Decimal("1.00"))]


def test_lots_returns_consumption_order():
    inv = Inventory()
    inv.buy("A", 1, "5.00", date(2026, 1, 10))
    inv.buy("A", 1, "1.00", date(2026, 1, 1))
    assert [when for when, _, _ in inv.lots("A")] == [date(2026, 1, 1), date(2026, 1, 10)]


def test_value_empty_inventory_is_decimal_zero():
    assert Inventory().value() == Decimal("0")
    assert isinstance(Inventory().value(), Decimal)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
