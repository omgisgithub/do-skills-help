"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    if isinstance(w, Fraction):
        return w
    if isinstance(w, int):
        return Fraction(w)
    if isinstance(w, (float, Decimal)):
        try:
            if math.isnan(w) or math.isinf(w):
                raise ValueError("weight must be finite")
        except TypeError:
            pass
        return Fraction(w)
    raise ValueError("unsupported weight type: %r" % type(w))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    fracs = [_to_fraction(w) for w in list(weights)]
    if not fracs:
        raise ValueError("weights must not be empty")
    if any(f < 0 for f in fracs):
        raise ValueError("weights must not be negative")
    wsum = sum(fracs, Fraction(0))
    if wsum == 0:
        raise ValueError("weights must not all be zero")

    n = abs(total_cents)
    shares = []
    rems = []
    for f in fracs:
        exact = f * n / wsum
        fl = exact.numerator // exact.denominator
        shares.append(fl)
        rems.append(exact - fl)

    leftover = n - sum(shares)
    order = sorted(
        (i for i, f in enumerate(fracs) if f > 0),
        key=lambda i: (-rems[i], -fracs[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [-s if total_cents < 0 else s for s in shares]
