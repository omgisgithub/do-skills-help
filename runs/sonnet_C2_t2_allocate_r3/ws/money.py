"""Money helpers."""
from fractions import Fraction


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if type(total_cents) is not int:
        raise ValueError("total_cents must be an int")
    try:
        w = [Fraction(x) for x in weights]  # NaN/inf raise ValueError/OverflowError
    except (ValueError, OverflowError) as e:
        raise ValueError("weights must be finite numbers") from e
    if not w:
        raise ValueError("weights is empty")
    if any(x < 0 for x in w):
        raise ValueError("negative weight")
    s = sum(w)
    if s == 0:
        raise ValueError("all weights are zero")

    n = abs(total_cents)
    exact = [n * x / s for x in w]
    shares = [int(e) for e in exact]  # floor: exact is non-negative
    order = sorted(range(len(w)), key=lambda i: (-(exact[i] - shares[i]), -w[i], i))
    for i in order[: n - sum(shares)]:
        shares[i] += 1
    return [-x for x in shares] if total_cents < 0 else shares


if __name__ == "__main__":
    from decimal import Decimal
    assert allocate(100, [1, 1, 1]) == [34, 33, 33]
    assert allocate(100, [1, 2]) == [33, 67]
    assert allocate(7, [0.1, 0.2, 0.7]) == [1, 1, 5]
    assert allocate(0, [3, 5]) == [0, 0]
    assert allocate(-5, [1, 1]) == [-3, -2]
    assert allocate(5, [0, 1, 1]) == [0, 3, 2]
    assert allocate(3, [Decimal("0.5"), Fraction(1, 2)]) == [2, 1]
    for tot, ws in [(1, []), (1, [-1, 2]), (1, [0, 0]), (1, [float("nan")]),
                    (1, [float("inf")]), (1, [Decimal("NaN")]), (1.0, [1]), (True, [1])]:
        try:
            allocate(tot, ws)
        except ValueError:
            continue
        raise AssertionError((tot, ws))
