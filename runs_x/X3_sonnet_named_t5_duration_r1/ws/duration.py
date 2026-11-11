import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"
_NUM = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_RE = re.compile(r"(?:%s[wdhms])(?: ?%s[wdhms])*" % (_NUM, _NUM))
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_RE = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    t = s.strip()
    if t == "0":
        return 0
    neg = False
    if t.startswith("-"):
        neg = True
        t = t[1:]
    if _UNIT_RE.fullmatch(t):
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
        val = int(total)
    else:
        m = _CLOCK_RE.fullmatch(t)
        if not m:
            raise ValueError("invalid duration: %r" % s)
        a, b, c = m.groups()
        if c is None:
            if int(b) > 59:
                raise ValueError("invalid duration: %r" % s)
            val = int(a) * 60 + int(b)
        else:
            if int(b) > 59 or int(c) > 59:
                raise ValueError("invalid duration: %r" % s)
            val = int(a) * 3600 + int(b) * 60 + int(c)
    return -val if neg else val
