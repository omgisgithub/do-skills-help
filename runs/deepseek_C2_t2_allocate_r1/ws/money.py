"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact(weight):
    """Return weight as a Fraction, rejecting floats/Decimals that are NaN or infinite."""
    if isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError("weights must be finite")
        return Fraction(weight)
    if isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(weight)
    return Fraction(weight)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact = [_exact(w) for w in weights]
    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")
    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    shares = [amount * w / total_weight for w in exact]
    floors = [s.numerator // s.denominator for s in shares]
    remainders = [s - f for s, f in zip(shares, floors)]

    leftover = amount - sum(floors)
    order = sorted(
        range(len(exact)),
        key=lambda i: (-remainders[i], -exact[i], i),
    )
    result = list(floors)
    for i in order[:leftover]:
        result[i] += 1

    if total_cents < 0:
        result = [-share for share in result]
    return result
