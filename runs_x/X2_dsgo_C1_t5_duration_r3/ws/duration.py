import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = {unit: i for i, unit in enumerate("wdhms")}
_UNIT_PART = re.compile(r"(\d+(?:\.\d+)?)([wdhms])")
_UNIT_FORM = re.compile(r"\d+(?:\.\d+)?[wdhms](?: ?\d+(?:\.\d+)?[wdhms])*")
_CLOCK_FORM = re.compile(r"\d+(?::\d{2}){1,2}")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    text = s.strip()
    if not text:
        raise ValueError("empty duration")

    negative = False
    if text.startswith("-"):
        negative = True
        text = text[1:]
        if not text:
            raise ValueError("missing duration after sign")
    elif text.startswith("+"):
        raise ValueError("leading '+' is not allowed")

    if text == "0":
        return 0

    if _UNIT_FORM.fullmatch(text):
        total = Fraction(0)
        previous = -1
        for number, unit in _UNIT_PART.findall(text):
            order = _UNIT_ORDER[unit]
            if order <= previous:
                raise ValueError("units must be strictly decreasing and unique")
            previous = order
            total += Fraction(number) * _UNITS[unit]
        if total.denominator != 1:
            raise ValueError("duration is not a whole number of seconds")
        seconds = total.numerator
    elif _CLOCK_FORM.fullmatch(text):
        fields = [int(field) for field in text.split(":")]
        if any(field > 59 for field in fields[1:]):
            raise ValueError("clock field out of range")
        seconds = 0
        for field in fields:
            seconds = seconds * 60 + field
    else:
        raise ValueError("invalid duration")

    return -seconds if negative else seconds
