import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_PART = _NUMBER + r"[wdhms]"
_UNIT_FORM = re.compile(_UNIT_PART + r"(?: ?" + _UNIT_PART + r")*")
_UNIT_PARTS = re.compile(r"(" + _NUMBER + r")([wdhms])")
_CLOCK_FORM = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a str")
    text = s.strip()
    if text == "0":
        return 0
    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]
    if _CLOCK_FORM.fullmatch(text):
        total = 0
        for field in text.split(":"):
            total = total * 60 + int(field)
        return sign * total
    if _UNIT_FORM.fullmatch(text):
        total = Fraction(0)
        previous = None
        for number, unit in _UNIT_PARTS.findall(text):
            size = _UNITS[unit]
            if previous is not None and size >= previous:
                raise ValueError(f"units out of order or repeated: {s!r}")
            previous = size
            total += Fraction(number) * size
        if total.denominator != 1:
            raise ValueError(f"not a whole number of seconds: {s!r}")
        return sign * int(total)
    raise ValueError(f"invalid duration: {s!r}")
