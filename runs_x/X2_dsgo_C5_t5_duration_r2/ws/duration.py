import re
from fractions import Fraction

_UNIT_SECONDS = {
    "w": 604800,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}
_UNIT_ORDER = ["w", "d", "h", "m", "s"]

_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_PART = r"(" + _NUMBER + r")([wdhms])"
_UNIT_FORM_RE = re.compile(r"^" + _PART + r"(?: ?" + _PART + r")*\Z")
_UNIT_PART_RE = re.compile(_PART)
_CLOCK_FORM_RE = re.compile(r"^([0-9]+):([0-9]{2})(?::([0-9]{2}))?\Z")


def _parse_number(text):
    """Return the exact value of a decimal number literal as a Fraction."""
    if "." in text:
        whole, frac = text.split(".")
        return Fraction(int(whole + frac), 10 ** len(frac))
    return Fraction(int(text), 1)


def _parse_unit_form(body):
    """Parse Form A and return the total seconds as an exact Fraction."""
    total = Fraction(0, 1)
    last_index = -1

    for match in _UNIT_PART_RE.finditer(body):
        number_text, unit = match.group(1), match.group(2)
        index = _UNIT_ORDER.index(unit)
        if index <= last_index:
            raise ValueError("units must be strictly decreasing and unique")
        last_index = index
        total += _parse_number(number_text) * _UNIT_SECONDS[unit]

    return total


def _parse_clock_form(body):
    """Parse Form B and return the total seconds as an exact Fraction."""
    match = _CLOCK_FORM_RE.match(body)
    first, second, third = match.group(1), match.group(2), match.group(3)

    if third is None:
        # M:SS
        minutes, seconds = int(first), int(second)
        if seconds > 59:
            raise ValueError("seconds field must be 00-59")
        return Fraction(minutes * 60 + seconds, 1)

    # H:MM:SS
    hours, minutes, seconds = int(first), int(second), int(third)
    if minutes > 59 or seconds > 59:
        raise ValueError("minutes and seconds fields must be 00-59")
    return Fraction(hours * 3600 + minutes * 60 + seconds, 1)


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    body = s.strip()
    if not body:
        raise ValueError("empty duration")

    negative = False
    if body.startswith("-"):
        negative = True
        body = body[1:]

    if body == "0":
        return 0

    if ":" in body:
        if not _CLOCK_FORM_RE.match(body):
            raise ValueError("invalid clock duration")
        total = _parse_clock_form(body)
    else:
        if not _UNIT_FORM_RE.match(body):
            raise ValueError("invalid unit duration")
        total = _parse_unit_form(body)

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds")

    result = total.numerator
    return -result if negative else result
