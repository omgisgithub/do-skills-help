"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _as_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting non-finite values."""
    if isinstance(weight, Fraction):
        return weight
    if isinstance(weight, bool):
        return Fraction(int(weight))
    if isinstance(weight, int):
        return Fraction(weight)
    if isinstance(weight, float):
        if math.isnan(weight) or math.isinf(weight):
            raise ValueError("weight must be finite")
        # Exact binary value of the float; do not round it.
        return Fraction(weight)
    if isinstance(weight, Decimal):
        if weight.is_nan() or weight.is_infinite():
            raise ValueError("weight must be finite")
        return Fraction(weight)
    raise ValueError("unsupported weight type: %r" % (type(weight).__name__,))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    try:
        weight_list = list(weights)
    except TypeError:
        raise ValueError("weights must be an iterable of numbers")

    if not weight_list:
        raise ValueError("weights must not be empty")

    exact_weights = [_as_fraction(w) for w in weight_list]
    if any(w < 0 for w in exact_weights):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("weights must not all be zero")

    negative = total_cents < 0
    amount = abs(total_cents)

    shares = []
    remainders = []
    allocated = 0
    for weight in exact_weights:
        if weight == 0:
            shares.append(0)
            remainders.append(Fraction(0))
            continue
        exact_share = Fraction(amount) * weight / total_weight
        base = exact_share.numerator // exact_share.denominator
        shares.append(base)
        remainders.append(exact_share - base)
        allocated += base

    leftover = amount - allocated
    if leftover:
        # Largest remainder first; ties to the larger weight, then lower index.
        order = sorted(
            (i for i, weight in enumerate(exact_weights) if weight != 0),
            key=lambda i: (-remainders[i], -exact_weights[i], i),
        )
        for i in order[:leftover]:
            shares[i] += 1

    if negative:
        shares = [-share for share in shares]
    return shares
