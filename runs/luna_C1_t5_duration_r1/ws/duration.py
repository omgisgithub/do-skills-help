import re
from fractions import Fraction


_PART = re.compile(r"(\d+(?:\.\d+)?)([wdhms])")
_CLOCK_HMS = re.compile(r"(\d+):(\d{2}):(\d{2})")
_CLOCK_MS = re.compile(r"(\d+):(\d{2})")
_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(s: str) -> int:
    """Parse a strict human-written duration into whole seconds."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    value = s.strip()
    if not value:
        raise ValueError("duration cannot be empty")

    sign = 1
    if value.startswith("-"):
        sign = -1
        value = value[1:]
    if not value:
        raise ValueError("invalid duration")

    if value == "0":
        return 0

    match = _CLOCK_HMS.fullmatch(value)
    if match:
        hours, minutes, seconds = map(int, match.groups())
        if minutes > 59 or seconds > 59:
            raise ValueError("clock fields must be between 00 and 59")
        return sign * (hours * 3600 + minutes * 60 + seconds)

    match = _CLOCK_MS.fullmatch(value)
    if match:
        minutes, seconds = map(int, match.groups())
        if seconds > 59:
            raise ValueError("clock fields must be between 00 and 59")
        return sign * (minutes * 60 + seconds)

    # Spaces are permitted only as one separator between unit parts.
    parts = value.split(" ")
    if any(not part for part in parts):
        raise ValueError("invalid spacing")

    total = Fraction(0)
    previous_size = float("inf")
    for part in parts:
        position = 0
        while position < len(part):
            match = _PART.match(part, position)
            if not match:
                raise ValueError("invalid duration part")
            number, unit = match.groups()
            size = _UNITS[unit]
            if size >= previous_size:
                raise ValueError("units must be in strictly decreasing order")
            previous_size = size

            whole, dot, decimal = number.partition(".")
            numerator = int(whole + decimal) if dot else int(whole)
            denominator = 10 ** len(decimal) if dot else 1
            total += Fraction(numerator * size, denominator)
            position = match.end()

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds")
    return sign * total.numerator
