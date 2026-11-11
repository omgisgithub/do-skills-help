"""Money helpers."""

from fractions import Fraction


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = []
    for weight in weights:
        try:
            exact_weight = Fraction(weight)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("weights must be finite numbers") from exc
        if exact_weight < 0:
            raise ValueError("weights must not be negative")
        exact_weights.append(exact_weight)

    weight_sum = sum(exact_weights, Fraction(0))
    if not weight_sum:
        raise ValueError("at least one weight must be positive")

    amount = abs(total_cents)
    exact_shares = [amount * weight / weight_sum for weight in exact_weights]
    shares = [share.numerator // share.denominator for share in exact_shares]
    remaining = amount - sum(shares)
    priority = sorted(
        (index for index, weight in enumerate(exact_weights) if weight > 0),
        key=lambda index: (
            -(exact_shares[index] - shares[index]),
            -exact_weights[index],
            index,
        ),
    )
    for index in priority[:remaining]:
        shares[index] += 1

    return [-share for share in shares] if total_cents < 0 else shares
