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
            exact = Fraction(weight)
        except (TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
            raise ValueError("weights must be finite numeric values") from exc
        if exact < 0:
            raise ValueError("weights must not be negative")
        exact_weights.append(exact)

    weight_sum = sum(exact_weights, Fraction(0))
    if weight_sum == 0:
        raise ValueError("at least one weight must be positive")

    amount = abs(total_cents)
    shares = []
    remainders = []
    for weight in exact_weights:
        exact_share = Fraction(amount) * weight / weight_sum
        floor_share = exact_share.numerator // exact_share.denominator
        shares.append(floor_share)
        remainders.append(exact_share - floor_share)

    cents_left = amount - sum(shares)
    order = sorted(
        range(len(exact_weights)),
        key=lambda i: (-remainders[i], -exact_weights[i], i),
    )
    for i in order[:cents_left]:
        shares[i] += 1

    if total_cents < 0:
        return [-share for share in shares]
    return shares
