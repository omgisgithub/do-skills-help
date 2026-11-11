"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(value):
    """Convert a weight to an exact Fraction, rejecting non-finite values."""
    if isinstance(value, bool):
        return Fraction(int(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("weights must be finite")
        return Fraction(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(value)
    if isinstance(value, (int, Fraction)):
        return Fraction(value)
    try:
        return Fraction(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("weight must be a number") from exc


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    weights = list(weights)
    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = [_to_fraction(weight) for weight in weights]
    if any(weight < 0 for weight in exact_weights):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("weights must not all be zero")

    sign = -1 if total_cents < 0 else 1
    amount = abs(total_cents)

    shares = []
    remainders = []
    for weight in exact_weights:
        exact_share = amount * weight / total_weight
        share = exact_share.numerator // exact_share.denominator
        shares.append(share)
        remainders.append(exact_share - share)

    leftover = amount - sum(shares)
    order = sorted(
        range(len(weights)),
        key=lambda i: (-remainders[i], -exact_weights[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    if sign < 0:
        shares = [-share for share in shares]
    return shares
