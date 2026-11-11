"""Money helpers."""

from decimal import Decimal
from fractions import Fraction


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = []
    for weight in weights:
        if not isinstance(weight, (int, float, Fraction, Decimal)):
            raise ValueError("weights must be numeric")
        try:
            exact_weight = Fraction(weight)
        except (ValueError, OverflowError) as exc:
            raise ValueError("weights must be finite") from exc
        if exact_weight < 0:
            raise ValueError("weights must be nonnegative")
        exact_weights.append(exact_weight)

    weight_sum = sum(exact_weights)
    if weight_sum == 0:
        raise ValueError("at least one weight must be positive")

    exact_shares = [abs(total_cents) * weight / weight_sum
                    for weight in exact_weights]
    shares = [share.numerator // share.denominator for share in exact_shares]
    remaining = abs(total_cents) - sum(shares)
    order = sorted(
        (index for index, weight in enumerate(exact_weights) if weight > 0),
        key=lambda index: (-(exact_shares[index] - shares[index]),
                           -exact_weights[index], index),
    )
    for index in order[:remaining]:
        shares[index] += 1

    if total_cents < 0:
        return [-share for share in shares]
    return shares
