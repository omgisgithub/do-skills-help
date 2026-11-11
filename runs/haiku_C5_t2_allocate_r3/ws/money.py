"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting NaN and infinity."""
    if isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(weight)
    if isinstance(weight, float) and (math.isnan(weight) or math.isinf(weight)):
        raise ValueError("weights must be finite")
    return Fraction(weight)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    weights = list(weights)
    if not weights:
        raise ValueError("weights must not be empty")

    exact = [_to_fraction(w) for w in weights]
    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    amount = abs(total_cents)
    shares = [amount * w / total_weight for w in exact]
    floors = [int(share) for share in shares]
    leftover = amount - sum(floors)

    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(
        range(len(weights)),
        key=lambda i: (-(shares[i] - floors[i]), -exact[i], i),
    )
    for i in order[:leftover]:
        floors[i] += 1

    if total_cents < 0:
        return [-s for s in floors]
    return floors
