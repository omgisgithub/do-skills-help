import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = "wdhms"  # strictly decreasing size

_NUM = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_PART = re.compile(r"(" + _NUM + r")([wdhms])")
_UNIT_FORM = re.compile(_NUM + r"[wdhms](?: ?" + _NUM + r"[wdhms])*")
_CLOCK_FORM = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a str")

    s = s.strip()
    negative = s.startswith("-")
    body = s[1:] if negative else s
    sign = -1 if negative else 1

    if body == "":
        raise ValueError("empty duration")
    if body == "0" and not negative:
        return 0

    clock = _CLOCK_FORM.fullmatch(body)
    if clock:
        # Fields are [M, SS] or [H, MM, SS]; every field after the first is 00-59.
        fields = [int(f) for f in clock.group(1, 2, 3) if f is not None]
        if any(f > 59 for f in fields[1:]):
            raise ValueError(f"invalid clock duration: {s!r}")
        total = 0
        for f in fields:
            total = total * 60 + f
        return sign * total

    if _UNIT_FORM.fullmatch(body):
        total = Fraction(0)
        last_rank = -1
        for num, unit in _UNIT_PART.findall(body):
            rank = _UNIT_ORDER.index(unit)
            if rank <= last_rank:
                raise ValueError(f"units out of order or repeated: {s!r}")
            last_rank = rank
            total += Fraction(num) * _UNITS[unit]
        if total.denominator != 1:
            raise ValueError(f"duration is not a whole number of seconds: {s!r}")
        return sign * int(total)

    raise ValueError(f"invalid duration: {s!r}")
