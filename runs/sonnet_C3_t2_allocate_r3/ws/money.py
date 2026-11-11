"""Money helpers."""

from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    try:
        return Fraction(w)
    except (ValueError, OverflowError):
        raise ValueError("weight must be finite and not NaN: %r" % (w,))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if type(total_cents) is not int and (
        isinstance(total_cents, bool) or not isinstance(total_cents, int)
    ):
        raise ValueError("total_cents must be an int")
    fracs = [_to_fraction(w) for w in weights]
    if not fracs:
        raise ValueError("weights must not be empty")
    if any(f < 0 for f in fracs):
        raise ValueError("weights must not be negative")
    weight_sum = sum(fracs, Fraction(0))
    if weight_sum == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    shares = []
    remainders = []
    for f in fracs:
        exact = amount * f / weight_sum
        floor = exact.numerator // exact.denominator
        shares.append(floor)
        remainders.append(exact - floor)

    leftover = amount - sum(shares)
    order = sorted(
        range(len(fracs)), key=lambda i: (-remainders[i], -fracs[i], i)
    )
    for i in order[:leftover]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-s for s in shares]
    return shares
