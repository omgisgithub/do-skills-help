"""Parse human-written timeouts into a whole number of seconds."""

from fractions import Fraction
import re

# Unit -> size in seconds, and a rank used to enforce strictly decreasing order.
_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_UNIT_RANK = {"w": 5, "d": 4, "h": 3, "m": 2, "s": 1}

_PART = r"([0-9]+)(?:\.([0-9]+))?([wdhms])"
_UNIT_FORM_RE = re.compile(r"^" + _PART + r"(?: ?" + _PART + r")*$")
_PART_RE = re.compile(_PART)
_CLOCK_FORM_RE = re.compile(r"^([0-9]+):([0-9]{2})(?::([0-9]{2}))?$")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a string")

    text = s.strip()
    if not text:
        raise ValueError("empty duration")

    negative = text.startswith("-")
    if negative:
        text = text[1:]

    if not text:
        raise ValueError("invalid duration: %r" % s)

    # The only valid bare number is exactly "0" (without a sign).
    if text == "0":
        if negative:
            raise ValueError("invalid duration: %r" % s)
        return 0

    match = _CLOCK_FORM_RE.match(text)
    if match is not None:
        first, second, third = match.groups()
        first = int(first)
        second = int(second)
        if second > 59:
            raise ValueError("invalid duration: %r" % s)
        if third is None:
            total = first * 60 + second
        else:
            third = int(third)
            if third > 59:
                raise ValueError("invalid duration: %r" % s)
            total = first * 3600 + second * 60 + third
        return -total if negative else total

    if _UNIT_FORM_RE.match(text) is None:
        raise ValueError("invalid duration: %r" % s)

    total = Fraction(0)
    previous_rank = 6
    for part in _PART_RE.finditer(text):
        whole, fraction, unit = part.groups()
        rank = _UNIT_RANK[unit]
        if rank >= previous_rank:
            raise ValueError("invalid duration: %r" % s)
        previous_rank = rank

        if fraction is None:
            value = Fraction(int(whole))
        else:
            value = Fraction(int(whole + fraction), 10 ** len(fraction))
        total += value * _UNIT_SECONDS[unit]

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds: %r" % s)

    total = total.numerator
    return -total if negative else total
