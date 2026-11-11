import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"
_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(r"%s(?: ?%s)*" % (_PART, _PART))
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_HMS = re.compile(r"([0-9]+):([0-5][0-9]):([0-5][0-9])")
_CLOCK_MS = re.compile(r"([0-9]+):([0-5][0-9])")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    t = s.strip()
    sign = 1
    if t.startswith("-"):
        sign = -1
        t = t[1:]
    if t == "0":
        return 0
    m = _CLOCK_HMS.fullmatch(t)
    if m:
        h, mi, se = (int(x) for x in m.groups())
        return sign * (h * 3600 + mi * 60 + se)
    m = _CLOCK_MS.fullmatch(t)
    if m:
        mi, se = (int(x) for x in m.groups())
        return sign * (mi * 60 + se)
    if not _UNIT_FORM.fullmatch(t):
        raise ValueError("invalid duration: %r" % (s,))
    total = Fraction(0)
    last = -1
    for num, unit in _PART_RE.findall(t):
        idx = _ORDER.index(unit)
        if idx <= last:
            raise ValueError("units out of order or repeated: %r" % (s,))
        last = idx
        total += Fraction(num) * _UNITS[unit]
    if total.denominator != 1:
        raise ValueError("not a whole number of seconds: %r" % (s,))
    return sign * int(total)
