"""Parse scheduler durations using the grammar in TASK.md."""

import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_UNITS = re.compile(r"[0-9]+(?:\.[0-9]+)?[wdhms](?: ?[0-9]+(?:\.[0-9]+)?[wdhms])*")
_CLOCK = re.compile(r"[0-9]+(?::[0-5][0-9]){1,2}")


def parse_duration(s: str) -> int:
    """Parse a unit or clock duration into an exact whole number of seconds.

    Args:
        s: Duration text, optionally negative and surrounded by whitespace.

    Returns:
        The signed number of seconds.

    Raises:
        TypeError: If the input is not a string.
        ValueError: If the syntax is invalid or the total seconds are fractional.
    """
    if not isinstance(s, str):
        raise TypeError("Duration must be a string")
    text = s.strip()
    sign = -1 if text.startswith("-") else 1
    if sign == -1:
        text = text[1:]
    if text == "0":
        return 0
    if _CLOCK.fullmatch(text):
        seconds = 0
        for field in text.split(":"):
            seconds = seconds * 60 + int(field)
        return sign * seconds
    if not _UNITS.fullmatch(text):
        raise ValueError("Invalid duration syntax")
    total = Fraction(0)
    previous_unit = 604801
    for part in _PART.finditer(text):
        number, unit = part.groups()
        unit_seconds = _UNIT_SECONDS[unit]
        if unit_seconds >= previous_unit:
            raise ValueError("Duration units must appear in strictly decreasing order")
        previous_unit = unit_seconds
        total += Fraction(number) * unit_seconds
    if total.denominator != 1:
        raise ValueError("Duration must total a whole number of seconds")
    return sign * total.numerator
