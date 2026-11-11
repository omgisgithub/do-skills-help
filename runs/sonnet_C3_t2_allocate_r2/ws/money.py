"""Money helpers."""

from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    if isinstance(w, Fraction):
        return w
    if isinstance(w, float):
        if w != w or w in (float("inf"), float("-inf")):
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, Decimal):
        if not w.is_finite():
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, int):
        return Fraction(w)
    raise ValueError("unsupported weight type: %r" % (type(w),))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    weights = list(weights)
    if not weights:
        raise ValueError("weights must not be empty")
    fracs = [_to_fraction(w) for w in weights]
    if any(f < 0 for f in fracs):
        raise ValueError("weights must not be negative")
    wsum = sum(fracs, Fraction(0))
    if wsum == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    shares = []
    rems = []
    for f in fracs:
        exact = f * amount / wsum
        fl = exact.numerator // exact.denominator
        shares.append(fl)
        rems.append(exact - fl)

    leftover = amount - sum(shares)
    order = sorted(range(len(fracs)), key=lambda i: (-rems[i], -fracs[i], i))
    for i in order[:leftover]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-s for s in shares]
    return shares
