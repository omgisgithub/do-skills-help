"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    if isinstance(w, bool):
        raise ValueError("invalid weight type")
    if isinstance(w, int):
        return Fraction(w)
    if isinstance(w, float):
        if math.isnan(w) or math.isinf(w):
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, Fraction):
        return w
    if isinstance(w, Decimal):
        if not w.is_finite():
            raise ValueError("weight must be finite")
        return Fraction(w)
    raise ValueError("invalid weight type")


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
    s = sum(fr, Fraction(0))
    if s == 0:
        raise ValueError("weights must not all be zero")

    total = abs(int(total_cents))
    shares = []
    rems = []
    for f in fr:
        exact = total * f / s
        fl = exact.numerator // exact.denominator
        shares.append(fl)
        rems.append(exact - fl)
    leftover = total - sum(shares)
    order = sorted(range(len(fr)), key=lambda i: (-rems[i], -fr[i], i))
    for i in order[:leftover]:
        shares[i] += 1
    if total_cents < 0:
        shares = [-x for x in shares]
    return shares
