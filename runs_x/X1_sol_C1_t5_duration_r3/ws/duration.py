import re
from fractions import Fraction


_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_PART_PATTERN = re.compile(_PART)
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")
_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def _integer(digits: str) -> int:
    # Chunk conversion also avoids interpreter limits on long decimal strings.
    value = 0
    for start in range(0, len(digits), 1000):
        chunk = digits[start:start + 1000]
        value = value * 10 ** len(chunk) + int(chunk)
    return value


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

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
        total = _integer(first) * 60 + int(second)
        if third is not None:
            total = total * 60 + int(third)
        return sign * total

    if not _UNIT_FORM.fullmatch(text):
        raise ValueError("invalid duration format")

    total = Fraction(0)
    previous_size = 604801
    for number, unit in _PART_PATTERN.findall(text):
        size = _SECONDS[unit]
        if size >= previous_size:
            raise ValueError("units must be in strictly decreasing order")
        previous_size = size
        whole, _, decimal = number.partition(".")
        total += Fraction(_integer(whole + decimal), 10 ** len(decimal)) * size

    if total.denominator != 1:
        raise ValueError("duration must be a whole number of seconds")
    return sign * total.numerator
