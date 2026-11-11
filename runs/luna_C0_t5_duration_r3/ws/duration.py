import re
from fractions import Fraction


_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_PART_RE = re.compile(r"(" + _NUMBER + r")([wdhms])")
_CLOCK_RE = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")
_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = {unit: rank for rank, unit in enumerate("wdhms")}


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
        if not value:
            raise ValueError("duration cannot be empty")
    elif value.startswith("+"):
        raise ValueError("leading plus is not allowed")

    if value == "0":
        return 0

    clock = _CLOCK_RE.fullmatch(value)
    if clock:
        first, second, third = clock.groups()
        if int(second) > 59 or (third is not None and int(third) > 59):
            raise ValueError("clock field must be between 00 and 59")
        if third is None:
            seconds = int(first) * 60 + int(second)
        else:
            seconds = int(first) * 3600 + int(second) * 60 + int(third)
        return sign * seconds

    # Split only on single ASCII spaces; empty parts reject repeated spaces.
    parts = value.split(" ")
    if any(not part for part in parts):
        raise ValueError("invalid spacing")

    total = Fraction(0)
    previous_rank = -1
    for segment in parts:
        pos = 0
        while pos < len(segment):
            match = _PART_RE.match(segment, pos)
            if match is None:
                raise ValueError("invalid duration")
            number, unit = match.groups()
            rank = _UNIT_ORDER[unit]
            if rank <= previous_rank:
                raise ValueError("units must be in decreasing order and unique")
            previous_rank = rank
            if "." in number:
                whole, decimal = number.split(".")
                amount = Fraction(int(whole + decimal), 10 ** len(decimal))
            else:
                amount = Fraction(int(number))
            total += amount * _UNIT_SECONDS[unit]
            pos = match.end()

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds")
    return sign * total.numerator
