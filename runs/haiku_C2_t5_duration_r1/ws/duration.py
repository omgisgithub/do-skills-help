import re
from fractions import Fraction

_ORDER = "wdhms"  # largest to smallest, so a unit's index must rise within one string
_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_NUM = r"[0-9]+(?:\.[0-9]+)?"
_PART = rf"{_NUM}[{_ORDER}]"
_UNIT_FORM = re.compile(rf"{_PART}(?: ?{_PART})*")
_PART_RE = re.compile(rf"({_NUM})([{_ORDER}])")
_CLOCK_FORM = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    body = s.strip()
    if body == "0":
        return 0
    sign = -1 if body.startswith("-") else 1
    if sign < 0:
        body = body[1:]
    if _CLOCK_FORM.fullmatch(body):
        total = 0
        for field in body.split(":"):
            total = total * 60 + int(field)
        return sign * total
    if not _UNIT_FORM.fullmatch(body):
        raise ValueError(f"invalid duration: {s!r}")
    total = Fraction(0)  # exact, so "0.1h" is 360 and not a float error
    last = -1
    for num, unit in _PART_RE.findall(body):
        rank = _ORDER.index(unit)
        if rank <= last:
            raise ValueError(f"units out of order or repeated: {s!r}")
        last = rank
        total += Fraction(num) * _SECONDS[unit]
    if total.denominator != 1:
        raise ValueError(f"not a whole number of seconds: {s!r}")
    return sign * int(total)
