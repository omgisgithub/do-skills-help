from datetime import date
from decimal import Decimal
from fifo import Inventory


def test_simple_sale() -> None:
    inv = Inventory()
    inv.buy("A", 10, "2.00", date(2026, 1, 1))
    assert inv.sell("A", 4, date(2026, 1, 5)) == Decimal("8.00")
    assert inv.on_hand("A") == 6


def test_two_lots() -> None:
    inv = Inventory()
    inv.buy("A", 2, "1.00", date(2026, 1, 1))
    inv.buy("A", 5, "3.00", date(2026, 1, 2))
    assert inv.sell("A", 3, date(2026, 1, 3)) == Decimal("5.00")
    assert inv.on_hand("A") == 4


def test_float_rejected() -> None:
    inv = Inventory()
    try:
        inv.buy("A", 1, 1.5, date(2026, 1, 1))
    except TypeError:
        return
    raise AssertionError("float accepted")


def test_sale_rounds_combined_cost_once() -> None:
    inv = Inventory()
    inv.buy("A", 1, "1.004", date(2026, 1, 1))
    inv.buy("A", 1, "1.004", date(2026, 1, 2))

    assert inv.sell("A", 2, date(2026, 1, 2)) == Decimal("2.01")
    assert inv.lots("A") == []


def test_sale_rounds_half_up() -> None:
    inv = Inventory()
    inv.buy("A", 1, "2.345", date(2026, 1, 1))

    result = inv.sell("A", 1, date(2026, 1, 1))

    assert result == Decimal("2.35")
    assert result.as_tuple().exponent == -2


def test_sale_preserves_decimal_precision() -> None:
    inv = Inventory()
    inv.buy("A", 1, "9007199254740992.01", date(2026, 1, 1))

    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("9007199254740992.01")


def test_late_invoices_preserve_fifo_and_same_date_order() -> None:
    inv = Inventory()
    inv.buy("A", 1, "3", date(2026, 1, 3))
    inv.buy("A", 1, "1", date(2026, 1, 1))
    inv.buy("A", 1, "2", date(2026, 1, 1))

    assert inv.lots("A") == [
        (date(2026, 1, 1), 1, Decimal("1")),
        (date(2026, 1, 1), 1, Decimal("2")),
        (date(2026, 1, 3), 1, Decimal("3")),
    ]
    assert inv.sell("A", 1, date(2026, 1, 3)) == Decimal("1.00")
    assert inv.sell("A", 1, date(2026, 1, 3)) == Decimal("2.00")


def test_insufficient_eligible_stock_leaves_inventory_unchanged() -> None:
    inv = Inventory()
    inv.buy("A", 2, "1.234", date(2026, 1, 1))
    inv.buy("A", 5, "3", date(2026, 1, 3))
    inv.buy("B", 1, "4", date(2026, 1, 1))
    before = list(inv.lots("A"))
    before_value = inv.value()

    try:
        inv.sell("A", 3, date(2026, 1, 2))
    except ValueError:
        pass
    else:
        raise AssertionError("sale accepted without eligible stock")

    assert inv.lots("A") == before
    assert inv.on_hand("A") == 7
    assert inv.value() == before_value
    assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("2.47")
    assert inv.lots("A") == [(date(2026, 1, 3), 5, Decimal("3"))]


def test_lots_returns_detached_list_of_tuples() -> None:
    inv = Inventory()
    inv.buy("A", 2, "1.234", date(2026, 1, 1))
    lots = inv.lots("A")

    assert isinstance(lots[0], tuple)
    lots[0] = (date(2020, 1, 1), 100, Decimal("0"))
    lots.clear()

    assert inv.lots("A") == [(date(2026, 1, 1), 2, Decimal("1.234"))]
    assert inv.value("A") == Decimal("2.468")


def test_value_is_exact_across_skus_and_partial_sales() -> None:
    inv = Inventory()
    inv.buy("A", 3, Decimal("1.234"), date(2026, 1, 1))
    inv.buy("B", 2, 4, date(2026, 1, 1))

    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("1.23")
    assert inv.value("A") == Decimal("2.468")
    assert inv.value() == Decimal("10.468")
    assert inv.on_hand("B") == 2


def test_unknown_sku_has_no_stock_or_value() -> None:
    inv = Inventory()

    assert inv.on_hand("missing") == 0
    assert inv.lots("missing") == []
    assert inv.value("missing") == Decimal("0")
    assert isinstance(inv.value(), Decimal)
    try:
        inv.sell("missing", 1, date(2026, 1, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("unknown SKU sale accepted")


def test_fractional_quantity_is_rejected_without_changing_stock() -> None:
    inv = Inventory()
    inv.buy("A", 2, "1", date(2026, 1, 1))

    try:
        inv.buy("A", 1.5, "1", date(2026, 1, 1))
    except TypeError:
        pass
    else:
        raise AssertionError("fractional purchase quantity accepted")
    try:
        inv.sell("A", 1.5, date(2026, 1, 1))
    except TypeError:
        pass
    else:
        raise AssertionError("fractional sale quantity accepted")

    assert inv.lots("A") == [(date(2026, 1, 1), 2, Decimal("1"))]


def test_invalid_purchases_and_sales_leave_inventory_unchanged() -> None:
    inv = Inventory()
    inv.buy("A", 2, "0", date(2026, 1, 1))

    for qty in (0, -1):
        for operation in (inv.buy, inv.sell):
            try:
                if operation == inv.buy:
                    inv.buy("A", qty, "1", date(2026, 1, 1))
                else:
                    inv.sell("A", qty, date(2026, 1, 1))
            except ValueError:
                pass
            else:
                raise AssertionError("nonpositive quantity accepted")
    try:
        inv.buy("A", 1, "-0.01", date(2026, 1, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("negative cost accepted")

    assert inv.on_hand("A") == 2
    assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("0.00")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
