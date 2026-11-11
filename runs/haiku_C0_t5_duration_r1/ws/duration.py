import re
from fractions import Fraction

# Unit seconds, ordered from largest to smallest; position = rank for ordering checks.
_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = {"w": 0, "d": 1, "h": 2, "m": 3, "s": 4}

# [0-9] rather than \d so that non-ASCII digits are rejected.
_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_PART_RE = re.compile(_PART)
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")

    body = s.strip()
    if not body:
        raise ValueError("empty duration")

    sign = 1
    if body.startswith("-"):
        sign = -1
        body = body[1:]

    if body == "0" and sign == 1:
        return 0

    if ":" in body:
        match = _CLOCK_FORM.fullmatch(body)
        if not match:
            raise ValueError(f"invalid clock duration: {s!r}")
        first, second, third = match.groups()
        if third is None:
            # M:SS
            total = int(first) * 60 + int(second)
        else:
            # H:MM:SS
            total = int(first) * 3600 + int(second) * 60 + int(third)
        return sign * total

    if not _UNIT_FORM.fullmatch(body):
        raise ValueError(f"invalid duration: {s!r}")

    total = Fraction(0)
    previous_rank = -1
    for number, unit in _PART_RE.findall(body):
        rank = _UNIT_ORDER[unit]
        if rank <= previous_rank:
            raise ValueError(f"units out of order or repeated: {s!r}")
        previous_rank = rank
        total += Fraction(number) * _UNITS[unit]

    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {s!r}")
    return sign * int(total)
