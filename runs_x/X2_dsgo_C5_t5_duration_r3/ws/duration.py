"""Parse human-written durations into whole seconds."""

import re
from fractions import Fraction

_UNIT_SECONDS = {
    "w": 604800,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}

# Strictly decreasing size, as required by Form A.
_UNIT_RANK = {unit: rank for rank, unit in enumerate("wdhms")}

_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_PART = _NUMBER + r"[wdhms]"
_UNIT_FORM = re.compile(r"^" + _UNIT_PART + r"(?: ?" + _UNIT_PART + r")*$")
_UNIT_PART_RE = re.compile(r"(" + _NUMBER + r")([wdhms])")

_CLOCK_FORM = re.compile(r"^([0-9]+):([0-9]{2})(?::([0-9]{2}))?$")


def _parse_unit_form(body):
    total = Fraction(0)
    previous_rank = -1

    for match in _UNIT_PART_RE.finditer(body):
        number, unit = match.group(1), match.group(2)
        rank = _UNIT_RANK[unit]
        if rank <= previous_rank:
            raise ValueError("units must be strictly decreasing and unique")
        previous_rank = rank
        total += Fraction(number) * _UNIT_SECONDS[unit]

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds")
    return total.numerator


def _parse_clock_form(body):
    match = _CLOCK_FORM.match(body)
    if match is None:
        raise ValueError("invalid duration")
    first, second, third = match.groups()
    if third is None:
        # M:SS
        minutes = int(first)
        seconds = int(second)
        if seconds > 59:
            raise ValueError("seconds out of range")
        return minutes * 60 + seconds
    # H:MM:SS
    hours = int(first)
    minutes = int(second)
    seconds = int(third)
    if minutes > 59 or seconds > 59:
        raise ValueError("minutes or seconds out of range")
    return hours * 3600 + minutes * 60 + seconds


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    body = s.strip()
    if not body:
        raise ValueError("empty duration")

    negative = body.startswith("-")
    if negative:
        body = body[1:]
        if not body:
            raise ValueError("invalid duration")

    if body == "0":
        result = 0
    elif _CLOCK_FORM.match(body):
        result = _parse_clock_form(body)
    elif _UNIT_FORM.match(body):
        result = _parse_unit_form(body)
    else:
        raise ValueError("invalid duration")

    return -result if negative else result
