import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"

_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(r"%s(?: ?%s)*" % (_PART, _PART))
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_HMS = re.compile(r"([0-9]+):([0-5][0-9]):([0-5][0-9])")
_CLOCK_MS = re.compile(r"([0-9]+):([0-5][0-9])")


def parse_duration(s: str) -> int:
    """Parse a human-written duration into a whole number of seconds."""
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    text = s.strip()
    negative = False
    if text.startswith("-"):
        negative = True
        text = text[1:]
    if not text:
        raise ValueError("empty duration")

    if text == "0":
        return 0

    m = _CLOCK_HMS.fullmatch(text)
    if m:
        h, mi, sec = (int(g) for g in m.groups())
        total = Fraction(h * 3600 + mi * 60 + sec)
    else:
        m = _CLOCK_MS.fullmatch(text)
        if m:
            total = Fraction(int(m.group(1)) * 60 + int(m.group(2)))
        elif _UNIT_FORM.fullmatch(text):
            total = Fraction(0)
            last = -1
            for num, unit in _PART_RE.findall(text):
                idx = _ORDER.index(unit)
                if idx <= last:
                    raise ValueError("units out of order or repeated: %r" % s)
                last = idx
                total += Fraction(num) * _UNITS[unit]
        else:
            raise ValueError("invalid duration: %r" % s)

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds: %r" % s)
    result = int(total)
    return -result if negative else result
