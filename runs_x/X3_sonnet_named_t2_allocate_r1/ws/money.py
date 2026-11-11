"""Money helpers."""
from decimal import Decimal
from fractions import Fraction
import math


def _to_fraction(w):
    if isinstance(w, Fraction):
        return w
    if isinstance(w, Decimal):
        if w.is_nan() or w.is_infinite():
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, float):
        if math.isnan(w) or math.isinf(w):
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, int):
        return Fraction(w)
    raise ValueError("unsupported weight type")


def allocate(total_cents, weights):
    """Split total_cents across weights (largest remainder). See TASK.md."""
    if type(total_cents) is not int and (
        isinstance(total_cents, bool) or not isinstance(total_cents, int)
    ):
        raise ValueError("total_cents must be an int")
    weights = list(weights)
    if not weights:
        raise ValueError("weights must not be empty")
    fr = [_to_fraction(w) for w in weights]
    if any(f < 0 for f in fr):
        raise ValueError("weights must not be negative")
    s = sum(fr, Fraction(0))
    if s == 0:
        raise ValueError("weights must not all be zero")

    t = abs(total_cents)
    exact = [t * f / s for f in fr]
    shares = [e.numerator // e.denominator for e in exact]
    left = t - sum(shares)
    order = sorted(
        (i for i in range(len(fr)) if fr[i] > 0),
        key=lambda i: (-(exact[i] - shares[i]), -fr[i], i),
    )
    for i in order[:left]:
        shares[i] += 1
    return [-x for x in shares] if total_cents < 0 else shares
