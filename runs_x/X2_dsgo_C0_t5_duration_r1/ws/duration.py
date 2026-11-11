import re
from fractions import Fraction

_UNIT_SECONDS = {
    "w": 604800,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}

# Larger units have larger ranks. Form A requires strictly decreasing ranks.
_UNIT_RANK = {"w": 5, "d": 4, "h": 3, "m": 2, "s": 1}

_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_PART = _NUMBER + r"[wdhms]"

_FORM_A_RE = re.compile(r"^" + _UNIT_PART + r"(?: ?" + _UNIT_PART + r")*$")
_PART_RE = re.compile(r"(" + _NUMBER + r")([wdhms])")
_FORM_B_RE = re.compile(r"^([0-9]+):([0-9]{2})(?::([0-9]{2}))?$")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("parse_duration() requires a string")

    text = s.strip()
    if not text:
        raise ValueError("empty duration")

    negative = False
    if text.startswith("-"):
        negative = True
        text = text[1:]

    # The bare string "0" is the only allowed bare number.
    if text == "0":
        return 0

    if not text:
        raise ValueError("invalid duration")

    match = _FORM_B_RE.match(text)
    if match is not None:
        first = int(match.group(1))
        second = int(match.group(2))
        third = match.group(3)

        if third is None:
            # M:SS
            if second > 59:
                raise ValueError("invalid duration")
            total = first * 60 + second
        else:
            # H:MM:SS
            seconds = int(third)
            if second > 59 or seconds > 59:
                raise ValueError("invalid duration")
            total = first * 3600 + second * 60 + seconds

        return -total if negative else total

    if _FORM_A_RE.match(text) is not None:
        previous_rank = None
        total = Fraction(0)

        for number, unit in _PART_RE.findall(text):
            rank = _UNIT_RANK[unit]
            if previous_rank is not None and rank >= previous_rank:
                raise ValueError("units must be strictly decreasing")
            previous_rank = rank
            total += Fraction(number) * _UNIT_SECONDS[unit]

        if total.denominator != 1:
            raise ValueError("duration must be a whole number of seconds")

        result = int(total)
        return -result if negative else result

    raise ValueError("invalid duration")
