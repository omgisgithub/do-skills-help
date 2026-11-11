import re
from fractions import Fraction


_PART = re.compile(r"([0-9]+)(?:\.([0-9]+))?([wdhms])")
_CLOCK = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")
_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def _integer(digits: str) -> int:
    # Small chunks also support fields beyond Python's integer-string limit.
    result = 0
    for start in range(0, len(digits), 9):
        chunk = digits[start:start + 9]
        result = result * 10 ** len(chunk) + int(chunk)
    return result


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds, following TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    value = s.strip()
    sign = 1
    if value.startswith("-"):
        sign = -1
        value = value[1:]
    if value == "0":
        return 0
    if not value:
        raise ValueError("duration is empty")

    clock = _CLOCK.fullmatch(value)
    if clock:
        first, second, third = clock.groups()
        if third is None:
            return sign * (_integer(first) * 60 + int(second))
        return sign * (_integer(first) * 3600 + int(second) * 60 + int(third))

    total = Fraction(0)
    previous_unit = 604801
    position = 0
    while position < len(value):
        part = _PART.match(value, position)
        if part is None:
            raise ValueError("invalid duration syntax")
        whole, decimal, unit = part.groups()
        seconds = _UNITS[unit]
        if seconds >= previous_unit:
            raise ValueError("duration units must be in decreasing order")
        previous_unit = seconds
        decimal = decimal or ""
        total += Fraction(_integer(whole + decimal), 10 ** len(decimal)) * seconds
        position = part.end()
        if position < len(value) and value[position] == " ":
            position += 1
            if position == len(value):
                raise ValueError("invalid duration syntax")

    if total.denominator != 1:
        raise ValueError("duration must be a whole number of seconds")
    return sign * total.numerator
