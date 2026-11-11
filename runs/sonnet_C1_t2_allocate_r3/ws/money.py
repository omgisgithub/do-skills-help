"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    if isinstance(w, float):
        if math.isnan(w) or math.isinf(w):
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, Decimal):
        if not w.is_finite():
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, (int, Fraction)):
        return Fraction(w)
    raise ValueError("unsupported weight type: %r" % (type(w),))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    fracs = [_to_fraction(w) for w in weights]
    if not fracs:
        raise ValueError("weights must not be empty")
    if any(f < 0 for f in fracs):
        raise ValueError("weights must not be negative")
    weight_sum = sum(fracs)
    if weight_sum == 0:
        raise ValueError("weights must not all be zero")

    total = abs(total_cents)
    exact = [total * f / weight_sum for f in fracs]
    shares = [e.numerator // e.denominator for e in exact]
    leftover = total - sum(shares)
    order = sorted(
        (i for i, f in enumerate(fracs) if f > 0),
        key=lambda i: (-(exact[i] - shares[i]), -fracs[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1
    return [-s for s in shares] if total_cents < 0 else shares
