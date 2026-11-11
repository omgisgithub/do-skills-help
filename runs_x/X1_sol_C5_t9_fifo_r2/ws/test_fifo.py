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


def test_date_order_and_same_date_stability():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 1, 3)
    inv.buy("A", 1, "9", late)
    inv.buy("A", 1, "2", early)
    inv.buy("A", 1, "3", early)
    assert inv.sell("A", 1, late) == Decimal("2.00")
    assert inv.sell("A", 1, late) == Decimal("3.00")
    assert inv.lots("A") == [(late, 1, Decimal("9"))]


def test_failed_sale_leaves_all_stock_unchanged():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 1, 3)
    inv.buy("A", 2, "1.25", early)
    inv.buy("A", 10, "3", late)
    inv.buy("B", 1, "7", early)
    try:
        inv.sell("A", 3, early)
    except ValueError:
        pass
    else:
        raise AssertionError("sale used unavailable stock")
    assert inv.on_hand("A") == 12
    assert inv.value() == Decimal("39.50")
    assert inv.sell("A", 2, early) == Decimal("2.50")
    assert inv.lots("A") == [(late, 10, Decimal("3"))]


def test_lots_are_an_independent_list_of_tuples():
    inv = Inventory()
    day = date(2026, 1, 1)
    inv.buy("A", 2, "1.25", day)
    lots = inv.lots("A")
    assert lots == [(day, 2, Decimal("1.25"))]
    lots[0] = (day, 99, Decimal("0"))
    lots.clear()
    assert inv.on_hand("A") == 2
    assert inv.value("A") == Decimal("2.50")


def test_fully_consumed_lots_disappear():
    inv = Inventory()
    day = date(2026, 1, 1)
    inv.buy("A", 1, 0, day)
    result = inv.sell("A", 1, day)
    assert result == Decimal("0.00")
    assert result.as_tuple().exponent == -2
    assert inv.lots("A") == []
    assert inv.on_hand("A") == 0


def test_exact_value_and_cogs_with_small_decimal_context():
    inv = Inventory()
    day = date(2026, 1, 1)
    inv.buy("A", 3, "1234567890123456789012345678.125", day)
    inv.buy("B", 1, "0.000000000000000000001", day)
    with localcontext() as ctx:
        ctx.prec = 6
        assert inv.value("A") == Decimal("3703703670370370367037037034.375")
        assert inv.value() == Decimal("3703703670370370367037037034.375000000000000000001")
        assert inv.sell("A", 1, day) == Decimal("1234567890123456789012345678.13")
    assert inv.value("A") == Decimal("2469135780246913578024691356.250")


def test_quantity_must_be_an_integer():
    day = date(2026, 1, 1)
    for qty in (1.5, Decimal("1.5"), "2"):
        inv = Inventory()
        inv.buy("A", 2, "1", day)
        for operation in (lambda: inv.buy("A", qty, "1", day),
                          lambda: inv.sell("A", qty, day)):
            try:
                operation()
            except TypeError:
                pass
            else:
                raise AssertionError("non-integer quantity accepted")
        assert inv.on_hand("A") == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
