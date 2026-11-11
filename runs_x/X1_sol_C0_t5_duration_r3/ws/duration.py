import re
from fractions import Fraction


_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_PART_PATTERN = re.compile(_PART)
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")
_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
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
    if clock is not None:
        first, second, third = clock.groups()
        if third is None:
            return sign * (int(first) * 60 + int(second))
        return sign * (int(first) * 3600 + int(second) * 60 + int(third))

    if _UNIT_FORM.fullmatch(value) is None:
        raise ValueError("invalid duration syntax")

    total = Fraction(0)
    previous_size = None
    for part in _PART_PATTERN.finditer(value):
        number, unit = part.groups()
        size = _UNIT_SECONDS[unit]
        if previous_size is not None and size >= previous_size:
            raise ValueError("duration units must be in decreasing order")
        previous_size = size
        total += Fraction(number) * size

    if total.denominator != 1:
        raise ValueError("duration must be a whole number of seconds")
    return sign * total.numerator
