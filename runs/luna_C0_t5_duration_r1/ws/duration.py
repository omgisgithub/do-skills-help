import re
from fractions import Fraction


_CLOCK = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?\Z")
_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds, following TASK.md's grammar."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    value = s.strip()
    if not value:
        raise ValueError("duration cannot be empty")
    if value == "0":
        return 0

    sign = 1
    if value.startswith("-"):
        sign = -1
        value = value[1:]
        if not value:
            raise ValueError("duration is incomplete")

    clock = _CLOCK.fullmatch(value)
    if clock:
        first, second, third = clock.groups()
        second = int(second)
        if second > 59:
            raise ValueError("clock field out of range")
        if third is None:
            return sign * (int(first) * 60 + second)
        third = int(third)
        if third > 59:
            raise ValueError("clock field out of range")
        return sign * (int(first) * 3600 + second * 60 + third)

    # Parse sequentially so unit ordering and the exact single-space separator
    # rule are both enforced, without accepting otherwise-valid regex fragments.
    total = Fraction(0)
    pos = 0
    last_rank = -1
    seen = set()
    ranks = {unit: rank for rank, unit in enumerate("wdhms")}
    while pos < len(value):
        match = _PART.match(value, pos)
        if not match:
            raise ValueError("invalid duration")
        number, unit = match.groups()
        rank = ranks[unit]
        if rank <= last_rank or unit in seen:
            raise ValueError("units must be in strictly decreasing order")
        last_rank = rank
        seen.add(unit)

        if "." in number:
            whole, decimal = number.split(".")
            amount = Fraction(int(whole + decimal), 10 ** len(decimal))
        else:
            amount = Fraction(int(number))
        total += amount * _UNITS[unit]
        pos = match.end()
        if pos == len(value):
            break
        if value[pos] == " ":
            pos += 1
            if pos == len(value) or value[pos] == " ":
                raise ValueError("invalid spacing")
        # Otherwise the next part must begin immediately.

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds")
    return sign * total.numerator
