"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _as_fraction(value):
    """Convert a supported weight to an exact Fraction, rejecting NaN/inf."""
    if isinstance(value, bool):
        return Fraction(int(value))
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Fraction):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("weights must be finite")
        return Fraction(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(value)
    try:
        return Fraction(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("unsupported weight type: {!r}".format(type(value)))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    # Copy so the caller's list is never modified.
    weights = list(weights)
    if not weights:
        raise ValueError("weights must not be empty")

    exact = [_as_fraction(weight) for weight in weights]
    if any(weight < 0 for weight in exact):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    negative = total_cents < 0
    amount = abs(total_cents)

    floors = []
    remainders = []
    for weight in exact:
        if weight == 0:
            floors.append(0)
            remainders.append(Fraction(0))
            continue
        share = Fraction(amount) * weight / total_weight
        whole = share.numerator // share.denominator
        floors.append(whole)
        remainders.append(share - whole)

    leftover = amount - sum(floors)

    # Largest remainder first; ties go to the larger weight, then lower index.
    order = sorted(
        range(len(exact)),
        key=lambda i: (-remainders[i], -exact[i], i),
    )
    for index in order[:leftover]:
        floors[index] += 1

    if negative:
        return [-share for share in floors]
    return floors
