import re
from fractions import Fraction

_UNIT_SECONDS = {
    "w": 604800,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}

# Ranks decrease in the same order as the units are allowed to appear.
_UNIT_RANKS = {"w": 5, "d": 4, "h": 3, "m": 2, "s": 1}

_NUMBER_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_CLOCK_RE = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def _parse_unit_form(text: str) -> Fraction:
    """Parse Form A and return the exact duration in seconds."""
    total = Fraction(0)
    last_rank = len(_UNIT_RANKS) + 1
    index = 0

    while index < len(text):
        number_match = _NUMBER_RE.match(text, index)
        if number_match is None:
            raise ValueError("invalid duration")
        number_text = number_match.group(0)
        index = number_match.end()

        if index == len(text):
            raise ValueError("invalid duration")
        unit = text[index]
        if unit not in _UNIT_SECONDS:
            raise ValueError("invalid duration")
        index += 1

        rank = _UNIT_RANKS[unit]
        if rank >= last_rank:
            raise ValueError("invalid duration")
        last_rank = rank

        whole, dot, fraction = number_text.partition(".")
        if dot:
            numerator = int(whole + fraction)
            denominator = 10 ** len(fraction)
        else:
            numerator = int(whole)
            denominator = 1
        total += Fraction(numerator * _UNIT_SECONDS[unit], denominator)

        if index == len(text):
            break
        if text[index] == " ":
            index += 1
            if index == len(text):
                raise ValueError("invalid duration")

    if total.denominator != 1:
        raise ValueError("invalid duration")
    return total


def _parse_clock_form(text: str) -> int:
    """Parse Form B and return the duration in seconds."""
    if _CLOCK_RE.fullmatch(text) is None:
        raise ValueError("invalid duration")

    fields = [int(field) for field in text.split(":")]
    if len(fields) == 2:
        minutes, seconds = fields
        return minutes * 60 + seconds

    hours, minutes, seconds = fields
    return hours * 3600 + minutes * 60 + seconds


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md.

    Args:
        s: A duration in unit form (for example ``1h30m``) or clock form
            (for example ``1:30``).

    Returns:
        The duration as a whole number of seconds. Negative durations are
        returned as negative integers.

    Raises:
        TypeError: If ``s`` is not a string.
        ValueError: If ``s`` is not a valid duration.
    """
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    text = s.strip()
    if not text:
        raise ValueError("invalid duration")

    is_negative = text.startswith("-")
    if is_negative:
        text = text[1:]
        if not text:
            raise ValueError("invalid duration")

    if text == "0":
        seconds = 0
    elif ":" in text:
        seconds = _parse_clock_form(text)
    else:
        seconds = _parse_unit_form(text)

    return -seconds if is_negative else seconds
