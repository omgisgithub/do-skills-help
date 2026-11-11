"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact(w):
    if isinstance(w, float) and not math.isfinite(w):
        raise ValueError("weight must be finite")
    if isinstance(w, Decimal) and not w.is_finite():
        raise ValueError("weight must be finite")
    return Fraction(w)  # exact: floats convert to their binary value, not a rounded decimal


def allocate(total_cents, weights):
    """Split total_cents across weights by largest remainder. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    ws = [_exact(w) for w in weights]
    if any(w < 0 for w in ws):
        raise ValueError("weights must not be negative")
    total_weight = sum(ws)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    total = abs(total_cents)
    shares = [total * w / total_weight for w in ws]
    result = [s.numerator // s.denominator for s in shares]
    leftover = total - sum(result)

    # Tie-break: larger remainder, then larger weight, then lower index.
    order = sorted(
        range(len(ws)),
        key=lambda i: (-(shares[i] - result[i]), -ws[i], i),
    )
    for i in order[:leftover]:
        result[i] += 1

    if total_cents < 0:
        result = [-r for r in result]
    return result
