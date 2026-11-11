"""Money helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal
from fractions import Fraction


def allocate(total_cents: int, weights: Sequence[int | float | Fraction | Decimal]) -> list[int]:
    """Split ``total_cents`` across ``weights`` using the largest remainder method.

    Each party first gets the floor of its exact proportional share. The leftover
    cents go one each to the parties with the largest fractional remainders. Ties
    go to the larger weight, then to the lower index. A negative total is split by
    its absolute value and every share is negated.

    Args:
        total_cents: The amount to split, in cents. Must be an ``int``, not ``bool``.
        weights: Non-negative, finite relative weights. The sequence is not modified.

    Returns:
        One share per weight. The shares sum exactly to ``total_cents``.

    Raises:
        ValueError: If ``total_cents`` is not an int, ``weights`` is empty, any weight
            is negative, NaN, or infinite, or every weight is zero.
    """
    _check_total_cents(total_cents)
    if not weights:
        raise ValueError("weights must not be empty")
    exact_weights = [_to_fraction(weight) for weight in weights]
    if any(weight < 0 for weight in exact_weights):
        raise ValueError("weights must not be negative")
    total_weight = sum(exact_weights)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    shares = _largest_remainder(abs(total_cents), exact_weights, total_weight)
    if total_cents < 0:
        return [-share for share in shares]
    return shares


def _check_total_cents(total_cents: int) -> None:
    """Reject anything that is not a plain int, including ``bool``.

    Args:
        total_cents: The value to check.

    Raises:
        ValueError: If ``total_cents`` is not an int.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError(f"total_cents must be an int, got {type(total_cents).__name__}")


def _to_fraction(weight: int | float | Fraction | Decimal) -> Fraction:
    """Convert a weight to an exact Fraction, rejecting NaN and infinity first.

    Args:
        weight: The weight to convert.

    Returns:
        The exact value of ``weight``.

    Raises:
        ValueError: If ``weight`` is a NaN or infinite float or Decimal.
    """
    # Fraction(nan) and Fraction(inf) raise inconsistent errors, so check explicitly.
    if isinstance(weight, float) and not math.isfinite(weight):
        raise ValueError(f"weights must be finite, got {weight!r}")
    if isinstance(weight, Decimal) and not weight.is_finite():
        raise ValueError(f"weights must be finite, got {weight!r}")
    return Fraction(weight)


def _largest_remainder(amount: int, weights: list[Fraction], total_weight: Fraction) -> list[int]:
    """Apply the largest remainder method to a non-negative amount.

    Args:
        amount: The non-negative number of cents to split.
        weights: Exact, non-negative weights with a positive sum.
        total_weight: The sum of ``weights``.

    Returns:
        Non-negative integer shares that sum to ``amount``.
    """
    exact_shares = [amount * weight / total_weight for weight in weights]
    shares = [math.floor(share) for share in exact_shares]
    leftover = amount - sum(shares)

    # Each fractional remainder is below 1, so a party with zero remainder
    # sorts after every party that can take a leftover cent.
    remainders = [share - floor for share, floor in zip(exact_shares, shares)]
    order = sorted(
        range(len(weights)),
        key=lambda index: (-remainders[index], -weights[index], index),
    )
    for index in order[:leftover]:
        shares[index] += 1
    return shares
