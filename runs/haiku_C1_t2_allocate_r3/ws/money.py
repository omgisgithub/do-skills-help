"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def _to_fraction(weight):
    """Convert a weight to an exact Fraction, rejecting NaN, infinities and bad types."""
    if isinstance(weight, Fraction):
        return weight
    if isinstance(weight, int):
        return Fraction(weight)
    if isinstance(weight, float):
        if not math.isfinite(weight):
            raise ValueError("weights must be finite")
        return Fraction(weight)
    if isinstance(weight, Decimal):
        if not weight.is_finite():
            raise ValueError("weights must be finite")
        return Fraction(weight)
    raise ValueError("unsupported weight type: %s" % type(weight).__name__)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if len(weights) == 0:
        raise ValueError("weights must not be empty")

    fracs = [_to_fraction(w) for w in weights]
    if any(f < 0 for f in fracs):
        raise ValueError("weights must not be negative")
    total_weight = sum(fracs)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    amount = abs(total_cents)
    exact = [amount * f / total_weight for f in fracs]
    shares = [int(e) for e in exact]  # exact values are non-negative, so int() floors
    leftover = amount - sum(shares)

    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(
        range(len(fracs)),
        key=lambda i: (-(exact[i] - shares[i]), -fracs[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    if total_cents < 0:
        shares = [-s for s in shares]
    return shares
