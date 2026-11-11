import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
# Units must appear in this order (strictly decreasing size).
_UNIT_ORDER = "wdhms"
_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_PART = rf"{_NUMBER}[wdhms]"
_UNIT_FORM = re.compile(rf"{_PART}(?: ?{_PART})*")
_PART_RE = re.compile(rf"({_NUMBER})([wdhms])")
_CLOCK_FORM = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")

    body = s.strip()
    sign = 1
    if body.startswith("-"):
        sign = -1
        body = body[1:]

    if body == "0":
        return 0

    if _CLOCK_FORM.fullmatch(body):
        total = 0
        for field in body.split(":"):
            total = total * 60 + int(field)
        return sign * total

    if _UNIT_FORM.fullmatch(body):
        total = Fraction(0)
        last_rank = -1
        for number, unit in _PART_RE.findall(body):
            rank = _UNIT_ORDER.index(unit)
            if rank <= last_rank:
                raise ValueError(f"units out of order or repeated: {s!r}")
            last_rank = rank
            total += Fraction(number) * _UNIT_SECONDS[unit]
        if total.denominator != 1:
            raise ValueError(f"not a whole number of seconds: {s!r}")
        return sign * int(total)

    raise ValueError(f"invalid duration: {s!r}")
