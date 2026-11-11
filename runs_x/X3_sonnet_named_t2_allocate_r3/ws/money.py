"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    if isinstance(w, Fraction):
        return w
    if isinstance(w, float):
        if math.isnan(w) or math.isinf(w):
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, Decimal):
        if not w.is_finite():
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, int):
        return Fraction(w)
    raise ValueError("unsupported weight type: %r" % type(w))


def allocate(total_cents, weights):
    """Split total_cents across weights (largest remainder). See TASK.md."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    ws = [_to_fraction(w) for w in list(weights)]
    if not ws:
        raise ValueError("weights must not be empty")
    if any(w < 0 for w in ws):
        raise ValueError("weights must not be negative")
    wsum = sum(ws, Fraction(0))
    if wsum == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    shares, rems = [], []
    for w in ws:
        exact = amount * w / wsum
        fl = exact.numerator // exact.denominator
        shares.append(fl)
        rems.append(exact - fl)

    leftover = amount - sum(shares)
    order = sorted(
        (i for i, w in enumerate(ws) if w > 0),
        key=lambda i: (-rems[i], -ws[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [-s for s in shares] if total_cents < 0 else shares
