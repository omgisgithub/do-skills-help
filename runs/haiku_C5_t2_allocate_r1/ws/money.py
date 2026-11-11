"""Money helpers."""

import decimal
import math
from fractions import Fraction


def _exact_weight(w):
    """Convert one weight to an exact Fraction, rejecting NaN and infinity."""
    if isinstance(w, float):
        if not math.isfinite(w):
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, decimal.Decimal):
        if not w.is_finite():
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, Fraction):
        return w
    if isinstance(w, int):
        return Fraction(int(w))
    raise TypeError("unsupported weight type: %s" % type(w).__name__)


def allocate(total_cents, weights):
    """Split total_cents across weights using largest-remainder allocation.

    Returns a list of ints, one per weight, that sums to total_cents exactly.
    See TASK.md for the full spec.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if len(weights) == 0:
        raise ValueError("weights must not be empty")

    exact = [_exact_weight(w) for w in weights]
    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    amount = abs(total_cents)
    shares = [amount * w / total_weight for w in exact]
    floors = [s.numerator // s.denominator for s in shares]
    remainders = [s - f for s, f in zip(shares, floors)]
    leftover = amount - sum(floors)

    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(
        range(len(weights)),
        key=lambda i: (-remainders[i], -exact[i], i),
    )
    result = list(floors)
    for i in order[:leftover]:
        result[i] += 1

    if total_cents < 0:
        result = [-x for x in result]
    return result
