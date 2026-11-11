"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    if isinstance(w, bool) or not isinstance(w, (int, float, Fraction, Decimal)):
        raise ValueError("invalid weight type: %r" % (w,))
    if isinstance(w, float):
        if math.isnan(w) or math.isinf(w):
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, Decimal):
        if not w.is_finite():
            raise ValueError("weight must be finite")
        return Fraction(w)
    return Fraction(w)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    weights = list(weights)
    if not weights:
        raise ValueError("weights must not be empty")
    fr = [_to_fraction(w) for w in weights]
    if any(f < 0 for f in fr):
        raise ValueError("weights must not be negative")
    wsum = sum(fr, Fraction(0))
    if wsum == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    exact = [f * amount / wsum for f in fr]
    shares = [e.numerator // e.denominator for e in exact]
    leftover = amount - sum(shares)
    # zero-weight parties never receive leftovers (their remainder is 0, and
    # leftover < number of parties with positive remainder, so this is safe)
    order = sorted(
        (i for i in range(len(fr)) if fr[i] > 0),
        key=lambda i: (-(exact[i] - shares[i]), -fr[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1
    if total_cents < 0:
        shares = [-s for s in shares]
    return shares
