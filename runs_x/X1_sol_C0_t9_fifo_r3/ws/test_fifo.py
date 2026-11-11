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
    inv.buy("A", 1, "1.004", day)
    inv.buy("A", 1, "1.001", day)
    assert inv.sell("A", 2, day) == Decimal("2.01")
    inv.buy("A", 1, "2.345", day)
    result = inv.sell("A", 1, day)
    assert result == Decimal("2.35")
    assert result.as_tuple().exponent == -2
    assert inv.lots("A") == []


def test_fifo_dates_and_stable_ties():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 1, 2)
    inv.buy("A", 1, "9", late)
    inv.buy("A", 1, "2", early)
    inv.buy("A", 2, "3", early)
    assert inv.lots("A") == [
        (early, 1, Decimal("2")),
        (early, 2, Decimal("3")),
        (late, 1, Decimal("9")),
    ]
    assert inv.sell("A", 2, early) == Decimal("5.00")
    assert inv.value("A") == Decimal("12")
    assert inv.lots("A") == [
        (early, 1, Decimal("3")), (late, 1, Decimal("9"))]


def test_failed_sale_preserves_all_stock():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 2, 1)
    inv.buy("A", 2, "1.234", early)
    inv.buy("A", 10, "5", late)
    inv.buy("B", 1, "7", early)
    before = inv.lots("A"), inv.lots("B"), inv.value(), inv.on_hand("A")
    for sku, qty in [("A", 3), ("missing", 1)]:
        try:
            inv.sell(sku, qty, early)
        except ValueError:
            pass
        else:
            raise AssertionError("unavailable stock sold")
        assert before == (inv.lots("A"), inv.lots("B"),
                          inv.value(), inv.on_hand("A"))
    assert inv.sell("A", 2, early) == Decimal("2.47")
    assert inv.lots("A") == [(late, 10, Decimal("5"))]


def test_lots_are_detached_tuples():
    inv = Inventory()
    day = date(2026, 1, 1)
    inv.buy("A", 2, 3, day)
    lots = inv.lots("A")
    assert isinstance(lots[0], tuple)
    lots[0] = (day, 100, Decimal("0"))
    lots.clear()
    assert inv.lots("A") == [(day, 2, Decimal("3"))]


def test_exact_value_and_cogs_with_small_decimal_context():
    inv = Inventory()
    day = date(2026, 1, 1)
    inv.buy("A", 3, "123456789012345678901234567890.005", day)
    inv.buy("B", 1, "0.0001", day)
    with localcontext() as context:
        context.prec = 6
        assert inv.value() == Decimal("370370367037037036703703703670.0151")
        assert inv.sell("A", 2, day) == Decimal("246913578024691357802469135780.01")
        assert inv.value("A") == Decimal("123456789012345678901234567890.005")
        assert context.prec == 6
    assert inv.value("missing") == Decimal(0)
    assert isinstance(inv.value("missing"), Decimal)


def test_quantity_validation():
    inv = Inventory()
    day = date(2026, 1, 1)
    inv.buy("A", 2, "1", day)
    for qty, error in [(0, ValueError), (-1, ValueError), (1.5, TypeError)]:
        for operation in [lambda: inv.buy("A", qty, "1", day),
                          lambda: inv.sell("A", qty, day)]:
            try:
                operation()
            except error:
                pass
            else:
                raise AssertionError("invalid quantity accepted")
    assert inv.on_hand("A") == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
