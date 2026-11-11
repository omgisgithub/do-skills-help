from datetime import date
from decimal import Decimal, Inexact, localcontext
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
    inv.buy("A", 1, "1.005", date(2026, 1, 2))
    assert inv.sell("A", 2, date(2026, 1, 2)) == Decimal("2.01")
    inv.buy("A", 1, "2.345", date(2026, 1, 1))
    result = inv.sell("A", 1, date(2026, 1, 1))
    assert result == Decimal("2.35")
    assert result.as_tuple().exponent == -2


def test_fifo_dates_and_stable_ties():
    inv = Inventory()
    inv.buy("A", 1, "9", date(2026, 1, 3))
    inv.buy("A", 1, "2", date(2026, 1, 1))
    inv.buy("A", 1, "3", date(2026, 1, 1))
    assert inv.sell("A", 1, date(2026, 1, 3)) == Decimal("2.00")
    assert inv.lots("A") == [
        (date(2026, 1, 1), 1, Decimal("3")),
        (date(2026, 1, 3), 1, Decimal("9")),
    ]
    assert inv.sell("A", 1, date(2026, 1, 3)) == Decimal("3.00")


def test_insufficient_eligible_stock_is_atomic():
    inv = Inventory()
    inv.buy("A", 2, "1.125", date(2026, 1, 1))
    inv.buy("A", 5, "3", date(2026, 1, 3))
    inv.buy("B", 1, "4", date(2026, 1, 1))
    before = [tuple(lot) for lot in inv.lots("A")]
    try:
        inv.sell("A", 3, date(2026, 1, 2))
    except ValueError:
        pass
    else:
        raise AssertionError("sale used future stock")
    assert [tuple(lot) for lot in inv.lots("A")] == before
    assert inv.on_hand("A") == 7
    assert inv.value() == Decimal("21.250")
    assert inv.sell("A", 2, date(2026, 1, 1)) == Decimal("2.25")
    assert inv.lots("A") == [(date(2026, 1, 3), 5, Decimal("3"))]


def test_lots_snapshot_cannot_mutate_inventory():
    inv = Inventory()
    inv.buy("A", 2, 3, date(2026, 1, 1))
    snapshot = inv.lots("A")
    assert isinstance(snapshot[0], tuple)
    snapshot.clear()
    assert inv.on_hand("A") == 2
    assert inv.value("A") == Decimal("6")
    inv.sell("A", 2, date(2026, 1, 1))
    assert inv.lots("A") == []


def test_exact_costs_despite_decimal_context():
    inv = Inventory()
    inv.buy("A", 3, "1234567890123456789012345678.335", date(2026, 1, 1))
    inv.buy("B", 1, "0.001", date(2026, 1, 1))
    with localcontext() as ctx:
        ctx.prec = 6
        assert inv.value() == Decimal("3703703670370370367037037035.006")
        assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("1234567890123456789012345678.34")
        assert inv.value("A") == Decimal("2469135780246913578024691356.670")


def test_costs_isolate_caller_decimal_settings():
    inv = Inventory()
    inv.buy("A", 2, "1000.005", date(2026, 1, 1))
    with localcontext() as ctx:
        ctx.Emax = 2
        ctx.traps[Inexact] = True
        assert inv.value() == Decimal("2000.010")
        assert inv.sell("A", 1, date(2026, 1, 1)) == Decimal("1000.01")
        assert ctx.Emax == 2
        assert ctx.traps[Inexact]


def test_quantity_must_be_positive_integer():
    inv = Inventory()
    inv.buy("A", 2, "1", date(2026, 1, 1))
    for qty in (0, -1, 1.5, "1"):
        for operation in (
            lambda: inv.buy("A", qty, "1", date(2026, 1, 1)),
            lambda: inv.sell("A", qty, date(2026, 1, 1)),
        ):
            try:
                operation()
            except (TypeError, ValueError):
                pass
            else:
                raise AssertionError("invalid quantity accepted")
    assert inv.on_hand("A") == 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
