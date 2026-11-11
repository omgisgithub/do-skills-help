"""Parse human-written durations into whole seconds.

See TASK.md for the full grammar.
"""

import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_RANK = {"w": 0, "d": 1, "h": 2, "m": 3, "s": 4}

_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_PART = rf"{_NUMBER}[wdhms]"
_UNIT_FORM_RE = re.compile(rf"{_UNIT_PART}(?: ?{_UNIT_PART})*")
_UNIT_PART_RE = re.compile(rf"({_NUMBER})([wdhms])")
_CLOCK_FORM_RE = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def _to_fraction(number):
    """Convert a decimal-digit string to an exact Fraction."""
    if "." in number:
        whole, fraction = number.split(".")
        return Fraction(int(whole + fraction), 10 ** len(fraction))
    return Fraction(int(number))


def _parse_unit_form(body):
    if _UNIT_FORM_RE.fullmatch(body) is None:
        raise ValueError("invalid duration: %r" % (body,))

    total = Fraction(0)
    last_rank = -1
    for number, unit in _UNIT_PART_RE.findall(body):
        rank = _UNIT_RANK[unit]
        if rank <= last_rank:
            raise ValueError("invalid duration: units out of order or repeated")
        last_rank = rank
        total += _to_fraction(number) * _UNIT_SECONDS[unit]

    if total.denominator != 1:
        raise ValueError("invalid duration: not a whole number of seconds")
    return total.numerator


def _parse_clock_form(body):
    match = _CLOCK_FORM_RE.fullmatch(body)
    if match is None:
        raise ValueError("invalid duration: %r" % (body,))

    first, second, third = match.groups()
    if third is None:
        # M:SS
        return int(first) * 60 + int(second)
    # H:MM:SS
    return int(first) * 3600 + int(second) * 60 + int(third)


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    body = s.strip()
    if not body:
        raise ValueError("invalid duration: empty input")

    negative = False
    if body.startswith("-"):
        negative = True
        body = body[1:]

    if body == "0":
        if negative:
            raise ValueError("invalid duration: %r" % (s,))
        return 0

    if ":" in body:
        seconds = _parse_clock_form(body)
    else:
        seconds = _parse_unit_form(body)

    return -seconds if negative else seconds
