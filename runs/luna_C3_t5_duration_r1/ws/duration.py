import re
from fractions import Fraction


_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = {unit: index for index, unit in enumerate(_UNIT_SECONDS)}
_NUMBER = r"[0-9]+(?:\.[0-9]+)?"


def parse_duration(s: str) -> int:
    """Parse a human-written duration and return its exact value in seconds."""
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
            raise ValueError("duration must contain a value")

    if value == "0":
        return 0

    # Clock fields use ASCII digits and fixed-width minute/second fields.
    clock = re.fullmatch(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?", value)
    if clock:
        first = int(clock.group(1))
        second = int(clock.group(2))
        third = clock.group(3)
        if second > 59 or (third is not None and int(third) > 59):
            raise ValueError("clock minute and second fields must be 00 through 59")
        if third is None:
            seconds = first * 60 + second
        else:
            seconds = first * 3600 + second * 60 + int(third)
        return sign * seconds

    # A unit expression consists only of adjacent parts or parts separated by
    # exactly one space. Parse it in order so duplicate/increasing units fail.
    part_re = re.compile(r"(" + _NUMBER + r")([wdhms])")
    total = Fraction(0)
    position = 0
    previous_order = -1
    seen = set()
    while position < len(value):
        match = part_re.match(value, position)
        if not match:
            raise ValueError("invalid duration")
        number, unit = match.groups()
        order = _UNIT_ORDER[unit]
        if unit in seen or order <= previous_order:
            raise ValueError("duration units must be unique and decreasing")
        seen.add(unit)
        previous_order = order
        total += Fraction(number) * _UNIT_SECONDS[unit]
        position = match.end()
        if position == len(value):
            break
        if value[position] == " ":
            position += 1
            if position == len(value) or value[position] == " ":
                raise ValueError("invalid spacing in duration")

    if not seen or position != len(value) or total.denominator != 1:
        raise ValueError("duration must resolve to a whole number of seconds")
    return sign * total.numerator
