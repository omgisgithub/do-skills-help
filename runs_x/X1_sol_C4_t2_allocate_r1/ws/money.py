"""Money helpers."""

from decimal import Decimal
from fractions import Fraction
from typing import Union


def allocate(total_cents: int, weights: list[Union[int, float, Fraction, Decimal]]) -> list[int]:
    """Split cents proportionally using exact largest remainders.

    Args:
        total_cents: Signed number of cents to distribute.
        weights: Nonnegative, finite weights with a positive sum.

    Returns:
        Shares in input order, with ties settled by weight then index.

    Raises:
        ValueError: If the total is not an integer, or weights are empty,
            negative, nonfinite, or all zero.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an integer")
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
        raise ValueError("weights must have a positive sum")

    exact_shares = [abs(total_cents) * weight / weight_sum for weight in exact_weights]
    shares = [share.numerator // share.denominator for share in exact_shares]
    ranked_indices = sorted(
        (index for index, weight in enumerate(exact_weights) if weight > 0),
        key=lambda index: (-(exact_shares[index] - shares[index]), -exact_weights[index], index),
    )
    for index in ranked_indices[: abs(total_cents) - sum(shares)]:
        shares[index] += 1
    return [-share for share in shares] if total_cents < 0 else shares
