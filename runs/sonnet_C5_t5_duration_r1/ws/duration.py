import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"

_NUM = r"[0-9]+(?:\.[0-9]+)?"
_PART = r"(" + _NUM + r")([wdhms])"
_UNIT_RE = re.compile(_PART + r"(?: ?" + _PART + r")*")
_PART_RE = re.compile(_PART)
_CLOCK_RE = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s: str) -> int:
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    text = s.strip()
    if not text:
        raise ValueError("empty duration")
    if text == "0":
        return 0

    negative = text.startswith("-")
    if negative:
        text = text[1:]

    m = _CLOCK_RE.fullmatch(text)
    if m:
        if m.group(3) is None:
            total = int(m.group(1)) * 60 + int(m.group(2))
        else:
            total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    elif _UNIT_RE.fullmatch(text):
        total = Fraction(0)
        last = -1
        for num, unit in _PART_RE.findall(text):
            idx = _ORDER.index(unit)
            if idx <= last:
                raise ValueError("units must be in strictly decreasing order")
            last = idx
            total += Fraction(num) * _UNITS[unit]
        if total.denominator != 1:
            raise ValueError("duration is not a whole number of seconds")
        total = int(total)
    else:
        raise ValueError("invalid duration: %r" % (s,))

    return -total if negative else total
