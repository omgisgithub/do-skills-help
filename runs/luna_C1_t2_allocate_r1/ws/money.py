"""Money helpers."""

from decimal import Decimal
from fractions import Fraction
import math


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = []
    for weight in weights:
        if isinstance(weight, bool):
            # bool is an int subclass, but is not a meaningful allocation weight.
            exact = Fraction(int(weight))
        elif isinstance(weight, float):
            if not math.isfinite(weight):
                raise ValueError("weights must be finite")
            exact = Fraction(weight)
        elif isinstance(weight, Decimal):
            if not weight.is_finite():
                raise ValueError("weights must be finite")
            exact = Fraction(weight)
        else:
            try:
                exact = Fraction(weight)
            except (TypeError, ValueError, ZeroDivisionError, OverflowError):
                raise ValueError("invalid weight") from None
        if exact < 0:
            raise ValueError("weights must be nonnegative")
        exact_weights.append(exact)

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    amount = abs(total_cents)
    shares = []
    remainders = []
    for weight in exact_weights:
        exact_share = Fraction(amount) * weight / total_weight
        floor_share = exact_share.numerator // exact_share.denominator
        shares.append(floor_share)
        remainders.append(exact_share - floor_share)

    remaining = amount - sum(shares)
    order = sorted(
        range(len(exact_weights)),
        key=lambda i: (-remainders[i], -exact_weights[i], i),
    )
    for i in order[:remaining]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-share for share in shares]
    return shares
