"""Money helpers."""

from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    try:
        if isinstance(w, float):
            if w != w or w in (float("inf"), float("-inf")):
                raise ValueError("weight must be finite")
        elif isinstance(w, Decimal):
            if not w.is_finite():
                raise ValueError("weight must be finite")
        return Fraction(w)
    except (TypeError, OverflowError) as exc:
        raise ValueError("invalid weight: %r" % (w,)) from exc


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    fracs = [_to_fraction(w) for w in list(weights)]
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
        (i for i, f in enumerate(fracs) if f > 0),
        key=lambda i: (-remainders[i], -fracs[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [-s for s in shares] if total_cents < 0 else shares
