"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction

__all__ = ["allocate"]

# Weight types accepted by :func:`allocate`. Floats are converted with
# ``Fraction(x)`` so that binary floating-point error cannot decide a tie.
_WEIGHT_TYPES = (int, float, Fraction, Decimal)


def _to_exact_weight(weight: object) -> Fraction:
    """Convert a single weight to an exact ``Fraction``.

    Args:
        weight: A value of type ``int``, ``float``, ``Fraction`` or ``Decimal``.

    Returns:
        The weight as an exact ``Fraction``.

    Raises:
        ValueError: If the weight has an unsupported type or is NaN or infinite.
    """
    if not isinstance(weight, _WEIGHT_TYPES):
        raise ValueError(f"unsupported weight type: {type(weight).__name__}")
    if isinstance(weight, float) and not math.isfinite(weight):
        raise ValueError(f"weight must be finite: {weight!r}")
    if isinstance(weight, Decimal) and not weight.is_finite():
        raise ValueError(f"weight must be finite: {weight!r}")
    try:
        return Fraction(weight)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"invalid weight: {weight!r}") from exc


def allocate(total_cents: int, weights: list) -> list[int]:
    """Split total_cents across weights using the largest-remainder method.

    Each party receives the floor of its exact proportional share; leftover
    cents are distributed one at a time in order of decreasing fractional
    remainder, with ties broken by larger weight and then by lower index.
    A negative ``total_cents`` is allocated by magnitude and then negated.

    Args:
        total_cents: The total amount in cents.
        weights: Non-negative weights, one per party. Accepted types are
            ``int``, ``float``, ``Fraction`` and ``Decimal``. The sequence is
            never modified.

    Returns:
        A list of integer cents, one per weight, summing exactly to
        ``total_cents``.

    Raises:
        ValueError: If ``total_cents`` is not an ``int`` (``bool`` is
            rejected), if ``weights`` is empty, if any weight is negative, NaN
            or infinite, or if every weight is zero.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError(f"total_cents must be an int, not {total_cents!r}")

    try:
        count = len(weights)
    except TypeError:
        weights = list(weights)
        count = len(weights)

    if count == 0:
        raise ValueError("weights must not be empty")

    exact_weights = [_to_exact_weight(weight) for weight in weights]
    for weight in exact_weights:
        if weight < 0:
            raise ValueError(f"weights must not be negative: {weight!r}")

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    total = abs(total_cents)
    shares = []
    remainders = []
    for weight in exact_weights:
        exact_share = Fraction(total) * weight / total_weight
        whole = exact_share.numerator // exact_share.denominator
        shares.append(whole)
        remainders.append(exact_share - whole)

    leftover = total - sum(shares)
    order = sorted(
        range(count),
        key=lambda index: (-remainders[index], -exact_weights[index], index),
    )
    for index in order[:leftover]:
        shares[index] += 1

    if total_cents < 0:
        shares = [-share for share in shares]

    return shares
