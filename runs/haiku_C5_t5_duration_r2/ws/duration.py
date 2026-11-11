import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_ORDER = "wdhms"

_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_PART = _NUMBER + r"[wdhms]"
_UNIT_FORM = re.compile(_UNIT_PART + r"(?: ?" + _UNIT_PART + r")*")
_UNIT_PART_RE = re.compile(r"(" + _NUMBER + r")([wdhms])")
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def _unit_total(body):
    """Seconds for a unit-form body such as '1h 30m', as an exact Fraction."""
    if not _UNIT_FORM.fullmatch(body):
        raise ValueError(f"invalid duration: {body!r}")
    total = Fraction(0)
    last_rank = -1
    for number, unit in _UNIT_PART_RE.findall(body):
        rank = _UNIT_ORDER.index(unit)
        if rank <= last_rank:
            raise ValueError(f"units out of order or repeated: {body!r}")
        last_rank = rank
        total += Fraction(number) * _UNIT_SECONDS[unit]
    return total


def _clock_total(body):
    """Seconds for a clock-form body such as '1:02:03' or '1:30', as an exact Fraction."""
    match = _CLOCK_FORM.fullmatch(body)
    if not match:
        raise ValueError(f"invalid duration: {body!r}")
    hours_or_minutes, minutes_or_seconds, seconds = match.groups()
    if seconds is None:
        return Fraction(int(hours_or_minutes) * 60 + int(minutes_or_seconds))
    return Fraction(
        int(hours_or_minutes) * 3600 + int(minutes_or_seconds) * 60 + int(seconds)
    )


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")

    text = s.strip()
    if not text:
        raise ValueError("empty duration")

    negative = text.startswith("-")
    body = text[1:] if negative else text
    if not body:
        raise ValueError(f"invalid duration: {s!r}")

    if text == "0":
        return 0

    if ":" in body:
        total = _clock_total(body)
    else:
        total = _unit_total(body)

    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {s!r}")

    result = int(total)
    return -result if negative else result
