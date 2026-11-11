import re
from fractions import Fraction


_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_UNITS = re.compile(r"[0-9]+(?:\.[0-9]+)?[wdhms](?: ?[0-9]+(?:\.[0-9]+)?[wdhms])*")
_CLOCK = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")
_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(s: str) -> int:
    """Parse the unit or clock grammar in TASK.md into exact whole seconds.

    Raise TypeError for non-strings and ValueError for invalid durations.
    """
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
        seconds = 0
        for field in s.split(":"):
            seconds = seconds * 60 + int(field)
        return sign * seconds

    if not _UNITS.fullmatch(s):
        raise ValueError("invalid duration syntax")

    total = Fraction(0)
    previous_scale = 604801
    for number, unit in _PART.findall(s):
        scale = _SECONDS[unit]
        if scale >= previous_scale:
            raise ValueError("duration units must be in decreasing order")
        previous_scale = scale
        total += Fraction(number) * scale

    if total.denominator != 1:
        raise ValueError("duration must total a whole number of seconds")
    return sign * total.numerator
