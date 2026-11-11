import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"  # strictly decreasing size, so index must increase
_NUM = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_FORM = re.compile(rf"{_NUM}[wdhms](?: ?{_NUM}[wdhms])*")
_PART = re.compile(rf"({_NUM})([wdhms])")
_CLOCK_FORM = re.compile(r"[0-9]+(?::[0-5][0-9]){1,2}")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    text = s.strip()
    if text == "0":
        return 0
    sign = -1 if text.startswith("-") else 1
    body = text[1:] if sign < 0 else text
    if _CLOCK_FORM.fullmatch(body):
        total = 0
        for field in body.split(":"):
            total = total * 60 + int(field)
    elif _UNIT_FORM.fullmatch(body):
        total = Fraction(0)
        last = -1
        for num, unit in _PART.findall(body):
            rank = _ORDER.index(unit)
            if rank <= last:
                raise ValueError(f"units out of order or repeated: {s!r}")
            last = rank
            total += Fraction(num) * _UNITS[unit]
        if total.denominator != 1:
            raise ValueError(f"not a whole number of seconds: {s!r}")
        total = total.numerator
    else:
        raise ValueError(f"invalid duration: {s!r}")
    return sign * total
