"""Parsing of human-written durations into whole seconds."""

import re
from fractions import Fraction

_UNIT_SECONDS = {
    "w": 604800,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}

# Larger units sort first; parts of the unit form must be strictly decreasing.
_UNIT_RANK = {"w": 5, "d": 4, "h": 3, "m": 2, "s": 1}

_UNIT_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_RE = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")


def _parse_unit_form(text):
    """Parse the unit form (``1h 30m``) into a Fraction of seconds."""
    total = Fraction(0)
    previous_rank = None

    # Splitting on a single space means repeated or non-space whitespace is
    # rejected below, since the resulting token will not match. A token may
    # itself contain several touching parts, such as ``1h30m``.
    for token in text.split(" "):
        matches = list(_UNIT_PART_RE.finditer(token))
        if not matches or "".join(m.group(0) for m in matches) != token:
            raise ValueError("invalid duration: %r" % text)

        for match in matches:
            number_text, unit = match.groups()
            rank = _UNIT_RANK[unit]
            if previous_rank is not None and rank >= previous_rank:
                raise ValueError("invalid duration: %r" % text)
            previous_rank = rank

            number = Fraction(number_text)
            total += number * _UNIT_SECONDS[unit]

    return total


def _parse_clock_form(text):
    """Parse the clock form (``H:MM:SS`` or ``M:SS``) into a Fraction of seconds."""
    match = _CLOCK_RE.fullmatch(text)
    if match is None:
        raise ValueError("invalid duration: %r" % text)

    first, second, third = match.groups()
    if third is None:
        # M:SS
        minutes = int(first)
        seconds = int(second)
        if seconds > 59:
            raise ValueError("invalid duration: %r" % text)
        return Fraction(minutes * 60 + seconds)

    # H:MM:SS
    hours = int(first)
    minutes = int(second)
    seconds = int(third)
    if minutes > 59 or seconds > 59:
        raise ValueError("invalid duration: %r" % text)
    return Fraction(hours * 3600 + minutes * 60 + seconds)


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string, not %s" % type(s).__name__)

    text = s.strip()
    if not text:
        raise ValueError("empty duration")

    negative = False
    if text.startswith("-"):
        negative = True
        text = text[1:]
        if not text:
            raise ValueError("invalid duration: %r" % s)

    if text == "0":
        return 0

    if ":" in text:
        total = _parse_clock_form(text)
    else:
        total = _parse_unit_form(text)

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds: %r" % s)

    seconds = int(total)
    return -seconds if negative else seconds
