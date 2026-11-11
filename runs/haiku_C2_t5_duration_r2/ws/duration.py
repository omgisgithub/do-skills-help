import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}  # largest first
_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_PART_RE = re.compile(_PART)
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    body = s.strip()
    sign = 1
    if body.startswith("-"):
        sign, body = -1, body[1:]
    if body == "0":
        return 0

    clock = _CLOCK_FORM.fullmatch(body)
    if clock:
        a, b, c = clock.groups()
        if c is None:
            secs = Fraction(int(a) * 60 + int(b))
        else:
            secs = Fraction(int(a) * 3600 + int(b) * 60 + int(c))
    elif _UNIT_FORM.fullmatch(body):
        secs, last_rank = Fraction(0), -1
        units = list(_UNITS)
        for num, unit in _PART_RE.findall(body):
            rank = units.index(unit)
            if rank <= last_rank:  # units must strictly decrease, each once
                raise ValueError(f"units out of order or repeated: {s!r}")
            last_rank = rank
            secs += Fraction(num) * _UNITS[unit]  # exact: 0.1h is 360 s, not a float
    else:
        raise ValueError(f"invalid duration: {s!r}")

    if secs.denominator != 1:
        raise ValueError(f"not a whole number of seconds: {s!r}")
    return sign * int(secs)
