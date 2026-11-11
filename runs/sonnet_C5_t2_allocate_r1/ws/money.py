"""Money helpers."""

from decimal import Decimal
from fractions import Fraction


def _to_fraction(w):
    if isinstance(w, Fraction):
        return w
    if isinstance(w, Decimal):
        if w.is_nan() or w.is_infinite():
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, float):
        if w != w or w in (float("inf"), float("-inf")):
            raise ValueError("weight must be finite")
        return Fraction(w)
    if isinstance(w, int):
        return Fraction(w)
    raise ValueError("unsupported weight type: %r" % type(w).__name__)


def allocate(total_cents, weights):
    """Split total_cents across weights. See TASK.md for the full spec."""
    if not isinstance(total_cents, int) or isinstance(total_cents, bool):
        raise ValueError("total_cents must be an int")
    fr = [_to_fraction(w) for w in list(weights)]
    if not fr:
        raise ValueError("weights must not be empty")
    if any(w < 0 for w in fr):
        raise ValueError("weights must not be negative")
    weight_sum = sum(fr, Fraction(0))
    if weight_sum == 0:
        raise ValueError("weights must not all be zero")

    total = abs(total_cents)
    exact = [total * w / weight_sum for w in fr]
    shares = [e.numerator // e.denominator for e in exact]
    leftover = total - sum(shares)

    order = sorted(
        (i for i, w in enumerate(fr) if w > 0),
        key=lambda i: (-(exact[i] - shares[i]), -fr[i], i),
    )
    for i in order[:leftover]:
        shares[i] += 1

    return [-s for s in shares] if total_cents < 0 else shares
