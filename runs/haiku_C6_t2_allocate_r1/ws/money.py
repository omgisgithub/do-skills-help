"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact_weight(w):
    """Return weight w as an exact Fraction, or raise ValueError if it is invalid."""
    if isinstance(w, bool) or not isinstance(w, (int, float, Fraction, Decimal)):
        raise ValueError(f"unsupported weight type: {type(w).__name__}")
    if isinstance(w, float) and not math.isfinite(w):
        raise ValueError("weights must be finite")
    if isinstance(w, Decimal) and not w.is_finite():
        raise ValueError("weights must be finite")
    value = Fraction(w)
    if value < 0:
        raise ValueError("weights must not be negative")
    return value


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not isinstance(weights, list):
        raise ValueError("weights must be a list")
    if not weights:
        raise ValueError("weights must not be empty")

    ws = [_exact_weight(w) for w in weights]
    total_weight = sum(ws)
    if total_weight == 0:
        raise ValueError("all weights are zero")

    # Largest remainder method, using exact arithmetic throughout.
    total = abs(total_cents)
    exact = [total * w / total_weight for w in ws]
    shares = [math.floor(e) for e in exact]
    leftover = total - sum(shares)

    # Most remainder first; ties go to the larger weight, then the lower index.
    order = sorted(range(len(ws)), key=lambda i: (-(exact[i] - shares[i]), -ws[i], i))
    for i in order[:leftover]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-s for s in shares]
    return shares
