import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"
_NUM = r"[0-9]+(?:\.[0-9]+)?"
_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_UNIT_FORM = re.compile(r"(?:%s[wdhms])(?: ?(?:%s[wdhms]))*" % (_NUM, _NUM))
_CLOCK = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("expected str")
    t = s.strip()
    neg = False
    if t.startswith("-"):
        neg = True
        t = t[1:]
    if not t:
        raise ValueError("empty duration")

    if t == "0":
        total = Fraction(0)
    elif _UNIT_FORM.fullmatch(t):
        total = Fraction(0)
        last = -1
        for num, unit in _PART.findall(t):
            idx = _ORDER.index(unit)
            if idx <= last:
                raise ValueError("units out of order or repeated")
            last = idx
            total += Fraction(num) * _UNITS[unit]
    else:
        m = _CLOCK.fullmatch(t)
        if not m:
            raise ValueError("invalid duration: %r" % s)
        a, b, c = m.groups()
        if c is None:
            total = Fraction(int(a) * 60 + int(b))
        else:
            total = Fraction(int(a) * 3600 + int(b) * 60 + int(c))

    if total.denominator != 1:
        raise ValueError("not a whole number of seconds")
    n = int(total)
    return -n if neg else n
