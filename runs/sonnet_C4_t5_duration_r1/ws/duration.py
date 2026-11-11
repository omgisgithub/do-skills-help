import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = "wdhms"

_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_UNIT_FORM_RE = re.compile(rf"(?:{_NUMBER}[wdhms])(?: ?{_NUMBER}[wdhms])*")
_CLOCK_RE = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    text = s.strip()
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    if not text:
        raise ValueError(f"invalid duration: {s!r}")

    if text == "0" and not negative:
        return 0
    if _UNIT_FORM_RE.fullmatch(text):
        total = _parse_unit_form(text, s)
    else:
        match = _CLOCK_RE.fullmatch(text)
        if not match:
            raise ValueError(f"invalid duration: {s!r}")
        first, second, third = match.groups()
        if third is None:
            total = Fraction(int(first) * 60 + int(second))
        else:
            total = Fraction(int(first) * 3600 + int(second) * 60 + int(third))

    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {s!r}")
    return -int(total) if negative else int(total)


def _parse_unit_form(text, original):
    total = Fraction(0)
    last_index = -1
    for number, unit in _PART_RE.findall(text):
        index = _UNIT_ORDER.index(unit)
        if index <= last_index:
            raise ValueError(f"units out of order or repeated: {original!r}")
        last_index = index
        total += Fraction(number) * _UNIT_SECONDS[unit]
    return total
