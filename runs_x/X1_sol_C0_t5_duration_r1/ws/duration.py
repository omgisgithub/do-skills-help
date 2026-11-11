import re
from fractions import Fraction


_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_PART_PATTERN = re.compile(_PART)
_CLOCK_FORM = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")
_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def _integer(digits: str) -> int:
    # Small chunks also support fields beyond Python's integer-string limit.
    result = 0
    for start in range(0, len(digits), 9):
        chunk = digits[start:start + 9]
        result = result * 10 ** len(chunk) + int(chunk)
    return result


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    value = s.strip()
    sign = 1
    if value.startswith("-"):
        sign = -1
        value = value[1:]

    if value == "0":
        return 0

    if _CLOCK_FORM.fullmatch(value):
        total = 0
        for field in value.split(":"):
            total = total * 60 + _integer(field)
        return sign * total

    if not _UNIT_FORM.fullmatch(value):
        raise ValueError("invalid duration")

    total = Fraction(0)
    previous_unit = 604801
    for match in _PART_PATTERN.finditer(value):
        number, unit = match.groups()
        seconds = _SECONDS[unit]
        if seconds >= previous_unit:
            raise ValueError("units must be in strictly decreasing order")
        previous_unit = seconds

        whole, separator, decimal = number.partition(".")
        amount = Fraction(_integer(whole))
        if separator:
            amount += Fraction(_integer(decimal), 10 ** len(decimal))
        total += amount * seconds

    if total.denominator != 1:
        raise ValueError("duration must be a whole number of seconds")
    return sign * total.numerator
