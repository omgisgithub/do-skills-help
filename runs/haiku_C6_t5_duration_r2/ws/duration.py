import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
# Lower rank means bigger unit, so parts must have strictly increasing rank.
_UNIT_RANK = {"w": 0, "d": 1, "h": 2, "m": 3, "s": 4}

_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(r"%s(?: ?%s)*" % (_PART, _PART))
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_FORM = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def _sum_units(text):
    """Return the exact total seconds of a unit-form string, enforcing unit order."""
    total = Fraction(0)
    last_rank = -1
    for number, unit in _PART_RE.findall(text):
        rank = _UNIT_RANK[unit]
        if rank <= last_rank:
            raise ValueError("units must be strictly decreasing: %r" % text)
        last_rank = rank
        total += Fraction(number) * _UNIT_SECONDS[unit]
    return total


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be str, not %s" % type(s).__name__)

    text = s.strip()
    if text == "0":
        return 0

    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]

    if _CLOCK_FORM.fullmatch(text):
        fields = reversed(text.split(":"))
        total = Fraction(sum(int(f) * m for f, m in zip(fields, (1, 60, 3600))))
    elif _UNIT_FORM.fullmatch(text):
        total = _sum_units(text)
    else:
        raise ValueError("invalid duration: %r" % s)

    if total.denominator != 1:
        raise ValueError("duration is not a whole number of seconds: %r" % s)
    return sign * int(total)
