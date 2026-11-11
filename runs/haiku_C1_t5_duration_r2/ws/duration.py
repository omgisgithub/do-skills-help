import re
from fractions import Fraction

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
# Lower rank = larger unit. Units must appear with strictly increasing rank.
_UNIT_RANK = {"w": 0, "d": 1, "h": 2, "m": 3, "s": 4}

_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(_PART + r"(?: ?" + _PART + r")*")
_UNIT_PART = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_FORM = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def _parse_units(body):
    total = Fraction(0)
    last_rank = -1
    for number, unit in _UNIT_PART.findall(body):
        rank = _UNIT_RANK[unit]
        if rank <= last_rank:
            raise ValueError(f"units out of order or repeated: {body!r}")
        last_rank = rank
        total += Fraction(number) * _UNIT_SECONDS[unit]
    return total


def _parse_clock(body):
    total = 0
    for field in body.split(":"):
        total = total * 60 + int(field)
    return Fraction(total)


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"duration must be str, not {type(s).__name__}")
    body = s.strip()
    negative = body.startswith("-")
    if negative:
        body = body[1:]

    if body == "0":
        seconds = Fraction(0)
    elif _UNIT_FORM.fullmatch(body):
        seconds = _parse_units(body)
    elif _CLOCK_FORM.fullmatch(body):
        seconds = _parse_clock(body)
    else:
        raise ValueError(f"invalid duration: {s!r}")

    if negative:
        seconds = -seconds
    if seconds.denominator != 1:
        raise ValueError(f"duration is not a whole number of seconds: {s!r}")
    return int(seconds)
