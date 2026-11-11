"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _as_fraction(value):
    """Convert a weight to an exact Fraction, rejecting non-finite values."""
    if isinstance(value, bool):
        return Fraction(int(value), 1)
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("weights must be finite")
        return Fraction(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(value)
    raise ValueError("unsupported weight type: %s" % type(value).__name__)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    raw = list(weights)
    if not raw:
        raise ValueError("weights must not be empty")

    exact = [_as_fraction(w) for w in raw]
    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact, Fraction(0, 1))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    amount = abs(total_cents)
    floors = []
    remainders = []
    for weight in exact:
        share = amount * weight / total_weight
        whole = share.numerator // share.denominator
        floors.append(whole)
        remainders.append(share - whole)

    leftover = amount - sum(floors)
    order = sorted(
        range(len(exact)),
        key=lambda i: (-remainders[i], -exact[i], i),
    )
    for i in order[:leftover]:
        floors[i] += 1

    if total_cents < 0:
        floors = [-share for share in floors]
    return floors
