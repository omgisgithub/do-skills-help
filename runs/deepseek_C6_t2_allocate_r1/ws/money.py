"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact_weight(weight):
    """Return *weight* as an exact Fraction, or raise for an invalid weight."""
    if isinstance(weight, Fraction):
        value = weight
    elif isinstance(weight, int):
        value = Fraction(weight)
    elif isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError("weight must be finite")
        value = Fraction(weight)
    elif isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weight must be finite")
        value = Fraction(weight)
    else:
        raise TypeError("weight must be an int, float, Fraction or Decimal")

    if value < 0:
        raise ValueError("weight must not be negative")
    return value


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    weight_list = list(weights)
    if not weight_list:
        raise ValueError("weights must not be empty")

    exact = [_exact_weight(weight) for weight in weight_list]
    total_weight = sum(exact, Fraction(0))
    if total_weight == 0:
        raise ValueError("weights must not all be zero")

    amount = abs(total_cents)
    shares = []
    remainders = []
    for weight in exact:
        share = Fraction(amount) * weight / total_weight
        whole = share.numerator // share.denominator
        shares.append(whole)
        remainders.append(share - whole)

    leftover = amount - sum(shares)
    # Largest remainder first; then larger weight; then lower index.
    order = sorted(
        range(len(exact)),
        key=lambda i: (remainders[i], exact[i], -i),
        reverse=True,
    )
    for i in order[:leftover]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-share for share in shares]
    return shares
