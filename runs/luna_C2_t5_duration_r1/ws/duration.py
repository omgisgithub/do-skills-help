import re
from fractions import Fraction


_PART = re.compile(r"(\d+(?:\.\d+)?)([wdhms])")
_CLOCK = re.compile(r"(\d+):(\d{2})(?::(\d{2}))?")
_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")
    value = s.strip()
    if not value:
        raise ValueError("duration cannot be empty")

    sign = -1 if value.startswith("-") else 1
    if sign < 0:
        value = value[1:]
    if value == "0":
        return 0

    clock = _CLOCK.fullmatch(value)
    if clock:
        first, second, third = clock.groups()
        second = int(second)
        if second > 59 or (third is not None and int(third) > 59):
            raise ValueError("clock fields must be between 00 and 59")
        total = int(first) * (60 if third is None else 3600) + second * (60 if third else 1)
        if third is not None:
            total += int(third)
        return sign * total

    total = Fraction(0)
    previous_size = float("inf")
    parts = value.split(" ")
    if any(not part for part in parts):
        raise ValueError("invalid duration spacing")
    for part in parts:
        position = 0
        for match in _PART.finditer(part):
            if match.start() != position:
                raise ValueError("invalid duration part")
            number, unit = match.groups()
            size = _UNITS[unit]
            if size >= previous_size:
                raise ValueError("duration units must be in decreasing order")
            previous_size = size
            total += Fraction(number) * size
            position = match.end()
        if position != len(part):
            raise ValueError("invalid duration part")
    if total.denominator != 1:
        raise ValueError("duration must be a whole number of seconds")
    return sign * total.numerator
