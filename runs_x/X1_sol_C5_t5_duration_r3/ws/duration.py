import re
from fractions import Fraction


_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_UNITS = re.compile(_PART + r"(?: ?" + _PART + r")*")
_CLOCK = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    s = s.strip()
    sign = 1
    if s.startswith("-"):
        sign = -1
        s = s[1:]

    if s == "0":
        return 0

    if _CLOCK.fullmatch(s):
        total = 0
        for field in s.split(":"):
            total = total * 60 + int(field)
        return sign * total

    if not _UNITS.fullmatch(s):
        raise ValueError("invalid duration")

    total = Fraction(0)
    previous_size = _SECONDS["w"] + 1
    for number, unit in re.findall(_PART, s):
        size = _SECONDS[unit]
        if size >= previous_size:
            raise ValueError("duration units must be in decreasing order")
        previous_size = size
        total += Fraction(number) * size

    if total.denominator != 1:
        raise ValueError("duration must be a whole number of seconds")
    return sign * total.numerator
