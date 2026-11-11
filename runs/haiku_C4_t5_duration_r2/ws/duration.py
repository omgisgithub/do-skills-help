import re
from fractions import Fraction

# Units in strictly decreasing size; the position in this string is the order rank.
_UNITS = "wdhms"
_SECONDS_PER_UNIT = {"w": 604_800, "d": 86_400, "h": 3_600, "m": 60, "s": 1}

# ASCII-only character classes: `\d` would also match non-ASCII digits.
_UNIT_PART = r"([0-9]+(?:\.[0-9]+)?)([wdhms])"
_UNIT_FORM = re.compile(rf"{_UNIT_PART}(?: ?{_UNIT_PART})*")
_CLOCK_FORM = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")


def parse_duration(s: str) -> int:
    """Parse a human-written duration into a whole number of seconds.

    Accepts the unit form (``1h30m``, ``1.5h``) and the clock form (``1:02:03``,
    ``90:00``), each with an optional leading ``-``. The bare string ``0`` is also valid.

    Args:
        s: The duration text. Leading and trailing whitespace is ignored.

    Returns:
        The duration in seconds. Negative for a leading ``-``.

    Raises:
        TypeError: If ``s`` is not a ``str``.
        ValueError: If ``s`` is not a valid duration, or does not amount to whole seconds.
    """
    if not isinstance(s, str):
        raise TypeError(f"duration must be str, not {type(s).__name__}")
    text = s.strip()
    is_negative = text.startswith("-")
    body = text[1:] if is_negative else text
    if body == "0":
        return 0
    seconds = _parse_clock(body, s) if ":" in body else _parse_units(body, s)
    return -seconds if is_negative else seconds


def _parse_units(body: str, original: str) -> int:
    """Parse the unit form, such as ``1h 30m``, into seconds.

    Args:
        body: The duration text without its sign or surrounding whitespace.
        original: The caller's input, used only for error messages.

    Returns:
        The total number of seconds.

    Raises:
        ValueError: If the form is malformed, units are out of order or repeated,
            or the total is not a whole number of seconds.
    """
    if _UNIT_FORM.fullmatch(body) is None:
        raise ValueError(f"invalid duration: {original!r}")
    total = Fraction(0)
    last_rank = -1
    for number, unit in re.findall(_UNIT_PART, body):
        rank = _UNITS.index(unit)
        if rank <= last_rank:
            raise ValueError(f"units must be strictly decreasing and unique: {original!r}")
        last_rank = rank
        total += Fraction(number) * _SECONDS_PER_UNIT[unit]
    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {original!r}")
    return int(total)


def _parse_clock(body: str, original: str) -> int:
    """Parse the clock form, ``H:MM:SS`` or ``M:SS``, into seconds.

    Args:
        body: The duration text without its sign or surrounding whitespace.
        original: The caller's input, used only for error messages.

    Returns:
        The total number of seconds.

    Raises:
        ValueError: If the form is malformed or a field after the first is not 00-59.
    """
    match = _CLOCK_FORM.fullmatch(body)
    if match is None:
        raise ValueError(f"invalid duration: {original!r}")
    first, second, third = match.groups()
    if third is None:
        hours, minutes, seconds = 0, int(first), int(second)
    else:
        hours, minutes, seconds = int(first), int(second), int(third)
        if minutes > 59:
            raise ValueError(f"minutes must be 00-59: {original!r}")
    if seconds > 59:
        raise ValueError(f"seconds must be 00-59: {original!r}")
    return hours * 3600 + minutes * 60 + seconds
