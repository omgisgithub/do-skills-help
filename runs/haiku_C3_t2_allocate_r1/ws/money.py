"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact(weight):
    """Convert a weight to an exact Fraction, rejecting NaN and infinity."""
    if isinstance(weight, float):
        if math.isnan(weight) or math.isinf(weight):
            raise ValueError("weights must be finite")
        return Fraction(weight)
    if isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(weight)
    if isinstance(weight, (int, Fraction)):
        return Fraction(weight)
    raise TypeError(f"unsupported weight type: {type(weight).__name__}")


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    if len(weights) == 0:
        raise ValueError("weights must not be empty")

    exact = [_exact(w) for w in weights]
    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")
    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("all weights are zero")

    total = abs(total_cents)
    shares = [total * w / total_weight for w in exact]
    result = [math.floor(s) for s in shares]
    leftover = total - sum(result)

    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(
        range(len(exact)),
        key=lambda i: (-(shares[i] - result[i]), -exact[i], i),
    )
    for i in order[:leftover]:
        result[i] += 1

    if total_cents < 0:
        result = [-r for r in result]
    return result
