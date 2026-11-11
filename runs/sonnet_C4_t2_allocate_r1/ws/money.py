"""Money helpers."""

from decimal import Decimal
from fractions import Fraction


def _to_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting NaN and infinities."""
    if isinstance(weight, (float, Decimal)) and not weight == weight:
        raise ValueError("weights must not be NaN")
    try:
        return Fraction(weight)
    except OverflowError as exc:
        raise ValueError("weights must be finite") from exc


def allocate(total_cents, weights):
    """Split total_cents across weights using the largest remainder method.

    Args:
        total_cents: Amount to split, in cents. Must be an int (not a bool).
        weights: Non-negative int, float, Fraction or Decimal weights.

    Returns:
        A list of ints, one per weight, summing exactly to total_cents.

    Raises:
        ValueError: If the inputs are invalid.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if len(weights) == 0:
        raise ValueError("weights must not be empty")
    fractions = [_to_fraction(w) for w in weights]
    if any(w < 0 for w in fractions):
        raise ValueError("weights must not be negative")
    weight_sum = sum(fractions)
    if weight_sum == 0:
        raise ValueError("at least one weight must be non-zero")

    amount = abs(total_cents)
    exact = [amount * w / weight_sum for w in fractions]
    shares = [int(x) for x in exact]  # floor: exact shares are non-negative
    leftover = amount - sum(shares)

    order = sorted(
        range(len(fractions)),
        key=lambda i: (-(exact[i] - shares[i]), -fractions[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [-s for s in shares] if total_cents < 0 else shares
