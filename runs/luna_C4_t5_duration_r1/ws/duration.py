import re
from fractions import Fraction
from typing import Optional


_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_PART = re.compile(r"(\d+(?:\.\d+)?)([wdhms])")
_CLOCK_HMS = re.compile(r"(\d+):(\d{2}):(\d{2})")
_CLOCK_MS = re.compile(r"(\d+):(\d{2})")


def parse_duration(s: str) -> int:
    """Parse a human-written duration into a whole number of seconds."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    value = s.strip()
    if not value:
        raise ValueError("duration must not be empty")

    sign = 1
    if value.startswith("-"):
        sign = -1
        value = value[1:]
    if not value or value.startswith(("+", "-")):
        raise ValueError("invalid duration")

    if value == "0":
        return 0

    match = _CLOCK_HMS.fullmatch(value)
    if match is not None:
        hours, minutes, seconds = (int(field) for field in match.groups())
        if minutes > 59 or seconds > 59:
            raise ValueError("clock fields must be between 00 and 59")
        return sign * (hours * 3600 + minutes * 60 + seconds)

    match = _CLOCK_MS.fullmatch(value)
    if match is not None:
        minutes, seconds = (int(field) for field in match.groups())
        if seconds > 59:
            raise ValueError("clock seconds must be between 00 and 59")
        return sign * (minutes * 60 + seconds)

    parts: list[tuple[str, str]] = []
    position = 0
    while position < len(value):
        match = _UNIT_PART.match(value, position)
        if match is None:
            raise ValueError("invalid duration")
        parts.append((match.group(1), match.group(2)))
        position = match.end()
        if position == len(value):
            break
        if value[position] == " ":
            position += 1
            if position == len(value) or value[position] == " ":
                raise ValueError("invalid duration")

    total = Fraction(0)
    previous_size: Optional[int] = None
    for number, unit in parts:
        size = _UNIT_SECONDS[unit]
        if previous_size is not None and size >= previous_size:
            raise ValueError("units must be in strictly decreasing size")
        previous_size = size
        total += Fraction(number) * size

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds")
    return sign * total.numerator
