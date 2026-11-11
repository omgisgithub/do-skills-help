"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting NaN and infinity."""
    if isinstance(weight, float):
        if math.isnan(weight) or math.isinf(weight):
            raise ValueError("weights must be finite")
        return Fraction(weight)
    if isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(weight)
    if isinstance(weight, (int, Fraction)):
        return Fraction(weight)
    raise TypeError(f"unsupported weight type: {type(weight).__name__}")


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    weights = list(weights)
    if not weights:
        raise ValueError("weights must not be empty")
    fracs = [_to_fraction(w) for w in weights]
    if any(f < 0 for f in fracs):
        raise ValueError("weights must not be negative")
    total_weight = sum(fracs)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    amount = abs(total_cents)
    exact = [amount * f / total_weight for f in fracs]
    shares = [math.floor(e) for e in exact]
    leftover = amount - sum(shares)
    # Largest remainder first; ties go to the larger weight, then the lower index.
    # Zero-weight parties are excluded so they can never receive a leftover cent.
    order = sorted(
        (i for i, f in enumerate(fracs) if f > 0),
        key=lambda i: (-(exact[i] - shares[i]), -fracs[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1
    if total_cents < 0:
        shares = [-s for s in shares]
    return shares
