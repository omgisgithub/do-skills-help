"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    if isinstance(w, float):
        if not math.isfinite(w):
            raise ValueError("weight must be finite")
    elif isinstance(w, Decimal):
        if not w.is_finite():
            raise ValueError("weight must be finite")
    return Fraction(w)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    fw = [_to_fraction(w) for w in weights]
    if not fw:
        raise ValueError("weights must not be empty")
    if any(w < 0 for w in fw):
        raise ValueError("weights must not be negative")
    wsum = sum(fw, Fraction(0))
    if wsum == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    shares = []
    rems = []
    for w in fw:
        exact = amount * w / wsum
        fl = exact.numerator // exact.denominator
        shares.append(fl)
        rems.append(exact - fl)

    leftover = amount - sum(shares)
    order = sorted(
        (i for i, w in enumerate(fw) if w > 0),
        key=lambda i: (-rems[i], -fw[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [-s for s in shares] if total_cents < 0 else shares
