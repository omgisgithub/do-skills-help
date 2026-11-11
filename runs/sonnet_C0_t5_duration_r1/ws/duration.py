import re
from fractions import Fraction

_UNITS = (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
_PART = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_FORM = re.compile(
    r"(?:({n})w)?(?: ?({n})d)?(?: ?({n})h)?(?: ?({n})m)?(?: ?({n})s)?".format(n=_PART)
)
_CLOCK_FORM = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s: str) -> int:
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    text = s.strip()
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    if not text or text[0].isspace():
        raise ValueError("empty duration")

    total = None
    if text == "0":
        total = Fraction(0)
    else:
        m = _CLOCK_FORM.fullmatch(text)
        if m:
            if m.group(3) is None:
                total = int(m.group(1)) * 60 + int(m.group(2))
            else:
                total = (int(m.group(1)) * 3600 + int(m.group(2)) * 60
                         + int(m.group(3)))
        else:
            m = _UNIT_FORM.fullmatch(text)
            if m and any(m.groups()):
                total = sum(
                    Fraction(g) * mult
                    for g, (_, mult) in zip(m.groups(), _UNITS)
                    if g is not None
                )
    if total is None:
        raise ValueError("invalid duration: %r" % (s,))
    if Fraction(total).denominator != 1:
        raise ValueError("duration is not a whole number of seconds: %r" % (s,))
    total = int(total)
    return -total if negative else total
