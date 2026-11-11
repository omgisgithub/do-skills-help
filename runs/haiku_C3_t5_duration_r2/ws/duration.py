import re
from fractions import Fraction

# Largest to smallest; a unit may only appear after units of greater size.
_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"

# ASCII-only classes: \d would also match non-ASCII digits.
_UNIT_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def _parse_units(text):
    """Sum the `<number><unit>` parts of Form A exactly, as a Fraction."""
    total = Fraction(0)
    last_rank = -1
    pos = 0
    while pos < len(text):
        m = _UNIT_PART.match(text, pos)
        if m is None:
            raise ValueError(f"invalid duration: {text!r}")
        number, unit = m.group(1), m.group(2)
        rank = _ORDER.index(unit)
        if rank <= last_rank:
            raise ValueError(f"units out of order or repeated: {text!r}")
        last_rank = rank
        total += Fraction(number) * _UNITS[unit]
        pos = m.end()
        # Parts may be joined directly or separated by one space.
        if pos < len(text) and text[pos] == " ":
            pos += 1
    return total


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")

    text = s.strip()
    if text == "0":
        return 0
    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]
    if not text:
        raise ValueError("empty duration")

    if ":" in text:
        m = _CLOCK.fullmatch(text)
        if m is None:
            raise ValueError(f"invalid clock duration: {s!r}")
        first, second, third = m.groups()
        if third is None:
            total = int(first) * 60 + int(second)
        else:
            total = int(first) * 3600 + int(second) * 60 + int(third)
    else:
        seconds = _parse_units(text)
        if seconds.denominator != 1:
            raise ValueError(f"duration is not a whole number of seconds: {s!r}")
        total = seconds.numerator

    return sign * total
