"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact_weight(weight):
    """Convert a weight to an exact Fraction, rejecting NaN and infinity."""
    if isinstance(weight, (int, Fraction)):
        return Fraction(weight)
    if isinstance(weight, float):
        if math.isnan(weight) or math.isinf(weight):
            raise ValueError("weights must be finite")
        return Fraction(weight)
    if isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(weight)
    raise TypeError("unsupported weight type: %s" % type(weight).__name__)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    exact = [_exact_weight(w) for w in weights]
    if not exact:
        raise ValueError("weights must not be empty")
    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")
    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    cents = abs(total_cents)
    shares = []
    for w in exact:
        exact_share = cents * w / total_weight
        floor = exact_share.numerator // exact_share.denominator
        shares.append([floor, exact_share - floor])

    leftover = cents - sum(share[0] for share in shares)
    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(range(len(exact)), key=lambda i: (-shares[i][1], -exact[i], i))
    for i in order[:leftover]:
        shares[i][0] += 1

    result = [share[0] for share in shares]
    if total_cents < 0:
        result = [-s for s in result]
    return result
