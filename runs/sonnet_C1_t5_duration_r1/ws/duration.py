import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"
_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(r"%s(?: ?%s)*" % (_PART, _PART))
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    t = s.strip()
    if not t:
        raise ValueError("empty duration")
    neg = t.startswith("-")
    if neg:
        t = t[1:]
    if t == "0" and not neg:
        return 0

    m = _CLOCK.fullmatch(t)
    if m:
        a, b, c = m.groups()
        if c is None:
            total = int(a) * 60 + int(b)
        else:
            if b is None:
                raise ValueError("invalid duration")
            total = int(a) * 3600 + int(b) * 60 + int(c)
        return -total if neg else total

    if not _UNIT_FORM.fullmatch(t):
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
    total = int(total)
    return -total if neg else total
