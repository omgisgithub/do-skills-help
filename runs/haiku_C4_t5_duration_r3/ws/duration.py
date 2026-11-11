"""Parse human-written durations such as ``1h30m`` or ``1:30:00`` into whole seconds."""

import re
from fractions import Fraction
from typing import Final

_UNIT_SECONDS: Final[dict[str, int]] = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
# Largest unit first, so a unit's position doubles as its rank for the ordering check.
_UNIT_ORDER: Final[tuple[str, ...]] = tuple(_UNIT_SECONDS)
_UNIT_PART_PATTERN: Final = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM: Final = re.compile(rf"{_UNIT_PART_PATTERN}(?: ?{_UNIT_PART_PATTERN})*")
_UNIT_PART: Final = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_FORM: Final = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s: str) -> int:
    """Parse a human-written duration into a whole number of seconds.

    Accepts the unit form (``1h30m``, ``1.5h``, ``2d 4h``) and the clock form
    (``M:SS`` or ``H:MM:SS``). Leading and trailing whitespace is ignored, and an
    optional single leading ``-`` makes the result negative. See TASK.md for the
    full grammar.

    Args:
        s: The duration text to parse.

    Returns:
        The duration in seconds. Negative for a leading ``-``.

    Raises:
        TypeError: If ``s`` is not a ``str``.
        ValueError: If ``s`` does not match the grammar or is not a whole number of seconds.
    """
    if not isinstance(s, str):
        raise TypeError(f"duration must be a str, not {type(s).__name__}")
    text = s.strip()
    if text == "0":
        return 0
    negative = text.startswith("-")
    body = text[1:] if negative else text
    seconds = _parse_unsigned(body)
    return -seconds if negative else seconds


def _parse_unsigned(body: str) -> int:
    """Parse an unsigned duration in either form.

    Args:
        body: Duration text with any sign and surrounding whitespace removed.

    Returns:
        The duration in seconds.

    Raises:
        ValueError: If ``body`` matches neither form.
    """
    clock_match = _CLOCK_FORM.fullmatch(body)
    if clock_match is not None:
        return _parse_clock_form(clock_match)
    return _parse_unit_form(body)


def _parse_clock_form(match: re.Match[str]) -> int:
    """Convert a matched ``H:MM:SS`` or ``M:SS`` duration to seconds.

    Args:
        match: A match of ``_CLOCK_FORM``, whose minute and second fields are already
            validated to be ``00``-``59``.

    Returns:
        The duration in seconds.
    """
    first, second, third = match.groups()
    if third is None:
        return int(first) * 60 + int(second)
    return int(first) * 3600 + int(second) * 60 + int(third)


def _parse_unit_form(body: str) -> int:
    """Sum the ``<number><unit>`` parts of an unsigned unit-form duration.

    Exact rational arithmetic keeps fractional parts such as ``1.5m`` precise. The total
    must come out to a whole number of seconds.

    Args:
        body: Unsigned duration text with surrounding whitespace removed.

    Returns:
        The duration in seconds.

    Raises:
        ValueError: If the grammar is violated, units are out of order or repeated, or
            the total is not a whole number of seconds.
    """
    if _UNIT_FORM.fullmatch(body) is None:
        raise ValueError(f"invalid duration: {body!r}")
    total = Fraction(0)
    previous_rank = -1
    for number, unit in _UNIT_PART.findall(body):
        rank = _UNIT_ORDER.index(unit)
        if rank <= previous_rank:
            raise ValueError(f"units must be strictly decreasing and unique: {body!r}")
        previous_rank = rank
        total += Fraction(number) * _UNIT_SECONDS[unit]
    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {body!r}")
    return int(total)
