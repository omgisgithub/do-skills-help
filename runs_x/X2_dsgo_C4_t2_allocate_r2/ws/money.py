"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _as_fraction(value: object) -> Fraction:
    """Convert a weight to an exact Fraction, rejecting non-finite values.

    Args:
        value: A weight that is an int, float, Fraction, or Decimal.

    Returns:
        The weight as an exact Fraction.

    Raises:
        TypeError: If the weight is not a supported numeric type.
        ValueError: If the weight is NaN or infinite.
    """
    if isinstance(value, bool):
        return Fraction(int(value))
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("weights must be finite")
        return Fraction(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(value)
    if isinstance(value, Fraction):
        return value
    raise TypeError(f"unsupported weight type: {type(value).__name__}")


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split total_cents across weights using largest-remainder rounding.

    Each share is proportional to its weight. Every share is an integer, and
    the shares sum exactly to ``total_cents``. Ties in fractional remainder go
    to the larger weight, then to the lower index. Negative totals are
    allocated on their absolute value and then negated.

    Args:
        total_cents: The total amount to split, in cents.
        weights: A list of non-negative int, float, Fraction, or Decimal
            weights. The list is not modified.

    Returns:
        A list of integer shares, one per weight, summing to ``total_cents``.

    Raises:
        ValueError: If ``total_cents`` is not an int (booleans are rejected),
            ``weights`` is empty, a weight is negative or non-finite, or all
            weights are zero.
        TypeError: If a weight has an unsupported type.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    exact_weights = []
    for weight in weights:
        exact = _as_fraction(weight)
        if exact < 0:
            raise ValueError("weights must not be negative")
        exact_weights.append(exact)

    if not exact_weights:
        raise ValueError("weights must not be empty")

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    amount = abs(total_cents)
    shares = []
    remainders = []
    for weight in exact_weights:
        exact_share = Fraction(amount) * weight / total_weight
        whole = exact_share.numerator // exact_share.denominator
        shares.append(whole)
        remainders.append(exact_share - whole)

    leftover = amount - sum(shares)
    order = sorted(
        range(len(exact_weights)),
        key=lambda i: (-remainders[i], -exact_weights[i], i),
    )
    for index in order[:leftover]:
        shares[index] += 1

    if total_cents < 0:
        shares = [-share for share in shares]

    return shares
