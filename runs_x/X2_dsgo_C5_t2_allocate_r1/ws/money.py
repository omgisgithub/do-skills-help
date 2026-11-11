"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _as_fraction(value):
    """Convert a weight to an exact Fraction, rejecting non-finite values."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        return Fraction(int(value))
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("weights must be finite")
        return Fraction(value)
    if isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            raise ValueError("weights must be finite")
        return Fraction(value)
    try:
        return Fraction(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("weights must be numbers") from exc


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = [_as_fraction(weight) for weight in weights]

    if any(weight < 0 for weight in exact_weights):
        raise ValueError("weights must not be negative")
    if all(weight == 0 for weight in exact_weights):
        raise ValueError("weights must not all be zero")

    sign = -1 if total_cents < 0 else 1
    amount = abs(total_cents)
    weight_sum = sum(exact_weights)

    shares = []
    remainders = []
    for weight in exact_weights:
        share = Fraction(amount) * weight / weight_sum
        whole = share.numerator // share.denominator
        shares.append(whole)
        remainders.append(share - whole)

    leftover = amount - sum(shares)

    # Largest remainder; ties go to the larger weight, then the lower index.
    order = sorted(
        range(len(exact_weights)),
        key=lambda i: (-remainders[i], -exact_weights[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    if sign == -1:
        shares = [-share for share in shares]
    return shares
