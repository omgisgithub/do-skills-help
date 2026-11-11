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


def assert_raises(error, function, *args):
    try:
        function(*args)
    except error:
        return
    raise AssertionError("expected " + error.__name__)


def test_round_once_half_up():
    day = date(2026, 1, 1)
    inv = Inventory()
    inv.buy("A", 1, "2.335", day)
    assert inv.value("A") == Decimal("2.335")
    assert inv.sell("A", 1, day) == Decimal("2.34")
    inv.buy("A", 1, "2.345", day)
    assert inv.sell("A", 1, day) == Decimal("2.35")
    inv.buy("A", 1, "0.005", day)
    inv.buy("A", 1, "0.005", day)
    result = inv.sell("A", 2, day)
    assert result == Decimal("0.01")
    assert result.as_tuple().exponent == -2
    assert inv.lots("A") == []


def test_fifo_dates_and_stable_ties():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 1, 2)
    inv.buy("A", 1, "3", late)
    inv.buy("A", 1, "1", early)
    inv.buy("A", 1, "2", early)
    assert inv.lots("A") == [
        (early, 1, Decimal("1")), (early, 1, Decimal("2")),
        (late, 1, Decimal("3")),
    ]
    assert inv.sell("A", 1, early) == Decimal("1.00")
    assert inv.sell("A", 1, early) == Decimal("2.00")
    assert inv.lots("A") == [(late, 1, Decimal("3"))]


def test_failed_sale_preserves_all_stock():
    inv = Inventory()
    early, late = date(2026, 1, 1), date(2026, 1, 2)
    inv.buy("A", 2, "1.234", early)
    inv.buy("A", 5, "9", late)
    inv.buy("B", 1, "4", early)
    before = inv.lots("A")
    value = inv.value()
    assert_raises(ValueError, inv.sell, "A", 3, early)
    assert inv.lots("A") == before
    assert inv.on_hand("A") == 7
    assert inv.value() == value
    assert_raises(ValueError, inv.sell, "A", 8, late)
    assert inv.lots("A") == before
    assert_raises(ValueError, inv.sell, "missing", 1, late)
    assert inv.lots("missing") == []
    assert inv.on_hand("missing") == 0
    assert inv.value("missing") == Decimal(0)


def test_lots_are_independent_tuples():
    inv = Inventory()
    day = date(2026, 1, 1)
    inv.buy("A", 2, 3, day)
    lots = inv.lots("A")
    assert isinstance(lots[0], tuple)
    lots[0] = (day, 100, Decimal(0))
    lots.clear()
    assert inv.lots("A") == [(day, 2, Decimal(3))]
    assert inv.sell("A", 1, day) == Decimal("3.00")
    assert inv.on_hand("A") == 1
    assert inv.value("A") == Decimal(3)


def test_input_validation():
    inv = Inventory()
    day = date(2026, 1, 1)
    for qty in (0, -1):
        assert_raises(ValueError, inv.buy, "A", qty, "1", day)
        assert_raises(ValueError, inv.sell, "A", qty, day)
    for qty in (1.5, Decimal("1"), "1"):
        assert_raises(TypeError, inv.buy, "A", qty, "1", day)
        assert_raises(TypeError, inv.sell, "A", qty, day)
    assert_raises(ValueError, inv.buy, "A", 1, "-0.01", day)
    assert inv.lots("A") == []
    for cost in (Decimal("1"), 1, "1"):
        inv.buy("A", 1, cost, day)
    inv.buy("A", 1, "0", day)
    assert inv.value() == Decimal(3)
    assert inv.sell("A", 4, day) == Decimal("3.00")


def test_exact_cost_with_small_decimal_context():
    inv = Inventory()
    day = date(2026, 1, 1)
    with localcontext() as context:
        context.prec = 6
        inv.buy("A", 3, "12345678901234567890.12345", day)
        inv.buy("B", 1, "0.00001", day)
        assert inv.value() == Decimal("37037036703703703670.37036")
        assert inv.sell("A", 2, day) == Decimal("24691357802469135780.25")
        assert inv.value("A") == Decimal("12345678901234567890.12345")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
