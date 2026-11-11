"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact_weight(w):
    """Return weight w as an exact Fraction, rejecting NaN and infinity."""
    if isinstance(w, float) and not math.isfinite(w):
        raise ValueError("weights must be finite")
    if isinstance(w, Decimal) and not w.is_finite():
        raise ValueError("weights must be finite")
    return Fraction(w)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact = [_exact_weight(w) for w in weights]
    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")
    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    cents = abs(total_cents)
    shares = [cents * w / total_weight for w in exact]
    floors = [s.numerator // s.denominator for s in shares]
    leftover = cents - sum(floors)

    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(
        range(len(exact)),
        key=lambda i: (-(shares[i] - floors[i]), -exact[i], i),
    )
    for i in order[:leftover]:
        floors[i] += 1

    if total_cents < 0:
        floors = [-f for f in floors]
    return floors
