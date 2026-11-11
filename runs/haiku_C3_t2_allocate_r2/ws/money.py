"""Money helpers."""

import math
from decimal import Decimal
from fractions import Fraction


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    if not weights:
        raise ValueError("weights must not be empty")

    exact = []
    for w in weights:
        if isinstance(w, float):
            if math.isnan(w) or math.isinf(w):
                raise ValueError("weights must be finite")
            exact.append(Fraction(w))
        elif isinstance(w, Decimal):
            if not w.is_finite():
                raise ValueError("weights must be finite")
            exact.append(Fraction(w))
        else:
            exact.append(Fraction(w))

    if any(w < 0 for w in exact):
        raise ValueError("weights must not be negative")
    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    amount = abs(total_cents)
    shares = [amount * w / total_weight for w in exact]
    floors = [int(s) for s in shares]
    leftover = amount - sum(floors)

    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(
        range(len(exact)),
        key=lambda i: (-(shares[i] - floors[i]), -exact[i], i),
    )
    for i in order[:leftover]:
        floors[i] += 1

    if total_cents < 0:
        return [-f for f in floors]
    return floors
