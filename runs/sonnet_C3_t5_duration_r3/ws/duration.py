import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"
_NUM = r"[0-9]+(?:\.[0-9]+)?"
_PART = _NUM + r"[wdhms]"
_UNIT_RE = re.compile(r"%s(?: ?%s)*" % (_PART, _PART))
_PART_RE = re.compile(r"(%s)([wdhms])" % _NUM)
_CLOCK_RE = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    t = s.strip()
    sign = 1
    if t.startswith("-"):
        sign = -1
        t = t[1:]
    if not t:
        raise ValueError("empty duration")

    if t == "0":
        return 0

    m = _CLOCK_RE.fullmatch(t)
    if m:
        a, b, c = m.groups()
        if c is None:
            total = int(a) * 60 + int(b)
        else:
            total = int(a) * 3600 + int(b) * 60 + int(c)
        return sign * total

    if not _UNIT_RE.fullmatch(t):
        raise ValueError("invalid duration: %r" % s)
    total = Fraction(0)
    last = -1
    for num, unit in _PART_RE.findall(t):
        idx = _ORDER.index(unit)
        if idx <= last:
            raise ValueError("units out of order or repeated: %r" % s)
        last = idx
        total += Fraction(num) * _UNITS[unit]
    if total.denominator != 1:
        raise ValueError("not a whole number of seconds: %r" % s)
    return sign * int(total)
