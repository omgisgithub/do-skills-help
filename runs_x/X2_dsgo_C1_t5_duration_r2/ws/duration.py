"""Parse human-written durations into whole seconds."""

import re
from fractions import Fraction

_UNIT_SECONDS = {
    "w": 604800,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}

_UNIT_ORDER = {"w": 0, "d": 1, "h": 2, "m": 3, "s": 4}

_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_RE = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")


def _parse_unit_form(text):
    """Parse Form A (e.g. ``1h30m``) into seconds."""
    parts = []
    pos = 0
    for match in _PART_RE.finditer(text):
        gap = text[pos:match.start()]
        if gap not in ("", " "):
            raise ValueError("invalid duration: %r" % text)
        parts.append((match.group(1), match.group(2)))
        pos = match.end()

    if not parts or pos != len(text):
        raise ValueError("invalid duration: %r" % text)

    previous_rank = -1
    total = Fraction(0)
    for number, unit in parts:
        rank = _UNIT_ORDER[unit]
        if rank <= previous_rank:
            raise ValueError("invalid duration: %r" % text)
        previous_rank = rank
        total += Fraction(number) * _UNIT_SECONDS[unit]

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds: %r" % text)

    return int(total)


def _parse_clock_form(text):
    """Parse Form B (``H:MM:SS`` or ``M:SS``) into seconds."""
    match = _CLOCK_RE.fullmatch(text)
    if match is None:
        raise ValueError("invalid duration: %r" % text)

    first, second, third = match.groups()
    if third is None:
        minutes = int(first)
        seconds = int(second)
        if seconds > 59:
            raise ValueError("invalid duration: %r" % text)
        return minutes * 60 + seconds

    hours = int(first)
    minutes = int(second)
    seconds = int(third)
    if minutes > 59 or seconds > 59:
        raise ValueError("invalid duration: %r" % text)
    return hours * 3600 + minutes * 60 + seconds


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    text = s.strip()
    if not text:
        raise ValueError("invalid duration: %r" % s)

    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]

    if not text:
        raise ValueError("invalid duration: %r" % s)

    if text[0].isspace():
        raise ValueError("invalid duration: %r" % s)

    if text == "0":
        return 0

    if ":" in text:
        return sign * _parse_clock_form(text)

    return sign * _parse_unit_form(text)
