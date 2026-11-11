import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
# Largest to smallest; a unit may only appear after strictly larger ones.
_UNIT_ORDER = "wdhms"
_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_PART = re.compile(r"(" + _NUMBER + r")([wdhms])")
_UNIT_FORM = re.compile(r"[0-9]+(?:\.[0-9]+)?[wdhms](?: ?[0-9]+(?:\.[0-9]+)?[wdhms])*")
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    text = s.strip()
    if not text:
        raise ValueError("empty duration")

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
            # M:SS
            total = int(first) * 60 + int(second)
        else:
            # H:MM:SS
            total = int(first) * 3600 + int(second) * 60 + int(third)
        return sign * total

    if _UNIT_FORM.fullmatch(text):
        # Fraction keeps the sum exact, so 0.1h is 360 and 0.3s is rejected.
        total = Fraction(0)
        last = -1
        for number, unit in _PART.findall(text):
            index = _UNIT_ORDER.index(unit)
            if index <= last:
                raise ValueError(f"units out of order or repeated: {s!r}")
            last = index
            total += Fraction(number) * _UNITS[unit]
        if total.denominator != 1:
            raise ValueError(f"duration is not a whole number of seconds: {s!r}")
        return sign * int(total)

    raise ValueError(f"invalid duration: {s!r}")
