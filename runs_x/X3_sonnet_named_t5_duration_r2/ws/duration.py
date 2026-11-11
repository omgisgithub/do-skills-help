import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"
_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_RE = re.compile(r"(?:%s)(?: ?(?:%s))*" % (_PART, _PART))
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_RE = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s: str) -> int:
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    t = s.strip()
    neg = False
    if t.startswith("-"):
        neg = True
        t = t[1:]
    if not t:
        raise ValueError("empty duration")
    if t == "0":
        return 0
    m = _CLOCK_RE.fullmatch(t)
    if m:
        if m.group(3) is None:
            total = Fraction(int(m.group(1)) * 60 + int(m.group(2)))
        else:
            total = Fraction(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)))
    elif _UNIT_RE.fullmatch(t):
        total = Fraction(0)
        last = -1
        for num, unit in _PART_RE.findall(t):
            idx = _ORDER.index(unit)
            if idx <= last:
                raise ValueError("units out of order or repeated")
            last = idx
            total += Fraction(num) * _UNITS[unit]
    else:
        raise ValueError("invalid duration: %r" % (s,))
    if total.denominator != 1:
        raise ValueError("not a whole number of seconds")
    r = int(total)
    return -r if neg else r
