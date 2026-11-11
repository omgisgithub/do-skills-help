"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _exact_weight(weight):
    """Convert a supported weight to an exact Fraction, raising on bad values."""
    if isinstance(weight, bool):
        return Fraction(int(weight))
    if isinstance(weight, int):
        return Fraction(weight)
    if isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError("weights must not be NaN or infinite")
        return Fraction(weight)
    if isinstance(weight, Fraction):
        return weight
    if isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must not be NaN or infinite")
        return Fraction(weight)
    raise ValueError("unsupported weight type: {!r}".format(type(weight).__name__))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    if len(weights) == 0:
        raise ValueError("weights must not be empty")

    exact = [_exact_weight(w) for w in weights]

    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact, Fraction(0))
    if total_weight == 0:
        raise ValueError("weights must not all be zero")

    negative = total_cents < 0
    amount = abs(total_cents)

    shares = []
    remainders = []
    for weight in exact:
        share = Fraction(amount) * weight / total_weight
        whole = share.numerator // share.denominator
        shares.append(whole)
        remainders.append(share - whole)

    leftover = amount - sum(shares)
    order = sorted(
        range(len(exact)),
        key=lambda i: (-remainders[i], -exact[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    if negative:
        shares = [-share for share in shares]
    return shares
