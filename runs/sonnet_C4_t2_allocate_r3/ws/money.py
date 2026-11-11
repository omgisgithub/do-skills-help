"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting NaN, infinity and negatives."""
    if isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError(f"weight must be finite, got {weight!r}")
    elif isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError(f"weight must be finite, got {weight!r}")
    elif not isinstance(weight, (int, Fraction)):
        raise ValueError(f"unsupported weight type: {type(weight).__name__}")
    fraction = Fraction(weight)
    if fraction < 0:
        raise ValueError(f"weight must not be negative, got {weight!r}")
    return fraction


def allocate(total_cents, weights):
    """Split total_cents across weights using the largest remainder method.

    Args:
        total_cents: Amount to split, in cents. Must be an ``int`` (not ``bool``).
        weights: Non-negative int, float, Fraction or Decimal weights; not modified.

    Returns:
        A list of ints, one per weight, summing exactly to ``total_cents``.

    Raises:
        ValueError: On invalid ``total_cents`` or ``weights``.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError(f"total_cents must be an int, got {total_cents!r}")
    if len(weights) == 0:
        raise ValueError("weights must not be empty")
    fractions = [_to_fraction(weight) for weight in weights]
    weight_sum = sum(fractions, Fraction(0))
    if weight_sum == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    exact = [amount * fraction / weight_sum for fraction in fractions]
    shares = [math.floor(value) for value in exact]
    leftover = amount - sum(shares)

    order = sorted(
        range(len(fractions)),
        key=lambda i: (-(exact[i] - shares[i]), -fractions[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [-share for share in shares] if total_cents < 0 else shares
