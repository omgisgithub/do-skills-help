"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting NaN and infinity."""
    if isinstance(weight, int):
        return Fraction(weight)
    if isinstance(weight, float):
        if math.isnan(weight) or math.isinf(weight):
            raise ValueError("weights must be finite numbers")
        return Fraction(weight)
    if isinstance(weight, Decimal):
        if weight.is_nan() or weight.is_infinite():
            raise ValueError("weights must be finite numbers")
        return Fraction(weight)
    if isinstance(weight, Fraction):
        return weight
    raise TypeError("unsupported weight type: %s" % type(weight).__name__)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if len(weights) == 0:
        raise ValueError("weights must not be empty")

    fracs = [_to_fraction(w) for w in weights]
    if any(f < 0 for f in fracs):
        raise ValueError("weights must not be negative")
    total_weight = sum(fracs)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    total = abs(total_cents)
    floors = []
    remainders = []
    for f in fracs:
        exact = total * f / total_weight
        floor = math.floor(exact)
        floors.append(floor)
        remainders.append(exact - floor)

    leftover = total - sum(floors)
    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(range(len(fracs)), key=lambda i: (-remainders[i], -fracs[i], i))
    shares = list(floors)
    for i in order[:leftover]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-s for s in shares]
    return shares
