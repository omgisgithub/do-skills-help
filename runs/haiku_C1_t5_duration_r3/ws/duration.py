import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = "wdhms"

# Form A: one or more <number><unit> parts, separated by at most one space.
_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(rf"{_PART}(?: ?{_PART})*")
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")

# Form B: H:MM:SS or M:SS, with MM/SS restricted to 00-59.
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")

    text = s.strip()
    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]

    if text == "0":
        return 0

    clock = _CLOCK_FORM.fullmatch(text)
    if clock:
        first, second, third = clock.groups()
        if third is None:
            hours, minutes, seconds = 0, first, second
        else:
            hours, minutes, seconds = first, second, third
        total = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        return sign * total

    if not _UNIT_FORM.fullmatch(text):
        raise ValueError(f"invalid duration: {s!r}")

    total = Fraction(0)
    last_index = -1
    for number, unit in _PART_RE.findall(text):
        index = _UNIT_ORDER.index(unit)
        if index <= last_index:
            raise ValueError(f"invalid duration (units out of order or repeated): {s!r}")
        last_index = index
        total += Fraction(number) * _UNIT_SECONDS[unit]

    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {s!r}")
    return sign * int(total)
