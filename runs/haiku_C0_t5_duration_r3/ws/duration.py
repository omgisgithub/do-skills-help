import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}

_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_UNIT_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_HMS = re.compile(r"([0-9]+):([0-5][0-9]):([0-5][0-9])")
_CLOCK_MS = re.compile(r"([0-9]+):([0-5][0-9])")


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

    if _CLOCK_HMS.fullmatch(text):
        hours, minutes, seconds = _CLOCK_HMS.fullmatch(text).groups()
        total = Fraction(int(hours) * 3600 + int(minutes) * 60 + int(seconds))
    elif _CLOCK_MS.fullmatch(text):
        minutes, seconds = _CLOCK_MS.fullmatch(text).groups()
        total = Fraction(int(minutes) * 60 + int(seconds))
    elif _UNIT_FORM.fullmatch(text):
        total = Fraction(0)
        previous = None
        for number, unit in _UNIT_PART.findall(text):
            size = _UNIT_SECONDS[unit]
            if previous is not None and size >= previous:
                raise ValueError(f"units must be strictly decreasing: {s!r}")
            previous = size
            total += Fraction(number) * size
    else:
        raise ValueError(f"invalid duration: {s!r}")

    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {s!r}")
    result = int(total)
    return -result if negative else result
