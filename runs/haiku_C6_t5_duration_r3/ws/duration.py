import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
# Units must appear in this order (largest first), each at most once.
_UNIT_ORDER = "wdhms"
_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_FORM = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a str")

    text = s.strip()
    if text == "0":
        return 0

    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]

    if _CLOCK_FORM.fullmatch(text):
        # Fields are M:SS or H:MM:SS; zip pairs the seconds field with weight 1.
        total = sum(
            int(field) * weight
            for field, weight in zip(reversed(text.split(":")), (1, 60, 3600))
        )
    elif _UNIT_FORM.fullmatch(text):
        total = Fraction(0)
        last_rank = -1
        for number, unit in _PART_RE.findall(text):
            rank = _UNIT_ORDER.index(unit)
            if rank <= last_rank:
                raise ValueError("units must be strictly decreasing and unique: %r" % s)
            last_rank = rank
            total += Fraction(number) * _UNIT_SECONDS[unit]
        if total.denominator != 1:
            raise ValueError("duration is not a whole number of seconds: %r" % s)
        total = int(total)
    else:
        raise ValueError("invalid duration: %r" % s)

    return sign * total
