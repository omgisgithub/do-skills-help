import re
from fractions import Fraction

UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
# Index order matches size order: earlier units are larger.
UNIT_ORDER = "wdhms"

_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_UNIT_FORM = re.compile(r"[0-9]+(?:\.[0-9]+)?[wdhms](?: ?[0-9]+(?:\.[0-9]+)?[wdhms])*")
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def _unit_total(s: str, text: str) -> int:
    total = Fraction(0)
    last_rank = -1
    for number, unit in _PART.findall(text):
        rank = UNIT_ORDER.index(unit)
        if rank <= last_rank:
            raise ValueError(f"units must be strictly decreasing: {s!r}")
        last_rank = rank
        total += Fraction(number) * UNIT_SECONDS[unit]
    if total.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {s!r}")
    return total.numerator


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a str")
    text = s.strip()
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    if text == "0":
        return 0
    clock = _CLOCK_FORM.fullmatch(text)
    if clock:
        first, second, third = clock.groups()
        if third is None:
            total = int(first) * 60 + int(second)
        else:
            total = int(first) * 3600 + int(second) * 60 + int(third)
    elif _UNIT_FORM.fullmatch(text):
        total = _unit_total(s, text)
    else:
        raise ValueError(f"invalid duration: {s!r}")
    return -total if negative else total
