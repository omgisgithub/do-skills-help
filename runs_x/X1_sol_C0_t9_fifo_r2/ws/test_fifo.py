from datetime import date
from decimal import Decimal, localcontext
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


def test_round_once_half_up():
    inv = Inventory()
    inv.buy("A", 1, "1.005", date(2026, 1, 1))
    inv.buy("A", 1, "1.005", date(2026, 1, 1))
    assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("2.01")
    inv.buy("A", 1, "2.345", date(2026, 1, 1))
    result = inv.sell("A", 1, date(2026, 1, 1))
    assert result == Decimal("2.35")
    assert result.as_tuple().exponent == -2
    assert inv.lots("A") == []


def test_out_of_order_and_same_date_fifo():
    inv = Inventory()
    inv.buy("A", 1, "30", date(2026, 1, 3))
    inv.buy("A", 1, "10", date(2026, 1, 1))
    inv.buy("A", 1, "11", date(2026, 1, 1))
    assert [lot[2] for lot in inv.lots("A")] == [
        Decimal("10"), Decimal("11"), Decimal("30")
    ]
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("10.00")
    assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("11.00")
    assert inv.on_hand("A") == 1


def test_insufficient_eligible_stock_is_atomic():
    inv = Inventory()
    inv.buy("A", 2, "2.335", date(2026, 1, 1))
    inv.buy("A", 5, "3", date(2026, 2, 1))
    inv.buy("B", 3, "4", date(2026, 1, 1))
    before = (inv.lots("A"), inv.lots("B"), inv.value())
    for sku, qty in [("A", 3), ("A", 10), ("unknown", 1)]:
        try:
            inv.sell(sku, qty, date(2026, 1, 1))
        except ValueError:
            pass
        else:
            raise AssertionError("insufficient stock accepted")
        assert (inv.lots("A"), inv.lots("B"), inv.value()) == before
    assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("4.67")
    assert inv.lots("A") == [(date(2026, 2, 1), 5, Decimal("3"))]


def test_lots_are_detached_tuples():
    inv = Inventory()
    inv.buy("A", 2, 3, date(2026, 1, 1))
    snapshot = inv.lots("A")
    assert isinstance(snapshot[0], tuple)
    snapshot.clear()
    assert inv.on_hand("A") == 2
    snapshot = inv.lots("A")
    inv.sell("A", 1, date(2026, 1, 1))
    assert snapshot == [(date(2026, 1, 1), 2, Decimal("3"))]
    assert inv.lots("unknown") == []
    assert inv.on_hand("unknown") == 0
    assert inv.value("unknown") == 0


def test_exact_values_and_large_cogs_under_small_context():
    inv = Inventory()
    with localcontext() as context:
        context.prec = 6
        inv.buy("A", 2, "1234567890123456789012345678.005", date(2026, 1, 1))
        inv.buy("B", 1, "0.0001", date(2026, 1, 1))
        assert inv.value("A") == Decimal("2469135780246913578024691356.010")
        assert inv.value() == Decimal("2469135780246913578024691356.0101")
        assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal(
            "1234567890123456789012345678.01"
        )
        assert inv.value("A") == Decimal("1234567890123456789012345678.005")


def test_invalid_purchases_and_quantities_leave_stock_unchanged():
    inv = Inventory()
    for qty, cost, error in [
        (0, "1", ValueError), (-1, "1", ValueError),
        (1, "-1", ValueError), (1.5, "1", TypeError),
        (1, 1.5, TypeError),
    ]:
        try:
            inv.buy("A", qty, cost, date(2026, 1, 1))
        except error:
            pass
        else:
            raise AssertionError("invalid purchase accepted")
        assert inv.lots("A") == []
    for qty, error in [(0, ValueError), (-1, ValueError), (1.5, TypeError)]:
        try:
            inv.sell("A", qty, date(2026, 1, 1))
        except error:
            pass
        else:
            raise AssertionError("invalid sale accepted")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
