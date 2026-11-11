import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"
_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(r"%s(?: ?%s)*" % (_PART, _PART))
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK = re.compile(r"(?:([0-9]+):([0-5][0-9])|([0-9]+):([0-5][0-9]):([0-5][0-9]))")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    t = s.strip()
    negative = t.startswith("-")
    if negative:
        t = t[1:]
    if not t:
        raise ValueError("empty duration")

    if t == "0":
        total = Fraction(0)
    elif _CLOCK.fullmatch(t):
        nums = [int(x) for x in t.split(":")]
        total = Fraction(0)
        for n in nums:
            total = total * 60 + n
    elif _UNIT_FORM.fullmatch(t):
        total = Fraction(0)
        last = -1
        for num, unit in _PART_RE.findall(t):
            idx = _ORDER.index(unit)
            if idx <= last:
                raise ValueError("units out of order or repeated")
            last = idx
            total += Fraction(num) * _UNITS[unit]
        if total.denominator != 1:
            raise ValueError("not a whole number of seconds")
    else:
        raise ValueError("invalid duration: %r" % (s,))

    result = int(total)
    return -result if negative else result
