from fractions import Fraction
from decimal import Decimal
import math


def _to_fraction(w):
    if isinstance(w, bool):
        raise ValueError("invalid weight")
    if isinstance(w, float):
        if math.isnan(w) or math.isinf(w):
            raise ValueError("invalid weight")
        return Fraction(w)
    if isinstance(w, Decimal):
        if not w.is_finite():
            raise ValueError("invalid weight")
        return Fraction(w)
    if isinstance(w, (int, Fraction)):
        return Fraction(w)
    raise ValueError("invalid weight type")


def allocate(total_cents, weights):
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total_cents must be an int")
    ws = [_to_fraction(w) for w in list(weights)]
    if not ws:
        raise ValueError("weights is empty")
    if any(w < 0 for w in ws):
        raise ValueError("negative weight")
    s = sum(ws, Fraction(0))
    if s == 0:
        raise ValueError("all weights zero")

    t = abs(total_cents)
    exact = [w * t / s for w in ws]
    shares = [math.floor(e) for e in exact]
    left = t - sum(shares)
    order = sorted(
        (i for i in range(len(ws)) if ws[i] > 0),
        key=lambda i: (-(exact[i] - shares[i]), -ws[i], i),
    )
    for i in order[:left]:
        shares[i] += 1
    if total_cents < 0:
        shares = [-x for x in shares]
    return shares
