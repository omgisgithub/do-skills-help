"""Money helpers."""

from decimal import Decimal
from fractions import Fraction
from typing import Union


def allocate(
    total_cents: int, weights: list[Union[int, float, Fraction, Decimal]]
) -> list[int]:
    """Split cents proportionally using exact largest remainders.

    Ties favor larger weights, then lower indices. Negative totals receive
    the negation of the corresponding positive allocation.

    Args:
        total_cents: The signed number of cents to distribute.
        weights: Nonnegative, finite weights with a positive sum.

    Returns:
        Integer shares in input order that sum to total_cents.

    Raises:
        ValueError: If the total is not an integer (excluding booleans), or
            weights are empty, negative, nonfinite, or all zero.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an integer, not a boolean")
    if not weights:
        raise ValueError("weights must not be empty")

    try:
        exact_weights = [Fraction(weight) for weight in weights]
    except (ValueError, OverflowError) as exc:
        raise ValueError("weights must be finite") from exc
    if any(weight < 0 for weight in exact_weights):
        raise ValueError("weights must be nonnegative")
    weight_sum = sum(exact_weights, Fraction(0))
    if weight_sum == 0:
        raise ValueError("at least one weight must be positive")

    exact_shares = [abs(total_cents) * weight / weight_sum for weight in exact_weights]
    shares = [share.numerator // share.denominator for share in exact_shares]
    ranked_indices = sorted(
        (index for index, weight in enumerate(exact_weights) if weight > 0),
        key=lambda index: (
            -(exact_shares[index] - shares[index]),
            -exact_weights[index],
            index,
        ),
    )
    for index in ranked_indices[: abs(total_cents) - sum(shares)]:
        shares[index] += 1
    return [-share for share in shares] if total_cents < 0 else shares
