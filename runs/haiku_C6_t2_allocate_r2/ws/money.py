"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact_weight(weight):
    """Return weight as an exact Fraction, or raise ValueError if it is unusable."""
    if isinstance(weight, float):
        if math.isnan(weight) or math.isinf(weight):
            raise ValueError("weights must be finite")
        value = Fraction(weight)
    elif isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must be finite")
        value = Fraction(weight)
    elif isinstance(weight, (int, Fraction)):
        value = Fraction(weight)
    else:
        raise ValueError(f"unsupported weight type: {type(weight).__name__}")
    if value < 0:
        raise ValueError("weights must not be negative")
    return value


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    items = list(weights)
    if not items:
        raise ValueError("weights must not be empty")
    exact = [_exact_weight(w) for w in items]
    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("all weights are zero")

    amount = abs(total_cents)
    shares = []
    remainders = []
    for w in exact:
        exact_share = amount * w / total_weight
        floor = exact_share.numerator // exact_share.denominator
        shares.append(floor)
        remainders.append(exact_share - floor)

    leftover = amount - sum(shares)
    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(range(len(exact)), key=lambda i: (-remainders[i], -exact[i], i))
    for i in order[:leftover]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-s for s in shares]
    return shares
