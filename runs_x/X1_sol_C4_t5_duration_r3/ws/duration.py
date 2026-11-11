"""Parse human-written scheduler durations using exact arithmetic."""

import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_UNITS = re.compile(_PART + r"(?: ?" + _PART + r")*")
_CLOCK = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def parse_duration(s: str) -> int:
    """Parse a unit or clock duration into whole seconds.

    Args:
        s: Duration text, optionally negative and surrounded by whitespace.

    Returns:
        The signed number of seconds.

    Raises:
        TypeError: If the input is not a string.
        ValueError: If the syntax is invalid or the total is not whole seconds.
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
        raise ValueError("Expected a unit duration or M:SS / H:MM:SS clock duration")
    return sign * _parse_units(text)


def _parse_units(text: str) -> int:
    total = Fraction(0)
    previous_scale = 604801
    for part in re.finditer(_PART, text):
        number, unit = part.groups()
        scale = _UNIT_SECONDS[unit]
        if scale >= previous_scale:
            raise ValueError("Duration units must appear once in decreasing size")
        previous_scale = scale
        total += Fraction(number) * scale
    if total.denominator != 1:
        raise ValueError("Duration must total a whole number of seconds")
    return total.numerator
