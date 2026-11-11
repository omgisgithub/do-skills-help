"""Money helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal
from fractions import Fraction

_WEIGHT_TYPES = (int, float, Fraction, Decimal)


def allocate(total_cents: int, weights: Sequence[int | float | Fraction | Decimal]) -> list[int]:
    """Split total_cents across weights using the largest remainder method.

    Each share is proportional to its weight, computed with exact arithmetic so
    float rounding never decides a tie. Leftover cents go to the largest
    fractional remainders; ties go to the larger weight, then to the lower index.
    Negative amounts are split by magnitude and every share is negated.

    Args:
        total_cents: The amount to split. Must be an int (bool is rejected).
        weights: Non-negative, finite weights, at least one of them non-zero.

    Returns:
        A new list with one share per weight that sums to ``total_cents``.

    Raises:
        ValueError: If ``total_cents`` is not an int, ``weights`` is empty, any weight
            is negative, NaN or infinite, or all weights are zero.
        TypeError: If a weight is not an int, float, Fraction or Decimal.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError(f"total_cents must be an int, got {type(total_cents).__name__}")
    exact_weights = _exact_weights(weights)
    shares = _largest_remainder(abs(total_cents), exact_weights)
    if total_cents < 0:
        return [-share for share in shares]
    return shares


def _exact_weights(weights: Sequence[int | float | Fraction | Decimal]) -> list[Fraction]:
    """Convert weights to exact Fractions and validate them.

    Args:
        weights: The raw weights as passed by the caller. Not modified.

    Returns:
        A new list of Fractions, in the same order as ``weights``.

    Raises:
        ValueError: If ``weights`` is empty, a weight is non-finite or negative,
            or all weights are zero.
        TypeError: If a weight has an unsupported type.
    """
    if len(weights) == 0:
        raise ValueError("weights must not be empty")
    exact_weights = [_to_exact_weight(weight) for weight in weights]
    if any(weight < 0 for weight in exact_weights):
        raise ValueError("weights must not be negative")
    if not any(exact_weights):
        raise ValueError("at least one weight must be non-zero")
    return exact_weights


def _to_exact_weight(weight: int | float | Fraction | Decimal) -> Fraction:
    """Convert one weight to a Fraction, rejecting unsupported and non-finite values.

    Args:
        weight: A single raw weight.

    Returns:
        The weight as an exact Fraction.

    Raises:
        TypeError: If ``weight`` is not an int, float, Fraction or Decimal.
        ValueError: If ``weight`` is NaN or infinite.
    """
    if not isinstance(weight, _WEIGHT_TYPES):
        raise TypeError(
            f"weight must be int, float, Fraction or Decimal, got {type(weight).__name__}"
        )
    if isinstance(weight, float) and not math.isfinite(weight):
        raise ValueError(f"weight must be finite, got {weight!r}")
    if isinstance(weight, Decimal) and not weight.is_finite():
        raise ValueError(f"weight must be finite, got {weight!r}")
    return Fraction(weight)


def _largest_remainder(total: int, weights: list[Fraction]) -> list[int]:
    """Distribute a non-negative total by floor shares plus leftover cents.

    Args:
        total: The non-negative amount to distribute.
        weights: Validated exact weights with a positive sum.

    Returns:
        One non-negative share per weight that sums to ``total``.
    """
    total_weight = sum(weights)
    exact_shares = [total * weight / total_weight for weight in weights]
    shares = [share.numerator // share.denominator for share in exact_shares]
    leftover = total - sum(shares)
    # Leftover is always smaller than the number of parties with a positive remainder,
    # so a zero-weight party (remainder 0) is never selected here.
    order = sorted(
        range(len(weights)),
        key=lambda index: (-(exact_shares[index] - shares[index]), -weights[index], index),
    )
    for index in order[:leftover]:
        shares[index] += 1
    return shares
