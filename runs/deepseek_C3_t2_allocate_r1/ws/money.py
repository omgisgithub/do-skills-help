"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _as_fraction(weight):
    """Convert a supported weight to an exact Fraction, rejecting non-finite values."""
    if isinstance(weight, bool):
        return Fraction(int(weight))
    if isinstance(weight, int):
        return Fraction(weight)
    if isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError("weight must be finite")
        return Fraction(weight)
    if isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weight must be finite")
        return Fraction(weight)
    if isinstance(weight, Fraction):
        return weight
    try:
        return Fraction(weight)
    except (TypeError, ValueError, ZeroDivisionError):
        raise ValueError("unsupported weight: {!r}".format(weight))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    weights = list(weights)
    if not weights:
        raise ValueError("weights must not be empty")

    exact = [_as_fraction(weight) for weight in weights]
    if any(weight < 0 for weight in exact):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    sign = -1 if total_cents < 0 else 1
    amount = abs(total_cents)

    shares = []
    remainders = []
    for weight in exact:
        share = amount * weight / total_weight
        whole = share.numerator // share.denominator
        shares.append(whole)
        remainders.append(share - whole)

    leftover = amount - sum(shares)
    order = sorted(
        range(len(weights)),
        key=lambda i: (-remainders[i], -exact[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [sign * share for share in shares]
