"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(weight: object) -> Fraction:
    """Convert a supported weight to an exact Fraction.

    Args:
        weight: An int, float, Fraction, or Decimal.

    Returns:
        The weight as an exact Fraction.

    Raises:
        ValueError: If the weight is NaN, infinite, or not a supported number.
    """
    if isinstance(weight, bool):
        # bool is an int subclass; treat True/False as 1/0.
        return Fraction(int(weight))

    if isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError(f"weight must be finite, got {weight!r}")
        return Fraction(weight)

    if isinstance(weight, Decimal):
        if weight.is_nan() or weight.is_infinite():
            raise ValueError(f"weight must be finite, got {weight!r}")
        return Fraction(weight)

    if isinstance(weight, (int, Fraction)):
        return Fraction(weight)

    try:
        return Fraction(weight)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unsupported weight type: {type(weight).__name__}") from exc


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = [_to_fraction(weight) for weight in weights]

    if any(weight < 0 for weight in exact_weights):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    is_negative = total_cents < 0
    amount = abs(total_cents)

    shares = []
    remainders = []
    for weight in exact_weights:
        if weight == 0:
            shares.append(0)
            remainders.append(Fraction(0))
            continue

        exact_share = amount * weight / total_weight
        floor_share = exact_share.numerator // exact_share.denominator
        shares.append(floor_share)
        remainders.append(exact_share - floor_share)

    leftover = amount - sum(shares)

    # Rank candidates by largest remainder, then larger weight, then lower index.
    # Zero-weight parties are excluded so they can never receive a leftover cent.
    candidates = sorted(
        (index for index, weight in enumerate(exact_weights) if weight > 0),
        key=lambda index: (-remainders[index], -exact_weights[index], index),
    )
    for index in candidates[:leftover]:
        shares[index] += 1

    if is_negative:
        return [-share for share in shares]
    return shares
