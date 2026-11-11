import re
from fractions import Fraction

_UNITS = [("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
_NUM = r"(?:[0-9]+(?:\.[0-9]+)?)"
_UNIT_RE = re.compile(
    r"(?:(%s)w)?(?: ?(%s)d)?(?: ?(%s)h)?(?: ?(%s)m)?(?: ?(%s)s)?" % ((_NUM,) * 5)
)
_CLOCK_RE = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")


def parse_duration(s: str) -> int:
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    t = s.strip(" \t\n\r\f\v")
    if not t:
        raise ValueError("empty duration")
    neg = False
    if t.startswith("-"):
        neg = True
        t = t[1:]
        if t[:1].isspace():
            raise ValueError("space after minus")
    if t == "0" and not neg:
        return 0
    total = None
    m = _CLOCK_RE.fullmatch(t)
    if m:
        a, b, c = m.groups()
        if c is None:
            if int(b) > 59:
                raise ValueError("invalid clock field")
            total = Fraction(int(a) * 60 + int(b))
        else:
            if int(b) > 59 or int(c) > 59:
                raise ValueError("invalid clock field")
            total = Fraction(int(a) * 3600 + int(b) * 60 + int(c))
    else:
        m = _UNIT_RE.fullmatch(t)
        # A space may only separate parts, so it can't lead the string
        if not m or not any(g is not None for g in m.groups()):
            raise ValueError("invalid duration: %r" % (s,))
        total = Fraction(0)
        for g, (_, mult) in zip(m.groups(), _UNITS):
            if g is not None:
                total += Fraction(g) * mult
        if total.denominator != 1:
            raise ValueError("not a whole number of seconds")
    result = int(total)
    return -result if neg else result
