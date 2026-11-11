"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _as_fraction(value):
    """Return *value* as an exact Fraction, rejecting non-finite numbers."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("weights must be finite")
        return Fraction(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(value)
    if isinstance(value, int):
        return Fraction(value)
    try:
        result = Fraction(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("weight must be a real number") from exc
    return result


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")

    values = list(weights)
    if not values:
        raise ValueError("weights must not be empty")

    exact_weights = [_as_fraction(weight) for weight in values]
    if any(weight < 0 for weight in exact_weights):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    shares = []
    remainders = []
    for weight in exact_weights:
        exact_share = Fraction(amount) * weight / total_weight
        share = exact_share.numerator // exact_share.denominator
        shares.append(share)
        remainders.append(exact_share - share)

    leftover = amount - sum(shares)
    order = sorted(
        range(len(values)),
        key=lambda index: (-remainders[index], -exact_weights[index], index),
    )
    for index in order[:leftover]:
        shares[index] += 1

    if total_cents < 0:
        shares = [-share for share in shares]

    return shares
