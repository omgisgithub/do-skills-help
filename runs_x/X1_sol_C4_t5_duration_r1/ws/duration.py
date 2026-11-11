"""Parse human-written durations using the grammar in TASK.md."""

import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_CLOCK_FORM = re.compile(r"[0-9]+(?::[0-5][0-9]){1,2}")


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds.

    Args:
        s: A unit duration, clock duration, or bare zero, optionally negative.

    Returns:
        The signed number of seconds.

    Raises:
        TypeError: If the input is not a string.
        ValueError: If the grammar is invalid or the total seconds are fractional.
    """
    if not isinstance(s, str):
        raise TypeError("Duration must be a string")
    value = s.strip()
    sign = -1 if value.startswith("-") else 1
    if sign == -1:
        value = value[1:]
    if value == "0":
        return 0
    if _CLOCK_FORM.fullmatch(value):
        seconds = 0
        for field in value.split(":"):
            seconds = seconds * 60 + int(field)
        return sign * seconds
    return sign * _parse_units(value)


def _parse_units(value: str) -> int:
    if not _UNIT_FORM.fullmatch(value):
        raise ValueError("Invalid duration syntax")
    total = Fraction(0)
    previous_size = _UNIT_SECONDS["w"] + 1
    for part in re.finditer(_PART, value):
        number, unit = part.groups()
        size = _UNIT_SECONDS[unit]
        if size >= previous_size:
            raise ValueError("Duration units must be unique and in decreasing size")
        previous_size = size
        total += Fraction(number) * size
    if total.denominator != 1:
        raise ValueError("Duration must total a whole number of seconds")
    return total.numerator
