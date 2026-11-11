"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact_weight(weight):
    """Convert a weight to an exact Fraction, rejecting NaN and infinity."""
    if isinstance(weight, float) and not math.isfinite(weight):
        raise ValueError(f"weight must be finite, got {weight!r}")
    if isinstance(weight, Decimal) and not weight.is_finite():
        raise ValueError(f"weight must be finite, got {weight!r}")
    if not isinstance(weight, (int, float, Fraction, Decimal)):
        raise TypeError(f"unsupported weight type: {type(weight).__name__}")
    return Fraction(weight)


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError(f"total_cents must be an int, got {total_cents!r}")
    if not weights:
        raise ValueError("weights must not be empty")

    exact = [_exact_weight(w) for w in weights]
    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")
    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    amount = abs(total_cents)
    shares = [amount * w / total_weight for w in exact]
    floors = [math.floor(s) for s in shares]
    leftover = amount - sum(floors)

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
