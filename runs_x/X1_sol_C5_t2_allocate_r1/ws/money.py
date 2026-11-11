"""Money helpers."""

from fractions import Fraction


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split cents exactly using largest remainders, then weight and index."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    try:
        exact_weights = [Fraction(weight) for weight in weights]
    except (ValueError, OverflowError) as exc:
        raise ValueError("weights must be finite") from exc
    if any(weight < 0 for weight in exact_weights):
        raise ValueError("weights must not be negative")
    weight_sum = sum(exact_weights)
    if weight_sum == 0:
        raise ValueError("at least one weight must be positive")

    total = abs(total_cents)
    exact_shares = [total * weight / weight_sum for weight in exact_weights]
    shares = [share.numerator // share.denominator for share in exact_shares]
    leftover = total - sum(shares)
    # Excluding zero weights also guarantees they never receive a leftover cent.
    order = sorted(
        (index for index, weight in enumerate(exact_weights) if weight > 0),
        key=lambda index: (
            -(exact_shares[index] - shares[index]),
            -exact_weights[index],
            index,
        ),
    )
    for index in order[:leftover]:
        shares[index] += 1

    return [-share for share in shares] if total_cents < 0 else shares
