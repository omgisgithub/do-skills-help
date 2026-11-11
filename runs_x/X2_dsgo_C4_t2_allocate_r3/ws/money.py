"""Money helpers."""

from __future__ import annotations

import math
from decimal import Decimal
from fractions import Fraction
from typing import Sequence, Union

Weight = Union[int, float, Fraction, Decimal]


def _to_fraction(weight: object) -> Fraction:
    """Convert a single weight to an exact fraction.

    Args:
        weight: The raw weight supplied by the caller.

    Returns:
        The weight as an exact ``Fraction``.

    Raises:
        ValueError: If the weight is not a supported numeric type, is not
            finite, or is negative.
    """
    if isinstance(weight, bool):
        weight = int(weight)
    elif isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError("weights must be finite numbers")
    elif isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must be finite numbers")
    elif not isinstance(weight, (int, Fraction)):
        raise ValueError(f"unsupported weight type: {type(weight).__name__}")

    exact = Fraction(weight)
    if exact < 0:
        raise ValueError(f"weights must be non-negative, got {weight!r}")
    return exact


def allocate(total_cents: int, weights: Sequence[Weight]) -> list[int]:
    """Split ``total_cents`` across ``weights`` using largest remainder.

    Every share is proportional to its weight, and the returned shares sum to
    exactly ``total_cents``. Arithmetic is exact, so float inputs never decide
    a rounding tie. Ties in the fractional remainder go to the larger weight,
    then to the lower index.

    Args:
        total_cents: Total amount to split, in integer cents. May be negative.
        weights: Relative weights, one per party. Each must be finite and
            non-negative.

    Returns:
        One integer share per weight, in the same order, summing to
        ``total_cents``.

    Raises:
        ValueError: If ``weights`` is empty, any weight is negative, all
            weights are zero, any weight is NaN or infinite, or
            ``total_cents`` is not an ``int`` (``bool`` excluded).
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = [_to_fraction(weight) for weight in weights]
    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    magnitude = abs(total_cents)
    shares = [weight * magnitude / total_weight for weight in exact_weights]
    floors = [share.numerator // share.denominator for share in shares]
    remainders = [share - floor for share, floor in zip(shares, floors)]

    leftover = magnitude - sum(floors)
    # Rank by largest remainder first, then larger weight, then lower index.
    order = sorted(
        range(len(exact_weights)),
        key=lambda index: (remainders[index], exact_weights[index], -index),
        reverse=True,
    )
    for index in order[:leftover]:
        floors[index] += 1

    if total_cents < 0:
        return [-share for share in floors]
    return floors
