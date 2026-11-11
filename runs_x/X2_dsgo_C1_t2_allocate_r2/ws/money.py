"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _as_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting NaN and infinities."""
    if isinstance(weight, Fraction):
        return weight
    if isinstance(weight, Decimal):
        if weight.is_nan() or weight.is_infinite():
            raise ValueError("weight must be finite")
        return Fraction(weight)
    if isinstance(weight, float):
        if math.isnan(weight) or math.isinf(weight):
            raise ValueError("weight must be finite")
        return Fraction(weight)
    if isinstance(weight, int):
        return Fraction(weight)
    raise ValueError("unsupported weight type: %r" % (type(weight).__name__,))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")

    if not weights:
        raise ValueError("weights must not be empty")

    exact = [_as_fraction(w) for w in weights]

    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    amount = abs(total_cents)
    shares = []
    remainders = []
    for w in exact:
        share = Fraction(amount) * w / total_weight
        floor = share.numerator // share.denominator
        shares.append(floor)
        remainders.append(share - floor)

    leftover = amount - sum(shares)
    # Largest remainder first, then larger weight, then lower index.
    order = sorted(range(len(exact)), key=lambda i: (-remainders[i], -exact[i], i))
    for i in order[:leftover]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-s for s in shares]

    return shares
