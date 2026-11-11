import re
from fractions import Fraction


_CLOCK = re.compile(r"(?:([0-9]+):([0-9]{2}):([0-9]{2})|([0-9]+):([0-9]{2}))\Z")
_PARTS = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    value = s.strip()
    if not value:
        raise ValueError("duration cannot be empty")

    sign = 1
    if value.startswith("-"):
        sign = -1
        value = value[1:]
    if not value or value.startswith(("-", "+")):
        raise ValueError("invalid duration")

    if value == "0":
        return 0

    clock = _CLOCK.fullmatch(value)
    if clock:
        fields = clock.groups()
        if fields[0] is not None:
            hours, minutes, seconds = map(int, fields[:3])
        else:
            hours = 0
            minutes, seconds = map(int, fields[3:])
        if minutes > 59 or seconds > 59:
            raise ValueError("invalid clock duration")
        return sign * (hours * 3600 + minutes * 60 + seconds)

    total = Fraction(0)
    last_rank = -1
    pos = 0
    part_count = 0
    while pos < len(value):
        match = _PARTS.match(value, pos)
        if match is None:
            raise ValueError("invalid duration")
        number, unit = match.groups()
        rank = "wdhms".index(unit)
        if rank <= last_rank:
            raise ValueError("units must be in decreasing order")
        last_rank = rank

        total += Fraction(number) * _UNITS[unit]
        part_count += 1
        pos = match.end()
        if pos == len(value):
            break
        if value[pos] != " ":
            raise ValueError("invalid duration")
        pos += 1
        if pos == len(value) or value[pos] == " ":
            raise ValueError("invalid duration")

    if part_count == 0 or total.denominator != 1:
        raise ValueError("duration must be a whole number of seconds")
    return sign * total.numerator
