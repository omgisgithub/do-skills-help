"""Money helpers."""

import decimal
import fractions
import math


def _as_fraction(value):
    """Convert a weight to an exact Fraction, rejecting invalid values."""
    if isinstance(value, fractions.Fraction):
        return value
    if isinstance(value, decimal.Decimal):
        if not value.is_finite():
            raise ValueError("weight must be finite")
        return fractions.Fraction(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("weight must be finite")
        return fractions.Fraction(value)
    if isinstance(value, int):
        return fractions.Fraction(value)
    raise ValueError("unsupported weight type: {!r}".format(type(value).__name__))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    raw_weights = list(weights)
    if not raw_weights:
        raise ValueError("weights must not be empty")

    exact_weights = []
    for weight in raw_weights:
        exact = _as_fraction(weight)
        if exact < 0:
            raise ValueError("weights must not be negative")
        exact_weights.append(exact)

    negative = total_cents < 0
    amount = abs(total_cents)

    total_weight = sum(exact_weights, fractions.Fraction(0))
    if total_weight == 0:
        raise ValueError("weights must not all be zero")

    shares = []
    remainders = []
    allocated = 0
    for weight in exact_weights:
        exact_share = fractions.Fraction(amount) * weight / total_weight
        floor_share = exact_share.numerator // exact_share.denominator
        shares.append(floor_share)
        remainders.append(exact_share - floor_share)
        allocated += floor_share

    leftover = amount - allocated
    order = sorted(
        range(len(exact_weights)),
        key=lambda i: (-remainders[i], -exact_weights[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    if negative:
        shares = [-share for share in shares]

    return shares
