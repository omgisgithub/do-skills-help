"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split ``total_cents`` across ``weights`` using the largest remainder method.

    Shares are computed with exact arithmetic, so float rounding never decides a
    tie. Negative totals are allocated by absolute value and then negated.

    Args:
        total_cents: The amount to split, in cents.
        weights: Non-negative int, float, Fraction or Decimal weights. Not modified.

    Returns:
        One int per weight, in the same order, summing exactly to ``total_cents``.

    Raises:
        ValueError: If ``total_cents`` is not an int, ``weights`` is empty, any weight
            is negative, NaN or infinite, or all weights are zero.
        TypeError: If a weight is not a supported numeric type.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError(f"total_cents must be an int, got {type(total_cents).__name__}")
    exact_weights = _exact_weights(weights)
    magnitude = _largest_remainder(abs(total_cents), exact_weights)
    if total_cents < 0:
        return [-share for share in magnitude]
    return magnitude


def _to_fraction(weight: object) -> Fraction:
    """Convert a weight to an exact, non-negative Fraction."""
    if not isinstance(weight, (int, float, Fraction, Decimal)):
        raise TypeError(f"unsupported weight type: {type(weight).__name__}")
    if isinstance(weight, Decimal) and not weight.is_finite():
        raise ValueError(f"weight must be finite, got {weight!r}")
    if isinstance(weight, float) and not math.isfinite(weight):
        raise ValueError(f"weight must be finite, got {weight!r}")
    exact = Fraction(weight)
    if exact < 0:
        raise ValueError(f"weight must not be negative, got {weight!r}")
    return exact


def _exact_weights(weights: list) -> list[Fraction]:
    """Convert all weights to Fractions, rejecting empty or all-zero input."""
    exact_weights = [_to_fraction(weight) for weight in weights]
    if not exact_weights:
        raise ValueError("weights must not be empty")
    if not any(weight > 0 for weight in exact_weights):
        raise ValueError("at least one weight must be non-zero")
    return exact_weights


def _largest_remainder(total: int, weights: list[Fraction]) -> list[int]:
    """Split a non-negative total so the shares sum exactly to it.

    Leftover cents go to the largest fractional remainders. Ties go to the larger
    weight, then to the lower index.
    """
    weight_sum = sum(weights)
    shares = [total * weight / weight_sum for weight in weights]
    floors = [share.numerator // share.denominator for share in shares]
    leftover = total - sum(floors)
    remainders = [share - floor for share, floor in zip(shares, floors)]
    ranked = sorted(range(len(weights)), key=lambda i: (-remainders[i], -weights[i], i))
    result = list(floors)
    for index in ranked[:leftover]:
        result[index] += 1
    return result
