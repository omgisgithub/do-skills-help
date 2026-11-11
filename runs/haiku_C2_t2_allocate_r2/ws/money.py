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
        if isinstance(w, float) and not math.isfinite(w):
            raise ValueError("weights must be finite")
        if isinstance(w, Decimal) and not w.is_finite():
            raise ValueError("weights must be finite")
        f = Fraction(w)  # exact: floats are not rounded
        if f < 0:
            raise ValueError("weights must not be negative")
        exact.append(f)
    total_weight = sum(exact)
    if total_weight == 0:
        raise ValueError("at least one weight must be non-zero")

    n = abs(total_cents)
    shares = [n * w / total_weight for w in exact]
    floors = [int(s) for s in shares]  # shares are non-negative, so int() floors
    leftover = n - sum(floors)
    # Largest remainder first; ties go to the larger weight, then the lower index.
    order = sorted(range(len(exact)), key=lambda i: (-(shares[i] - floors[i]), -exact[i], i))
    for i in order[:leftover]:
        floors[i] += 1

    if total_cents < 0:
        floors = [-s for s in floors]
    return floors
