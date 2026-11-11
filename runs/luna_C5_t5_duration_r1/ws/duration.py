import re
from fractions import Fraction


_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = {unit: index for index, unit in enumerate(_UNIT_SECONDS)}
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    value = s.strip()
    if not value:
        raise ValueError("duration cannot be empty")

    negative = value.startswith("-")
    if negative:
        value = value[1:]
        if not value:
            raise ValueError("duration must contain a value")

    if value == "0":
        return 0

    if re.fullmatch(r"[0-9]+:[0-9]{2}(?::[0-9]{2})?", value):
        fields = value.split(":")
        if any(int(field) > 59 for field in fields[1:]):
            raise ValueError("clock fields must be between 00 and 59")
        if len(fields) == 2:
            total = int(fields[0]) * 60 + int(fields[1])
        else:
            total = int(fields[0]) * 3600 + int(fields[1]) * 60 + int(fields[2])
        return -total if negative else total

    total = Fraction(0)
    previous_order = -1
    position = 0
    first = True
    while position < len(value):
        if not first:
            if value[position] == " ":
                position += 1
                if position == len(value) or value[position] == " ":
                    raise ValueError("invalid duration separator")
        match = _PART_RE.match(value, position)
        if match is None:
            raise ValueError("invalid duration")
        number, unit = match.groups()
        order = _UNIT_ORDER[unit]
        if order <= previous_order:
            raise ValueError("units must be in strictly decreasing size")
        previous_order = order
        total += Fraction(number) * _UNIT_SECONDS[unit]
        position = match.end()
        first = False

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds")
    seconds = total.numerator
    return -seconds if negative else seconds
