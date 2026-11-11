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


def assert_raises(error, operation):
    try:
        operation()
    except error:
        return
    raise AssertionError("expected " + error.__name__)


def test_rounding_once_half_up():
    day = date(2026, 1, 1)
    for price, expected in [("2.335", "2.34"), ("2.345", "2.35")]:
        inv = Inventory()
        inv.buy("A", 1, price, day)
        result = inv.sell("A", 1, day)
        assert result == Decimal(expected)
        assert result.as_tuple().exponent == -2
    inv = Inventory()
    inv.buy("A", 1, "0.004", day)
    inv.buy("A", 1, "0.004", day)
    assert inv.sell("A", 2, day) == Decimal("0.01")
    assert inv.lots("A") == []


def test_fifo_dates_and_stable_ties():
    inv = Inventory()
    first, second, future = (date(2026, 1, n) for n in (1, 2, 3))
    inv.buy("A", 1, "9", future)
    inv.buy("A", 1, "2", second)
    inv.buy("A", 1, "1", first)
    inv.buy("A", 2, "3", second)
    assert inv.lots("A") == [
        (first, 1, Decimal("1")),
        (second, 1, Decimal("2")),
        (second, 2, Decimal("3")),
        (future, 1, Decimal("9")),
    ]
    assert inv.sell("A", 3, second) == Decimal("6.00")
    assert inv.lots("A") == [
        (second, 1, Decimal("3")), (future, 1, Decimal("9"))
    ]


def test_failed_sale_is_atomic():
    inv = Inventory()
    day, future = date(2026, 1, 1), date(2026, 1, 2)
    inv.buy("A", 2, "2.335", day)
    inv.buy("A", 10, "5", future)
    inv.buy("B", 1, "7", day)
    before = inv.lots("A"), inv.lots("B"), inv.value()
    for qty, when in [(3, day), (13, future)]:
        assert_raises(ValueError, lambda: inv.sell("A", qty, when))
        assert (inv.lots("A"), inv.lots("B"), inv.value()) == before
        assert inv.on_hand("A") == 12
    assert_raises(ValueError, lambda: inv.sell("missing", 1, day))
    assert inv.on_hand("missing") == 0
    assert inv.lots("missing") == []
    assert inv.value("missing") == Decimal(0)


def test_lots_are_detached_tuples():
    inv = Inventory()
    day = date(2026, 1, 1)
    inv.buy("A", 2, 3, day)
    lots = inv.lots("A")
    assert isinstance(lots, list) and isinstance(lots[0], tuple)
    lots[0] = (day, 99, Decimal(0))
    lots.clear()
    assert inv.on_hand("A") == 2
    assert inv.value() == Decimal(6)


def test_quantities_and_costs():
    inv = Inventory()
    day = date(2026, 1, 1)
    for qty in [0, -1]:
        assert_raises(ValueError, lambda: inv.buy("A", qty, "1", day))
        assert_raises(ValueError, lambda: inv.sell("A", qty, day))
    for qty in [1.5, "1", Decimal(1), True]:
        assert_raises(TypeError, lambda: inv.buy("A", qty, "1", day))
        assert_raises(TypeError, lambda: inv.sell("A", qty, day))
    for cost in [-1, "-0.01", Decimal("-2")]:
        assert_raises(ValueError, lambda: inv.buy("A", 1, cost, day))
    for cost in [1.5, None, object()]:
        assert_raises(TypeError, lambda: inv.buy("A", 1, cost, day))
    assert inv.lots("A") == []
    for cost in [0, "2.335", Decimal("1.125")]:
        inv.buy("A", 1, cost, day)
    assert inv.value("A") == Decimal("3.460")
    assert inv.sell("A", 3, day) == Decimal("3.46")
    assert inv.value() == Decimal(0)


def test_exact_costs_with_small_decimal_context():
    inv = Inventory()
    day = date(2026, 1, 1)
    price = Decimal("123456789012345678901234567890.12345")
    with localcontext() as context:
        context.prec = 3
        inv.buy("A", 3, price, day)
        inv.buy("B", 1, "0.000006", day)
        assert inv.value("A") == Decimal("370370367037037036703703703670.37035")
        assert inv.value() == Decimal("370370367037037036703703703670.370356")
        assert inv.sell("A", 2, day) == Decimal("246913578024691357802469135780.25")
        assert inv.value("A") == price


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
