"""Money helpers."""

from fractions import Fraction


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    weights = list(weights)
    if not weights:
        raise ValueError("weights must not be empty")

    exact = []
    for w in weights:
        try:
            f = Fraction(w)
        except (ValueError, OverflowError, TypeError) as e:
            raise ValueError("invalid weight: %r" % (w,)) from e
        if f < 0:
            raise ValueError("weights must not be negative")
        exact.append(f)

    weight_sum = sum(exact)
    if weight_sum == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    shares = []
    remainders = []
    for f in exact:
        q, r = divmod(amount * f / weight_sum, 1)
        shares.append(int(q))
        remainders.append(r)

    leftover = amount - sum(shares)
    order = sorted(
        (i for i, f in enumerate(exact) if f > 0),
        key=lambda i: (-remainders[i], -exact[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [-s for s in shares] if total_cents < 0 else shares
