"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact_weight(weight):
    """Convert a weight to an exact non-negative Fraction."""
    if isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError("weights must be finite")
        value = Fraction(weight)
    elif isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must be finite")
        value = Fraction(weight)
    elif isinstance(weight, (int, Fraction)):
        value = Fraction(weight)
    else:
        raise TypeError("unsupported weight type: %s" % type(weight).__name__)
    if value < 0:
        raise ValueError("weights must not be negative")
    return value


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split total_cents across weights using largest remainder. See TASK.md."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    if len(weights) == 0:
        raise ValueError("weights must not be empty")

    values = [_exact_weight(weight) for weight in weights]
    total_weight = sum(values)
    if total_weight == 0:
        raise ValueError("all weights are zero")

    amount = abs(total_cents)
    exact_shares = [amount * value / total_weight for value in values]
    shares = [int(share) for share in exact_shares]
    leftover = amount - sum(shares)

    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(
        range(len(values)),
        key=lambda i: (-(exact_shares[i] - shares[i]), -values[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-share for share in shares]
    return shares
