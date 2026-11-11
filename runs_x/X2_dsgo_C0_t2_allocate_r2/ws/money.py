"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(value):
    """Return *value* as an exact Fraction, rejecting non-finite weights."""
    if isinstance(value, bool):
        # bool is an int subclass; treat it like the int it is.
        return Fraction(int(value))
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Fraction):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("weight must be finite")
        return Fraction(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("weight must be finite")
        return Fraction(value)
    raise TypeError("unsupported weight type: %r" % (type(value).__name__,))


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")

    if len(weights) == 0:
        raise ValueError("weights must not be empty")

    exact_weights = [_to_fraction(w) for w in weights]
    if any(w < 0 for w in exact_weights):
        raise ValueError("weights must not be negative")

    total_weight = sum(exact_weights, Fraction(0))
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")

    # Work with a non-negative amount, then negate the shares at the end.
    sign = -1 if total_cents < 0 else 1
    amount = abs(total_cents)

    shares = []
    remainders = []
    for weight in exact_weights:
        exact_share = Fraction(amount) * weight / total_weight
        whole = math.floor(exact_share)
        shares.append(whole)
        remainders.append(exact_share - whole)

    leftover = amount - sum(shares)

    # Largest remainder first; ties go to the larger weight, then lower index.
    order = sorted(
        range(len(exact_weights)),
        key=lambda i: (-remainders[i], -exact_weights[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    if sign == -1:
        shares = [-share for share in shares]
    return shares
