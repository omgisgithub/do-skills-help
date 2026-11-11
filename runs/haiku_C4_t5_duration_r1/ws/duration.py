"""Parse human-written durations such as ``1h30m`` or ``1:30:00`` into seconds."""

import re
from fractions import Fraction
from typing import Final

_UNIT_SECONDS: Final = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
# Ordered from largest to smallest, so a unit's index doubles as its size rank.
_UNITS: Final = tuple(_UNIT_SECONDS)

# ``[0-9]`` rather than ``\d`` because ``\d`` also matches non-ASCII digits.
_NUMBER: Final = r"[0-9]+(?:\.[0-9]+)?"
_PART: Final = rf"{_NUMBER}[wdhms]"
_UNIT_FORM_RE: Final = re.compile(rf"{_PART}(?: ?{_PART})*")
_PART_RE: Final = re.compile(rf"({_NUMBER})([wdhms])")
_CLOCK_RE: Final = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s: str) -> int:
    """Parse a human-written duration into a whole number of seconds.

    Accepts the unit form (``1h30m``, ``1.5h``, ``1w2d``) and the clock form
    (``1:30``, ``1:02:03``). Leading and trailing whitespace is ignored, and an
    optional leading ``-`` makes the result negative.

    Args:
        s: The duration text to parse.

    Returns:
        The duration in seconds.

    Raises:
        TypeError: If ``s`` is not a string.
        ValueError: If ``s`` is not a valid duration, or does not amount to a
            whole number of seconds.
    """
    if not isinstance(s, str):
        raise TypeError(f"duration must be a str, not {type(s).__name__}")
    body = s.strip()
    is_negative = body.startswith("-")
    if is_negative:
        body = body[1:]
    seconds = _parse_unsigned(body)
    return -seconds if is_negative else seconds


def _parse_unsigned(text: str) -> int:
    """Parse a duration with no sign and no surrounding whitespace.

    Args:
        text: The unsigned duration text.

    Returns:
        The duration in seconds.

    Raises:
        ValueError: If ``text`` matches neither the unit form nor the clock form.
    """
    if text == "0":
        return 0
    if clock_match := _CLOCK_RE.fullmatch(text):
        return _clock_seconds(clock_match)
    if _UNIT_FORM_RE.fullmatch(text):
        return _unit_form_seconds(text)
    raise ValueError(f"invalid duration: {text!r}")


def _clock_seconds(match: re.Match[str]) -> int:
    """Convert a matched ``H:MM:SS`` or ``M:SS`` clock string into seconds.

    Args:
        match: A match of ``_CLOCK_RE``.

    Returns:
        The duration in seconds.
    """
    first, second, third = match.groups()
    if third is None:
        return int(first) * 60 + int(second)
    return int(first) * 3600 + int(second) * 60 + int(third)


def _unit_form_seconds(text: str) -> int:
    """Sum the ``<number><unit>`` parts of a unit-form duration.

    Args:
        text: A unit-form duration already validated against ``_UNIT_FORM_RE``.

    Returns:
        The duration in seconds.

    Raises:
        ValueError: If units are not in strictly decreasing size, or the total
            is not a whole number of seconds.
    """
    total = Fraction(0)
    previous_rank = -1
    for number, unit in _PART_RE.findall(text):
        rank = _UNITS.index(unit)
        if rank <= previous_rank:
            raise ValueError(f"units must be in decreasing order, each at most once: {text!r}")
        previous_rank = rank
        total += Fraction(number) * _UNIT_SECONDS[unit]
    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {text!r}")
    return total.numerator
