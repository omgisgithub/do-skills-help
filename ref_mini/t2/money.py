from fractions import Fraction
from decimal import Decimal
import math


def _frac(w):
    if isinstance(w, bool):
        raise ValueError("bool weight")
    if isinstance(w, float):
        if math.isnan(w) or math.isinf(w):
            raise ValueError("bad float")
        return Fraction(w)
    if isinstance(w, Decimal):
        if not w.is_finite():
            raise ValueError("bad decimal")
        return Fraction(w)
    if isinstance(w, (int, Fraction)):
        return Fraction(w)
    raise ValueError("bad weight type")


def allocate(total_cents, weights):
    if isinstance(total_cents, bool) or not isinstance(total_cents, int):
        raise ValueError("total must be int")
    ws = [_frac(w) for w in list(weights)]
    if not ws:
        raise ValueError("empty")
    if any(w < 0 for w in ws):
        raise ValueError("negative")
    s = sum(ws)
    if s == 0:
        raise ValueError("all zero")
    sign = -1 if total_cents < 0 else 1
    t = abs(total_cents)
    exact = [t * w / s for w in ws]
    base = [math.floor(e) for e in exact]
    left = t - sum(base)
    order = sorted(range(len(ws)), key=lambda i: (-(exact[i] - base[i]), -ws[i], i))
    for i in order[:left]:
        base[i] += 1
    return [sign * b for b in base]
