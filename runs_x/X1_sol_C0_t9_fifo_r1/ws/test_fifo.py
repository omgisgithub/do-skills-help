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
    day = date(2026, 1, 1)
    inv.buy("A", 1, "1.005", day)
    inv.buy("A", 1, "1.005", day)
    assert inv.sell("A", 2, day) == Decimal("2.01")
    inv.buy("A", 1, "2.345", day)
    assert inv.sell("A", 1, day) == Decimal("2.35")
    inv.buy("A", 1, "999.999", day)
    assert inv.sell("A", 1, day) == Decimal("1000.00")


def test_fifo_dates_and_recording_order():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 1, 5)
    inv.buy("A", 2, "10", late)
    inv.buy("A", 1, "2", early)
    inv.buy("A", 2, "3", early)
    assert inv.lots("A") == [
        (early, 1, Decimal("2")),
        (early, 2, Decimal("3")),
        (late, 2, Decimal("10")),
    ]
    assert inv.sell("A", 2, early) == Decimal("5.00")
    assert inv.lots("A") == [
        (early, 1, Decimal("3")), (late, 2, Decimal("10"))
    ]
    assert inv.sell("A", 3, late) == Decimal("23.00")
    assert inv.lots("A") == []
    assert inv.on_hand("A") == 0


def test_failed_sale_preserves_inventory():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 1, 5)
    inv.buy("A", 2, "1.125", early)
    inv.buy("A", 10, "3", late)
    inv.buy("B", 1, "4", early)
    before = inv.lots("A"), inv.lots("B"), inv.value()
    for sku, qty, day in [("A", 3, early), ("A", 13, late), ("missing", 1, late)]:
        try:
            inv.sell(sku, qty, day)
        except ValueError:
            pass
        else:
            raise AssertionError("sale with insufficient eligible stock succeeded")
        assert (inv.lots("A"), inv.lots("B"), inv.value()) == before
    assert inv.sell("A", 2, early) == Decimal("2.25")


def test_lots_are_detached_tuples():
    inv = Inventory()
    day = date(2026, 1, 1)
    inv.buy("A", 2, "1", day)
    lots = inv.lots("A")
    assert isinstance(lots[0], tuple)
    lots[0] = (day, 100, Decimal("9"))
    lots.clear()
    assert inv.lots("A") == [(day, 2, Decimal("1"))]
    assert inv.lots("missing") == []


def test_exact_values_and_low_decimal_precision():
    inv = Inventory()
    day = date(2026, 1, 1)
    with localcontext() as context:
        context.prec = 4
        inv.buy("A", 3, "1234567890123456789012345678.12345", day)
        inv.buy("B", 2, "0.00001", day)
        assert inv.value("A") == Decimal("3703703670370370367037037034.37035")
        assert inv.value() == Decimal("3703703670370370367037037034.37037")
        assert inv.sell("A", 2, day) == Decimal("2469135780246913578024691356.25")
        assert inv.value("A") == Decimal("1234567890123456789012345678.12345")
        assert context.prec == 4
    assert inv.value("missing") == 0


def test_invalid_inputs_leave_stock_unchanged():
    inv = Inventory()
    day = date(2026, 1, 1)
    for qty in (0, -1):
        for operation in (lambda: inv.buy("A", qty, "1", day),
                          lambda: inv.sell("A", qty, day)):
            try:
                operation()
            except ValueError:
                pass
            else:
                raise AssertionError("nonpositive quantity accepted")
    for cost in ("-1",):
        try:
            inv.buy("A", 1, cost, day)
        except ValueError:
            pass
        else:
            raise AssertionError("negative cost accepted")
    assert inv.lots("A") == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
