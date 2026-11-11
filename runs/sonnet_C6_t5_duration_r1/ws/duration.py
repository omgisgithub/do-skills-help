import re
from fractions import Fraction

_NUM = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_RE = re.compile(r"(?:%s[wdhms])(?: ?(?:%s[wdhms]))*" % (_NUM, _NUM))
_PART_RE = re.compile(r"(%s)([wdhms])" % _NUM)
_CLOCK_RE = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")
_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("parse_duration expects str")
    t = s.strip()
    neg = False
    if t.startswith("-"):
        neg = True
        t = t[1:]
    if t == "":
        raise ValueError("empty duration")
    if t == "0" and not neg:
        return 0

    m = _CLOCK_RE.fullmatch(t)
    if m:
        if m.group(3) is None:
            total = int(m.group(1)) * 60 + int(m.group(2))
        else:
            # H:MM:SS
            total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    elif _UNIT_RE.fullmatch(t):
        total = Fraction(0)
        last = -1
        for num, unit in _PART_RE.findall(t):
            idx = _ORDER.index(unit)
            if idx <= last:
                raise ValueError("units out of order or repeated")
            last = idx
            total += Fraction(num) * _SECONDS[unit]
        if total.denominator != 1:
            raise ValueError("not a whole number of seconds")
        total = int(total)
    else:
        raise ValueError("invalid duration: %r" % (s,))
    return -total if neg else total
