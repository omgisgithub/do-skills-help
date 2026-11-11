import re
from fractions import Fraction


_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_PART_PATTERN = re.compile(_PART)
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")
_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(s: str) -> int:
    """Parse a strict unit or clock duration into exact whole seconds."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    value = s.strip()
    sign = 1
    if value.startswith("-"):
        sign = -1
        value = value[1:]

    if value == "0":
        return 0

    clock = _CLOCK_FORM.fullmatch(value)
    if clock:
        first, second, third = clock.groups()
        total = int(first) * 60 + int(second)
        if third is not None:
            total = total * 60 + int(third)
        return sign * total

    if not _UNIT_FORM.fullmatch(value):
        raise ValueError("invalid duration")

    total = Fraction(0)
    previous_scale = 604801
    for part in _PART_PATTERN.finditer(value):
        number, unit = part.groups()
        scale = _SECONDS[unit]
        if scale >= previous_scale:
            raise ValueError("duration units must be in decreasing order")
        previous_scale = scale
        total += Fraction(number) * scale

    if total.denominator != 1:
        raise ValueError("duration must be a whole number of seconds")
    return sign * total.numerator
