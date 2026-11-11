"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _as_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting non-finite values."""
    if isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weight must be finite")
        return Fraction(weight)
    if isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError("weight must be finite")
        return Fraction(weight)
    if isinstance(weight, (int, Fraction)):
        return Fraction(weight)
    try:
        return Fraction(weight)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("unsupported weight: {!r}".format(weight)) from exc


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    exact_weights = [_as_fraction(weight) for weight in weights]

    if not exact_weights:
        raise ValueError("weights must not be empty")
    for value in exact_weights:
        if value < 0:
            raise ValueError("weights must not be negative")

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    sign = -1 if total_cents < 0 else 1
    amount = abs(total_cents)

    shares = []
    remainders = []
    for value in exact_weights:
        exact_share = amount * value / total_weight
        whole = exact_share.numerator // exact_share.denominator
        shares.append(whole)
        remainders.append(exact_share - whole)

    leftover = amount - sum(shares)
    order = sorted(
        range(len(exact_weights)),
        key=lambda i: (-remainders[i], -exact_weights[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    if sign < 0:
        shares = [-share for share in shares]

    return shares
