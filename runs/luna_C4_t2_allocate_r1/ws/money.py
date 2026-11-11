"""Money helpers."""

from decimal import Decimal
from fractions import Fraction


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split cents proportionally using the largest-remainder method."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights: list[Fraction] = []
    for weight in weights:
        if not isinstance(weight, (int, float, Fraction, Decimal)):
            raise ValueError("weights must be numeric")
        try:
            exact_weight = Fraction(weight)
        except (ValueError, OverflowError) as exc:
            raise ValueError("weights must be finite") from exc
        if exact_weight < 0:
            raise ValueError("weights must not be negative")
        exact_weights.append(exact_weight)

    weight_total = sum(exact_weights, Fraction())
    if weight_total == 0:
        raise ValueError("at least one weight must be positive")

    cents = abs(total_cents)
    shares: list[int] = []
    remainders: list[Fraction] = []
    for weight in exact_weights:
        exact_share = Fraction(cents) * weight / weight_total
        floor_share = exact_share.numerator // exact_share.denominator
        shares.append(floor_share)
        remainders.append(exact_share - floor_share)

    remaining = cents - sum(shares)
    priority = sorted(
        range(len(weights)),
        key=lambda index: (remainders[index], exact_weights[index], -index),
        reverse=True,
    )
    for index in priority[:remaining]:
        shares[index] += 1

    if total_cents < 0:
        return [-share for share in shares]
    return shares
