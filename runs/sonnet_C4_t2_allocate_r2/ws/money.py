"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting NaN, infinity and negatives."""
    if isinstance(weight, float) and not math.isfinite(weight):
        raise ValueError(f"weight must be finite: {weight!r}")
    if isinstance(weight, Decimal) and not weight.is_finite():
        raise ValueError(f"weight must be finite: {weight!r}")
    try:
        fraction = Fraction(weight)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"invalid weight: {weight!r}") from exc
    if fraction < 0:
        raise ValueError(f"weight must not be negative: {weight!r}")
    return fraction


def allocate(total_cents, weights):
    """Split total_cents across weights using the largest remainder method.

    Ties in remainder go to the larger weight, then to the lower index.
    Negative totals are allocated by magnitude and the shares negated.

    Raises:
        ValueError: On invalid total_cents or weights.
    """
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError(f"total_cents must be an int: {total_cents!r}")
    fractions = [_to_fraction(weight) for weight in weights]
    if not fractions:
        raise ValueError("weights must not be empty")
    weight_sum = sum(fractions)
    if weight_sum == 0:
        raise ValueError("at least one weight must be positive")

    magnitude = abs(total_cents)
    exact = [magnitude * weight / weight_sum for weight in fractions]
    shares = [math.floor(share) for share in exact]
    remainders = [share - floor for share, floor in zip(exact, shares)]
    leftover = magnitude - sum(shares)

    order = sorted(
        range(len(fractions)),
        key=lambda i: (-remainders[i], -fractions[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [-share for share in shares] if total_cents < 0 else shares
