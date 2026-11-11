import re
from fractions import Fraction

_UNITS = (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
_UNIT_SECONDS = dict(_UNITS)
_UNIT_ORDER = {name: i for i, (name, _) in enumerate(_UNITS)}

_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(rf"{_PART}(?: ?{_PART})*")
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_FORM = re.compile(r"(?:([0-9]+):([0-9]{2}):([0-9]{2})|([0-9]+):([0-9]{2}))")


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    text = s.strip()
    sign = 1
    if text.startswith("-"):
        sign = -1
        text = text[1:]
    if not text:
        raise ValueError(f"invalid duration: {s!r}")
    if text == "0":
        return 0
    if _CLOCK_FORM.fullmatch(text):
        return sign * _parse_clock(text, s)
    if _UNIT_FORM.fullmatch(text):
        return sign * _parse_units(text, s)
    raise ValueError(f"invalid duration: {s!r}")


def _parse_clock(text, original):
    fields = [int(f) for f in text.split(":")]
    if any(f > 59 for f in fields[1:]):
        raise ValueError(f"invalid duration: {original!r}")
    total = 0
    for f in fields:
        total = total * 60 + f
    return total


def _parse_units(text, original):
    total = Fraction(0)
    last = -1
    for number, unit in _PART_RE.findall(text):
        order = _UNIT_ORDER[unit]
        if order <= last:
            raise ValueError(f"invalid duration: {original!r}")
        last = order
        total += Fraction(number) * _UNIT_SECONDS[unit]
    if total.denominator != 1:
        raise ValueError(f"invalid duration: {original!r}")
    return int(total)
