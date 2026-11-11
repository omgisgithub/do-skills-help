import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = {"w": 4, "d": 3, "h": 2, "m": 1, "s": 0}

_UNIT_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_RE = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def _invalid(s):
    return ValueError("invalid duration: {!r}".format(s))


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    text = s.strip()
    if not text:
        raise _invalid(s)

    negative = False
    if text.startswith("-"):
        negative = True
        text = text[1:]
        if not text:
            raise _invalid(s)

    # The bare string "0" is the only valid bare number.
    if text == "0" and not negative:
        return 0

    # Form B: clock form.
    clock = _CLOCK_RE.fullmatch(text)
    if clock is not None:
        first = int(clock.group(1))
        second = int(clock.group(2))
        third = clock.group(3)
        if third is None:
            total = first * 60 + second
        else:
            total = first * 3600 + second * 60 + int(third)
        return -total if negative else total

    # Form A: unit form. Consecutive parts are joined by at most one space.
    total = Fraction(0)
    previous_order = None
    position = 0
    length = len(text)

    while position < length:
        match = _UNIT_PART_RE.match(text, position)
        if match is None:
            raise _invalid(s)
        number, unit = match.groups()
        order = _UNIT_ORDER[unit]
        if previous_order is not None and order >= previous_order:
            raise _invalid(s)
        previous_order = order
        total += Fraction(number) * _UNIT_SECONDS[unit]
        position = match.end()

        if position < length and text[position] == " ":
            position += 1
            if position == length:
                raise _invalid(s)

    if total.denominator != 1:
        raise _invalid(s)

    result = int(total)
    return -result if negative else result
