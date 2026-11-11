"""Money helpers."""

from fractions import Fraction


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split cents proportionally using exact largest-remainder allocation."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = []
    for weight in weights:
        try:
            exact_weight = Fraction(weight)
        except (ValueError, OverflowError) as exc:
            raise ValueError("weights must be finite") from exc
        if exact_weight < 0:
            raise ValueError("weights must be nonnegative")
        exact_weights.append(exact_weight)

    weight_sum = sum(exact_weights, Fraction(0))
    if not weight_sum:
        raise ValueError("at least one weight must be positive")

    magnitude = abs(total_cents)
    exact_shares = [magnitude * weight / weight_sum for weight in exact_weights]
    shares = [share.numerator // share.denominator for share in exact_shares]
    remaining = magnitude - sum(shares)
    order = sorted(
        (index for index, weight in enumerate(exact_weights) if weight > 0),
        key=lambda index: (
            -(exact_shares[index] - shares[index]),
            -exact_weights[index],
            index,
        ),
    )
    for index in order[:remaining]:
        shares[index] += 1

    return [-share for share in shares] if total_cents < 0 else shares
