"""Money helpers."""
from decimal import Decimal
from fractions import Fraction


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if type(total_cents) is not int:
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")
    fr = []
    for w in weights:
        if isinstance(w, bool) or not isinstance(w, (int, float, Fraction, Decimal)):
            raise ValueError("invalid weight: %r" % (w,))
        try:
            f = Fraction(w)
        except (ValueError, OverflowError):  # NaN / infinity
            raise ValueError("weight must be finite: %r" % (w,))
        if f < 0:
            raise ValueError("weight must not be negative: %r" % (w,))
        fr.append(f)
    s = sum(fr)
    if s == 0:
        raise ValueError("all weights are zero")

    n = abs(total_cents)
    exact = [n * f / s for f in fr]
    shares = [int(e) for e in exact]  # floor: exact >= 0
    order = sorted(range(len(fr)), key=lambda i: (shares[i] - exact[i], -fr[i], i))
    for i in order[: n - sum(shares)]:
        shares[i] += 1
    return shares if total_cents >= 0 else [-x for x in shares]


if __name__ == "__main__":
    assert allocate(100, [1, 1, 1]) == [34, 33, 33]
    assert allocate(100, [1, 2]) == [33, 67]
    assert allocate(7, [0.1, 0.2, 0.7]) == [1, 1, 5]
    assert allocate(0, [3, 5]) == [0, 0]
    assert allocate(-5, [1, 1]) == [-3, -2]
    assert allocate(1, [0, 1, 1]) == [0, 1, 0]
    assert allocate(1, [1, 2, 2, 0]) == [0, 1, 0, 0]
    for bad in [(1, []), (1, [-1, 2]), (1, [0, 0]), (1, [float("nan")]),
                (1, [float("inf")]), (1, [Decimal("NaN")]), (True, [1]), (1.0, [1])]:
        try:
            allocate(*bad)
        except ValueError:
            continue
        raise AssertionError(bad)
