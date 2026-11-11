"""Money helpers."""

from decimal import Decimal
from fractions import Fraction
import math


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = []
    for weight in weights:
        if isinstance(weight, float) and not math.isfinite(weight):
            raise ValueError("weights must be finite")
        if isinstance(weight, Decimal) and not weight.is_finite():
            raise ValueError("weights must be finite")
        try:
            exact = Fraction(weight)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("weights must be finite numbers") from exc
        if exact < 0:
            raise ValueError("weights must be non-negative")
        exact_weights.append(exact)

    weight_sum = sum(exact_weights)
    if not weight_sum:
        raise ValueError("at least one weight must be positive")

    amount = abs(total_cents)
    shares = [Fraction(amount) * weight / weight_sum for weight in exact_weights]
    result = [share.numerator // share.denominator for share in shares]
    remaining = amount - sum(result)
    order = sorted(
        range(len(weights)),
        key=lambda i: (-(shares[i] - result[i]), -exact_weights[i], i),
    )
    for i in order[:remaining]:
        result[i] += 1

    return result if total_cents >= 0 else [-share for share in result]
