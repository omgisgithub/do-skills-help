import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = "wdhms"

_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(rf"{_PART}(?: ?{_PART})*")
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    text = s.strip()
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    total = _parse_unsigned(text, s)
    return -total if negative else total


def _parse_unsigned(text, original):
    if text == "0":
        return 0
    if _UNIT_FORM.fullmatch(text):
        total = _parse_unit_form(text, original)
    elif match := _CLOCK_FORM.fullmatch(text):
        total = _parse_clock_form(match)
    else:
        raise ValueError(f"invalid duration: {original!r}")
    return total


def _parse_unit_form(text, original):
    total = Fraction(0)
    last_index = -1
    for number, unit in _PART_RE.findall(text):
        index = _UNIT_ORDER.index(unit)
        if index <= last_index:
            raise ValueError(f"units out of order or repeated: {original!r}")
        last_index = index
        total += Fraction(number) * _UNIT_SECONDS[unit]
    if total.denominator != 1:
        raise ValueError(f"not a whole number of seconds: {original!r}")
    return int(total)


def _parse_clock_form(match):
    first, second, third = match.groups()
    if third is None:
        return int(first) * 60 + int(second)
    return int(first) * 3600 + int(second) * 60 + int(third)
