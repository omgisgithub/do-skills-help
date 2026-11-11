import re
from fractions import Fraction


_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_FORM = re.compile(rf"{_NUMBER}[wdhms](?: ?{_NUMBER}[wdhms])*")
_PART = re.compile(rf"({_NUMBER})([wdhms])")
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")
_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


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

    clock = _CLOCK_FORM.fullmatch(value)
    if clock:
        first, second, third = clock.groups()
        if third is None:
            return sign * (int(first) * 60 + int(second))
        return sign * (int(first) * 3600 + int(second) * 60 + int(third))

    if not _UNIT_FORM.fullmatch(value):
        raise ValueError("invalid duration")

    total = Fraction(0)
    previous = _SECONDS["w"] + 1
    for number, unit in _PART.findall(value):
        seconds = _SECONDS[unit]
        if seconds >= previous:
            raise ValueError("duration units must be in decreasing order")
        previous = seconds
        total += Fraction(number) * seconds

    if total.denominator != 1:
        raise ValueError("duration must be a whole number of seconds")
    return sign * total.numerator
