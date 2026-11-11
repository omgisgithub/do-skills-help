"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(weight):
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
    raise TypeError("unsupported weight type: %s" % type(weight).__name__)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    weights = list(weights)  # copy; never modify the caller's list
    if not weights:
        raise ValueError("weights must not be empty")

    exact = [_to_fraction(w) for w in weights]
    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    amount = abs(total_cents)

    # Largest remainder method: floor each exact share first.
    shares = [amount * w / total_weight for w in exact]
    result = [int(s) for s in shares]  # shares are non-negative, so int() floors
    leftover = amount - sum(result)

    # Hand out leftover cents by largest fractional remainder. Ties go to the
    # larger weight, then to the lower index. Zero-weight parties never win.
    order = sorted(
        (i for i in range(len(weights)) if exact[i] > 0),
        key=lambda i: (-(shares[i] - result[i]), -exact[i], i),
    )
    for i in order[:leftover]:
        result[i] += 1

    if total_cents < 0:
        result = [-r for r in result]
    return result
