"""Money helpers."""

import math
from fractions import Fraction


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    fracs = []
    for w in weights:
        try:
            f = Fraction(w)  # exact for float and Decimal; NaN/inf raise here
        except (ValueError, OverflowError):
            raise ValueError("weights must be finite")
        if f < 0:
            raise ValueError("weights must not be negative")
        fracs.append(f)

    total_weight = sum(fracs)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    n = abs(total_cents)
    exact = [n * f / total_weight for f in fracs]
    shares = [math.floor(e) for e in exact]
    leftover = n - sum(shares)
    # Largest remainder first; ties go to the larger weight, then the lower index.
    by_remainder = sorted(
        range(len(fracs)),
        key=lambda i: (-(exact[i] - shares[i]), -fracs[i], i),
    )
    for i in by_remainder[:leftover]:
        shares[i] += 1

    sign = -1 if total_cents < 0 else 1
    return [sign * s for s in shares]
