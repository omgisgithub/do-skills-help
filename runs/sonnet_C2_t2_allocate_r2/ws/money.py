"""Money helpers."""
from fractions import Fraction


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if type(total_cents) is not int:
        raise ValueError("total_cents must be an int")
    try:
        fw = [Fraction(w) for w in weights]  # NaN/inf raise ValueError/OverflowError
    except (OverflowError, TypeError) as e:
        raise ValueError(str(e))
    if not fw:
        raise ValueError("weights is empty")
    if any(w < 0 for w in fw):
        raise ValueError("negative weight")
    s = sum(fw)
    if s == 0:
        raise ValueError("all weights are zero")
    t = abs(total_cents)
    exact = [t * w / s for w in fw]
    shares = [int(x) for x in exact]  # floor: x >= 0
    order = sorted(range(len(fw)), key=lambda i: (-(exact[i] - shares[i]), -fw[i], i))
    for i in order[: t - sum(shares)]:
        shares[i] += 1
    return shares if total_cents >= 0 else [-x for x in shares]


if __name__ == "__main__":
    assert allocate(100, [1, 1, 1]) == [34, 33, 33]
    assert allocate(100, [1, 2]) == [33, 67]
    assert allocate(7, [0.1, 0.2, 0.7]) == [1, 1, 5]
    assert allocate(0, [3, 5]) == [0, 0]
    assert allocate(-5, [1, 1]) == [-3, -2]
    assert allocate(5, [0, 1, 1]) == [0, 3, 2]
    for bad in [(1, []), (1, [-1, 2]), (1, [0, 0]), (1, [float("nan")]),
                (1, [float("inf")]), (1.0, [1]), (True, [1])]:
        try:
            allocate(*bad)
        except ValueError:
            continue
        raise AssertionError(bad)
