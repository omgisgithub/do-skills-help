import re
from fractions import Fraction

UNITS = [("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
PART = re.compile(r"(\d+(?:\.\d+)?)([wdhms])")


def parse_duration(s):
    if not isinstance(s, str):
        raise TypeError("expected str")
    s = s.strip()
    if not s:
        raise ValueError("empty")
    neg = s.startswith("-")
    body = s[1:] if neg else s
    if body == "0":
        return 0
    m = re.fullmatch(r"(\d+):([0-5]\d)(?::([0-5]\d))?", body)
    if m:
        if m[3] is None:
            v = int(m[1]) * 60 + int(m[2])
        else:
            v = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
        return -v if neg else v
    if not re.fullmatch(r"(\d+(?:\.\d+)?[wdhms] ?)*\d+(?:\.\d+)?[wdhms]", body):
        raise ValueError("bad syntax")
    order = [u for u, _ in UNITS]
    size = dict(UNITS)
    last = -1
    total = Fraction(0)
    for num, unit in PART.findall(body):
        i = order.index(unit)
        if i <= last:
            raise ValueError("unit order")
        last = i
        total += Fraction(num) * size[unit]
    if total.denominator != 1:
        raise ValueError("not whole seconds")
    v = int(total)
    return -v if neg else v
