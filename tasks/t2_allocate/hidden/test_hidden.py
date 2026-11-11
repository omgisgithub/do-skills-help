from fractions import Fraction
from decimal import Decimal
import random
from money import allocate


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    except Exception as e:
        print("   wrong exception type:", type(e).__name__)
        return False
    return False


def test_examples():
    assert allocate(100, [1, 1, 1]) == [34, 33, 33]
    assert allocate(100, [1, 2]) == [33, 67]
    assert allocate(7, [0.1, 0.2, 0.7]) == [1, 1, 5]
    assert allocate(0, [3, 5]) == [0, 0]
    assert allocate(-5, [1, 1]) == [-3, -2]


def test_tie_goes_to_larger_weight():
    # exact shares 1/3*... : weights 1,1,2 of 5 -> 1.25,1.25,2.5 -> floors 1,1,2 left 1
    # remainders .25,.25,.5 -> index 2 gets it
    assert allocate(5, [1, 1, 2]) == [1, 1, 3]
    # remainders tie between weights 2 and 4? total 3, weights [2,4]: 1.0, 2.0 none left
    # total 1, weights [1,3]: .25,.75 -> idx1
    assert allocate(1, [1, 3]) == [0, 1]
    # tie in remainder, different weights: total 2, weights [1, 3, 1, 3] (sum 8)
    # exact .25,.75,.25,.75 -> floors 0 -> left 2 -> both .75: idx1, idx3
    assert allocate(2, [1, 3, 1, 3]) == [0, 1, 0, 1]
    assert allocate(3, [3, 1, 2]) == [2, 0, 1]
    assert allocate(3, [1, 3, 2]) == [0, 2, 1]


def test_tie_equal_weight_lower_index():
    assert allocate(1, [1, 1]) == [1, 0]
    assert allocate(2, [1, 1, 1]) == [1, 1, 0]


def test_float_weights_exact():
    # 0.1 + 0.2 != 0.3 in floats; Fraction(0.1) is slightly above 0.1, Fraction(0.2) slightly above 0.2,
    # Fraction(0.3) slightly below 0.3 -> no naive float tie
    r = allocate(1, [0.1, 0.2, 0.3, 0.4])
    assert sum(r) == 1
    exact = [Fraction(x) for x in [0.1, 0.2, 0.3, 0.4]]
    s = sum(exact)
    rem = [e / s - int(e / s) for e in exact]
    want = [0, 0, 0, 0]
    want[max(range(4), key=lambda i: (rem[i], exact[i], -i))] = 1
    assert r == want, (r, want)


def test_decimal_and_fraction():
    assert allocate(10, [Decimal("1.5"), Decimal("1.5"), Decimal("2")]) == [3, 3, 4]
    assert allocate(10, [Fraction(1, 3), Fraction(1, 3), Fraction(1, 3)]) == [4, 3, 3]


def test_zero_weight_gets_zero():
    assert allocate(3, [0, 1, 1]) == [0, 2, 1]
    assert allocate(1, [0, 0, 5]) == [0, 0, 1]


def test_negative_total():
    assert allocate(-100, [1, 1, 1]) == [-34, -33, -33]
    assert allocate(-1, [1, 3]) == [0, -1]


def test_errors():
    assert raises(lambda: allocate(10, []))
    assert raises(lambda: allocate(10, [1, -1]))
    assert raises(lambda: allocate(10, [0, 0]))
    assert raises(lambda: allocate(10, [1, float("nan")]))
    assert raises(lambda: allocate(10, [1, float("inf")]))
    assert raises(lambda: allocate(10.0, [1, 1]))
    assert raises(lambda: allocate(True, [1, 1]))
    assert raises(lambda: allocate("10", [1, 1]))


def test_does_not_mutate():
    w = [3, 1, 2]
    allocate(10, w)
    assert w == [3, 1, 2]


def test_random_invariants():
    rng = random.Random(7)
    for _ in range(500):
        n = rng.randint(1, 8)
        ws = [rng.choice([0, 1, 2, 3, 5, 7, 10, 0.5, 0.25, 1.1]) for _ in range(n)]
        if sum(ws) == 0:
            ws[0] = 1
        t = rng.randint(-1000, 1000)
        r = allocate(t, ws)
        assert sum(r) == t
        assert len(r) == n
        tot = sum(Fraction(w) for w in ws)
        for x, w in zip(r, ws):
            if w == 0:
                assert x == 0
            exact = abs(t) * Fraction(w) / tot
            assert abs(abs(x) - exact) < 1


def test_large_values():
    assert allocate(10**18 + 1, [1, 1]) == [5 * 10**17 + 1, 5 * 10**17]


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                fails += 1
                print("FAIL", name, type(e).__name__, e)
    sys.exit(1 if fails else 0)
