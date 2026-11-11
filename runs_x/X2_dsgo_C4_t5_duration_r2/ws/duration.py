"""Parse human-written durations into whole seconds.

The accepted grammar is defined in ``TASK.md``. Two forms are supported: a
unit form (``"1h30m"``) and a clock form (``"1:02:03"``).

Example:
    >>> parse_duration("1h30m")
    5400
"""

import re
from fractions import Fraction
from typing import Optional

_UNIT_SECONDS = {
    "w": 604800,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}

# Larger rank means a larger unit. Parts must use strictly decreasing ranks.
_UNIT_RANK = {
    "w": 5,
    "d": 4,
    "h": 3,
    "m": 2,
    "s": 1,
}

_UNIT_PART_RE = re.compile(r"(\d+(?:\.\d+)?)([wdhms])")
_CLOCK_RE = re.compile(r"(\d+):(\d{2})(?::(\d{2}))?")


def _parse_unit_form(text: str) -> int:
    """Parse the unit form, e.g. ``"1h 30m"``.

    Args:
        text: The duration without a sign or surrounding whitespace.

    Returns:
        The duration in whole seconds.

    Raises:
        ValueError: If the text does not match the unit grammar, uses units
            more than once or out of order, or is not a whole number of
            seconds.
    """
    total = Fraction(0)
    last_rank: Optional[int] = None
    pos = 0

    while pos < len(text):
        match = _UNIT_PART_RE.match(text, pos)
        if match is None:
            raise ValueError(f"invalid duration part at position {pos}: {text!r}")

        number, unit = match.group(1), match.group(2)
        rank = _UNIT_RANK[unit]
        if last_rank is not None and rank >= last_rank:
            raise ValueError(f"units must decrease and appear once: {text!r}")
        last_rank = rank

        total += Fraction(number) * _UNIT_SECONDS[unit]
        pos = match.end()

        if pos < len(text):
            if text[pos] != " ":
                continue
            pos += 1
            if pos == len(text) or text[pos] == " ":
                raise ValueError(f"invalid separator in {text!r}")

    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {text!r}")

    return total.numerator


def _parse_clock_form(text: str) -> int:
    """Parse the clock form, e.g. ``"1:02:03"`` or ``"45:00"``.

    Args:
        text: The duration without a sign or surrounding whitespace.

    Returns:
        The duration in whole seconds.

    Raises:
        ValueError: If the text does not match the clock grammar.
    """
    match = _CLOCK_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid clock duration: {text!r}")

    first, second, third = match.groups()
    if third is None:
        minutes, seconds = int(first), int(second)
        if seconds > 59:
            raise ValueError(f"seconds out of range: {text!r}")
        return minutes * 60 + seconds

    hours, minutes, seconds = int(first), int(second), int(third)
    if minutes > 59 or seconds > 59:
        raise ValueError(f"minutes or seconds out of range: {text!r}")
    return hours * 3600 + minutes * 60 + seconds


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds.

    Args:
        s: The duration to parse. Leading and trailing whitespace is ignored,
            and an optional single leading ``-`` negates the result.

    Returns:
        The duration in whole seconds.

    Raises:
        TypeError: If ``s`` is not a string.
        ValueError: If ``s`` is empty or does not match the accepted grammar,
            or if the unit form is not a whole number of seconds.

    Example:
        >>> parse_duration(" 2d 4h ")
        187200
    """
    if not isinstance(s, str):
        raise TypeError(f"duration must be a str, not {type(s).__name__}")

    text = s.strip()
    if not text:
        raise ValueError("duration is empty")

    is_negative = text.startswith("-")
    if is_negative:
        text = text[1:]
        if not text:
            raise ValueError(f"invalid duration: {s!r}")

    if text == "0":
        return 0

    if ":" in text:
        seconds = _parse_clock_form(text)
    else:
        seconds = _parse_unit_form(text)

    return -seconds if is_negative else seconds
