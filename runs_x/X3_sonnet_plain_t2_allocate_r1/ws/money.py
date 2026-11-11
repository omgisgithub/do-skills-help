"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    if isinstance(w, bool):
        return Fraction(int(w))
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
    total_w = sum(ws, Fraction(0))
    if total_w == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    exact = [w * amount / total_w for w in ws]
    shares = [e.numerator // e.denominator for e in exact]
    leftover = amount - sum(shares)
    order = sorted(range(len(ws)),
                   key=lambda i: (-(exact[i] - shares[i]), -ws[i], i))
    for i in order[:leftover]:
        shares[i] += 1
    return [-s for s in shares] if total_cents < 0 else shares
