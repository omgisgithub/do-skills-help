import re
from fractions import Fraction

_UNITS = (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    s = s.strip()
    neg = False
    if s.startswith("-"):
        neg = True
        s = s[1:]
    if not s:
        raise ValueError("empty duration")

    total = None
    m = _CLOCK.fullmatch(s)
    if m:
        a, b, c = m.groups()
        if c is None:
            secs, first = int(b), int(a)
            if secs > 59:
                raise ValueError("invalid seconds")
            total = Fraction(first * 60 + secs)
        else:
            if int(b) > 59 or int(c) > 59:
                raise ValueError("invalid clock field")
            total = Fraction(int(a) * 3600 + int(b) * 60 + int(c))
    elif s == "0":
        total = Fraction(0)
    else:
        pos = 0
        prev = -1
        total = Fraction(0)
        while pos < len(s):
            if prev >= 0 and s[pos] == " ":
                pos += 1
            pm = _PART.match(s, pos)
            if not pm:
                raise ValueError("invalid duration")
            idx = "wdhms".index(pm.group(2))
            if idx <= prev:
                raise ValueError("units out of order")
            prev = idx
            total += Fraction(pm.group(1)) * _UNITS[idx][1]
            pos = pm.end()

    if total.denominator != 1:
        raise ValueError("not a whole number of seconds")
    result = int(total)
    return -result if neg else result
