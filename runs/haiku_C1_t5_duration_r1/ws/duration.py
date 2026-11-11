import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"

# Use [0-9] rather than \d: \d also matches non-ASCII digits.
_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_PART_CAPTURE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_CLOCK_MS = re.compile(r"([0-9]+):([0-5][0-9])")
_CLOCK_HMS = re.compile(r"([0-9]+):([0-5][0-9]):([0-5][0-9])")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a str")

    text = s.strip()
    negative = text.startswith("-")
    if negative:
        text = text[1:]

    if text == "0" and not negative:
        return 0

    clock = _CLOCK_HMS.fullmatch(text)
    if clock:
        hours, minutes, seconds = clock.groups()
        total = Fraction(int(hours) * 3600 + int(minutes) * 60 + int(seconds))
    elif clock := _CLOCK_MS.fullmatch(text):
        minutes, seconds = clock.groups()
        total = Fraction(int(minutes) * 60 + int(seconds))
    elif _UNIT_FORM.fullmatch(text):
        total = Fraction(0)
        last = -1
        for number, unit in _PART_CAPTURE.findall(text):
            index = _ORDER.index(unit)
            if index <= last:
                raise ValueError(f"units out of order or repeated: {s!r}")
            last = index
            total += Fraction(number) * _UNITS[unit]
    else:
        raise ValueError(f"invalid duration: {s!r}")

    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {s!r}")
    result = int(total)
    return -result if negative else result
