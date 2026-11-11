import re
from fractions import Fraction

_UNITS = (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
_UNIT_SECONDS = dict(_UNITS)
_UNIT_ORDER = {u: i for i, (u, _) in enumerate(_UNITS)}

_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(r"%s(?: ?%s)*" % (_PART, _PART))
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_FORM = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    text = s.strip()
    if not text:
        raise ValueError("empty duration")

    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]

    if text == "0":
        return 0

    m = _CLOCK_FORM.fullmatch(text)
    if m:
        if m.group(3) is None:
            minutes, seconds = int(m.group(1)), int(m.group(2))
            if seconds > 59:
                raise ValueError("seconds out of range")
            return sign * (minutes * 60 + seconds)
        hours, minutes, seconds = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if minutes > 59 or seconds > 59:
            raise ValueError("minutes/seconds out of range")
        return sign * (hours * 3600 + minutes * 60 + seconds)

    if not _UNIT_FORM.fullmatch(text):
        raise ValueError("invalid duration: %r" % s)

    total = Fraction(0)
    last = -1
    for num, unit in _PART_RE.findall(text):
        order = _UNIT_ORDER[unit]
        if order <= last:
            raise ValueError("units out of order or repeated")
        last = order
        total += Fraction(num) * _UNIT_SECONDS[unit]

    if total.denominator != 1:
        raise ValueError("not a whole number of seconds")
    return sign * int(total)
