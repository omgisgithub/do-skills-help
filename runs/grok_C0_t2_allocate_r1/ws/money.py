"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents is not an int")
    if len(weights) == 0:
        raise ValueError("weights is empty")

    exact_weights = []
    for weight in weights:
        exact = _weight_to_fraction(weight)
        if exact < 0:
            raise ValueError("weight is negative")
        exact_weights.append(exact)

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("all weights are zero")

    amount = abs(total_cents)
    shares = [Fraction(amount) * exact / total_weight for exact in exact_weights]
    # Non-negative fractions: numerator // denominator is the floor.
    base = [share.numerator // share.denominator for share in shares]
    remainders = [share - given for share, given in zip(shares, base)]

    leftover = amount - sum(base)
    # Largest remainder, then larger weight, then lower index.
    recipients = sorted(
        range(len(exact_weights)),
        key=lambda i: (-remainders[i], -exact_weights[i], i),
    )
    for index in recipients[:leftover]:
        base[index] += 1

    if total_cents < 0:
        return [-share for share in base]
    return base


def _weight_to_fraction(weight):
    """Convert an allowed weight to an exact Fraction.

    Floats use Fraction(weight), which keeps the exact binary value so a
    later tie is not decided by binary floating-point rounding.
    """
    if isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError("weight is NaN or infinite")
        return Fraction(weight)
    if isinstance(weight, Decimal):
        if weight.is_nan() or weight.is_infinite():
            raise ValueError("weight is NaN or infinite")
        return Fraction(weight)
    if isinstance(weight, Fraction):
        return weight
    # bool is a subclass of int; weights may be ints, so bool is 0 or 1.
    if isinstance(weight, int):
        return Fraction(weight)
    raise ValueError("unsupported weight type")
