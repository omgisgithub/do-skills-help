import re
from fractions import Fraction

_UNITS = (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
_UNIT_SECONDS = dict(_UNITS)
_UNIT_ORDER = {u: i for i, (u, _) in enumerate(_UNITS)}
_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a str")
    text = s.strip()
    if text == "0":
        return 0
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    if not text:
        raise ValueError("empty duration")

    m = _CLOCK.fullmatch(text)
    if m:
        if m.group(3) is None:
            total = int(m.group(1)) * 60 + int(m.group(2))
        else:
            total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        return -total if negative else total

    total = Fraction(0)
    pos = 0
    last = -1
    while True:
        m = _PART.match(text, pos)
        if not m:
            raise ValueError("invalid duration: %r" % s)
        order = _UNIT_ORDER[m.group(2)]
        if order <= last:
            raise ValueError("units out of order or repeated: %r" % s)
        last = order
        total += Fraction(m.group(1)) * _UNIT_SECONDS[m.group(2)]
        pos = m.end()
        if pos == len(text):
            break
        if text[pos] == " ":
            pos += 1
    if total.denominator != 1:
        raise ValueError("not a whole number of seconds: %r" % s)
    total = int(total)
    return -total if negative else total
