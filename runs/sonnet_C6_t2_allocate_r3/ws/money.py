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
    elif isinstance(w, Decimal):
        if not w.is_finite():
            raise ValueError("weight must be finite")
    f = Fraction(w)
    if f < 0:
        raise ValueError("weight must not be negative")
    return f


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if type(total_cents) is not int and (
        isinstance(total_cents, bool) or not isinstance(total_cents, int)
    ):
        raise ValueError("total_cents must be an int")
    fracs = [_to_fraction(w) for w in list(weights)]
    if not fracs:
        raise ValueError("weights must not be empty")
    total_w = sum(fracs, Fraction(0))
    if total_w == 0:
        raise ValueError("weights must not all be zero")

    sign = -1 if total_cents < 0 else 1
    t = abs(total_cents)
    shares = []
    rems = []
    for f in fracs:
        exact = t * f / total_w
        fl = exact.numerator // exact.denominator
        shares.append(fl)
        rems.append(exact - fl)
    leftover = t - sum(shares)
    order = sorted(
        (i for i, f in enumerate(fracs) if f > 0),
        key=lambda i: (-rems[i], -fracs[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1
    return [sign * s for s in shares]
