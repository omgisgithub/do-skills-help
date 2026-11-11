"""Money helpers."""

from fractions import Fraction


def allocate(total_cents, weights):
    """Split ``total_cents`` proportionally using the largest remainder method."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact_weights = []
    for weight in weights:
        try:
            exact_weight = Fraction(weight)
        except (TypeError, ValueError, OverflowError, ZeroDivisionError):
            raise ValueError("weights must be finite numeric values") from None
        if exact_weight < 0:
            raise ValueError("weights must not be negative")
        exact_weights.append(exact_weight)

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    magnitude = abs(total_cents)
    floors = []
    remainders = []
    for weight in exact_weights:
        share = Fraction(magnitude) * weight / total_weight
        floor_share = share.numerator // share.denominator
        floors.append(floor_share)
        remainders.append(share - floor_share)

    leftover = magnitude - sum(floors)
    order = sorted(
        range(len(exact_weights)),
        key=lambda index: (
            -remainders[index],
            -exact_weights[index],
            index,
        ),
    )
    for index in order[:leftover]:
        floors[index] += 1

    if total_cents < 0:
        return [-share for share in floors]
    return floors
