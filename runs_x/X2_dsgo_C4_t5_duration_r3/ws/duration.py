"""Parse human-written duration strings into whole seconds."""

from fractions import Fraction
import re

# Unit sizes in seconds, ordered from largest to smallest.
_UNIT_SECONDS = {
    "w": 604800,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}
_UNIT_INDEX = {unit: index for index, unit in enumerate(_UNIT_SECONDS)}

# A single <number><unit> part, e.g. "1.5h".
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
# One or more parts written together, e.g. "1h30m".
_UNIT_TOKEN_RE = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?[wdhms])+")
# Clock form, e.g. "1:30" or "1:02:03".
_CLOCK_RE = re.compile(r"[0-9]+(?::[0-9]{2}){1,2}")


def parse_duration(s):
    """Parse a human-written duration into a whole number of seconds.

    Supports the unit form (``1h30m``, ``2d 4h``) and the clock form
    (``M:SS``, ``H:MM:SS``). A single leading ``-`` makes the result
    negative. The bare string ``"0"`` means zero.

    Args:
        s: The duration string to parse.

    Returns:
        The duration in whole seconds.

    Raises:
        TypeError: If ``s`` is not a string.
        ValueError: If ``s`` does not match the accepted grammar.
    """
    if not isinstance(s, str):
        raise TypeError(f"duration must be a str, not {type(s).__name__}")

    text = s.strip()
    if not text:
        raise ValueError("duration must not be empty")

    is_negative = text.startswith("-")
    if is_negative:
        text = text[1:]
        if not text:
            raise ValueError("duration must not be only a sign")

    if text == "0":
        return 0

    if ":" in text:
        seconds = _parse_clock(text)
    else:
        seconds = _parse_units(text)

    return -seconds if is_negative else seconds


def _parse_units(text):
    """Parse the unit form of a duration into whole seconds.

    Args:
        text: The duration without surrounding whitespace or sign.

    Returns:
        The duration in whole seconds.

    Raises:
        ValueError: If ``text`` is not a valid unit-form duration.
    """
    total = Fraction(0)
    last_index = -1

    for token in text.split(" "):
        if not token or _UNIT_TOKEN_RE.fullmatch(token) is None:
            raise ValueError(f"invalid duration: {text!r}")
        for number, unit in _PART_RE.findall(token):
            index = _UNIT_INDEX[unit]
            if index <= last_index:
                raise ValueError(f"units out of order or repeated: {text!r}")
            last_index = index
            total += Fraction(number) * _UNIT_SECONDS[unit]

    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {text!r}")

    return int(total)


def _parse_clock(text):
    """Parse the clock form of a duration into whole seconds.

    Args:
        text: The duration without surrounding whitespace or sign.

    Returns:
        The duration in whole seconds.

    Raises:
        ValueError: If ``text`` is not a valid clock-form duration.
    """
    if _CLOCK_RE.fullmatch(text) is None:
        raise ValueError(f"invalid duration: {text!r}")

    fields = [int(field) for field in text.split(":")]
    if any(value > 59 for value in fields[1:]):
        raise ValueError(f"clock fields out of range: {text!r}")

    if len(fields) == 2:
        minutes, seconds = fields
        return minutes * 60 + seconds

    hours, minutes, seconds = fields
    return hours * 3600 + minutes * 60 + seconds
