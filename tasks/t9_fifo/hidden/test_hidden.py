import subprocess
import sys
from datetime import date
from decimal import Decimal
from fifo import Inventory

D = date


def test_existing_tests_pass():
    r = subprocess.run([sys.executable, "test_fifo.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_rounding_once_half_up():
    inv = Inventory()
    inv.buy("A", 1, "1.005", D(2026, 1, 1))
    inv.buy("A", 1, "1.005", D(2026, 1, 2))
    # exact sum 2.010 -> 2.01 ; per-lot rounding of floats gives 1.0 + 1.0 = 2.00
    assert inv.sell("A", 2, D(2026, 1, 3)) == Decimal("2.01")
    inv2 = Inventory()
    inv2.buy("B", 1, "2.345", D(2026, 1, 1))
    assert inv2.sell("B", 1, D(2026, 1, 2)) == Decimal("2.35")
    inv3 = Inventory()
    inv3.buy("C", 3, "0.115", D(2026, 1, 1))
    assert inv3.sell("C", 3, D(2026, 1, 1)) == Decimal("0.35")  # 0.345 -> 0.35


def test_large_exact():
    inv = Inventory()
    inv.buy("A", 1000000, "0.0001", D(2026, 1, 1))
    inv.buy("A", 3, "33333333.335", D(2026, 1, 2))
    assert inv.sell("A", 1000003, D(2026, 2, 1)) == Decimal("100000100.01")


def test_out_of_order_purchases():
    inv = Inventory()
    inv.buy("A", 5, "3.00", D(2026, 1, 10))
    inv.buy("A", 5, "1.00", D(2026, 1, 1))   # late invoice for an earlier date
    assert inv.sell("A", 6, D(2026, 1, 20)) == Decimal("8.00")
    assert inv.lots("A") == [(D(2026, 1, 10), 4, Decimal("3.00"))]


def test_same_date_keeps_record_order():
    inv = Inventory()
    inv.buy("A", 1, "5", D(2026, 1, 2))
    inv.buy("A", 1, "7", D(2026, 1, 1))
    inv.buy("A", 1, "6", D(2026, 1, 2))
    assert [l[2] for l in inv.lots("A")] == [Decimal("7"), Decimal("5"), Decimal("6")]
    assert inv.sell("A", 2, D(2026, 1, 3)) == Decimal("12.00")


def test_failed_sale_changes_nothing():
    inv = Inventory()
    inv.buy("A", 2, "1.00", D(2026, 1, 1))
    inv.buy("A", 2, "2.00", D(2026, 1, 2))
    before = inv.lots("A")
    try:
        inv.sell("A", 5, D(2026, 1, 3))
        raise AssertionError("oversell accepted")
    except ValueError:
        pass
    assert inv.on_hand("A") == 4
    assert inv.lots("A") == before
    assert inv.sell("A", 4, D(2026, 1, 3)) == Decimal("6.00")


def test_future_lots_not_sold_and_failure_atomic():
    inv = Inventory()
    inv.buy("A", 2, "1.00", D(2026, 1, 1))
    inv.buy("A", 10, "9.00", D(2026, 3, 1))
    try:
        inv.sell("A", 3, D(2026, 2, 1))
        raise AssertionError("sold future stock")
    except ValueError:
        pass
    assert inv.on_hand("A") == 12
    assert inv.sell("A", 2, D(2026, 2, 1)) == Decimal("2.00")


def test_used_lots_disappear():
    inv = Inventory()
    inv.buy("A", 3, "1.00", D(2026, 1, 1))
    inv.buy("A", 3, "2.00", D(2026, 1, 2))
    inv.sell("A", 3, D(2026, 1, 3))
    assert inv.lots("A") == [(D(2026, 1, 2), 3, Decimal("2.00"))]
    inv.sell("A", 3, D(2026, 1, 3))
    assert inv.lots("A") == []
    assert inv.on_hand("A") == 0


def test_lots_is_a_copy():
    inv = Inventory()
    inv.buy("A", 3, "1.00", D(2026, 1, 1))
    got = inv.lots("A")
    assert got == [(D(2026, 1, 1), 3, Decimal("1.00"))]
    assert all(isinstance(x, tuple) for x in got)
    got.clear()
    assert inv.on_hand("A") == 3
    assert inv.lots("unknown") == []


def test_value():
    inv = Inventory()
    inv.buy("A", 3, "1.115", D(2026, 1, 1))
    inv.buy("B", 2, "0.5", D(2026, 1, 1))
    assert inv.value("A") == Decimal("3.345")
    assert inv.value() == Decimal("4.345")
    inv.sell("A", 1, D(2026, 1, 2))
    assert inv.value() == Decimal("3.230")
    assert inv.value("nope") == 0


def test_validation():
    inv = Inventory()
    for bad in [(0, "1"), (-1, "1")]:
        try:
            inv.buy("A", bad[0], bad[1], D(2026, 1, 1))
            raise AssertionError("accepted")
        except ValueError:
            pass
    try:
        inv.buy("A", 1, "-0.01", D(2026, 1, 1))
        raise AssertionError("accepted negative cost")
    except ValueError:
        pass
    try:
        inv.sell("A", 0, D(2026, 1, 1))
        raise AssertionError("accepted qty 0")
    except ValueError:
        pass


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                fails += 1
                print("FAIL", name, type(e).__name__, str(e)[:600])
    sys.exit(1 if fails else 0)
