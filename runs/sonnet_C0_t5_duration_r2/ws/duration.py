import re
from fractions import Fraction

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"
_NUM = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_RE = re.compile(r"(%s)([wdhms])" % _NUM)
_FORM_A = re.compile(r"(?:%s[wdhms])(?: ?%s[wdhms])*" % (_NUM, _NUM))
_CLOCK = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")


def parse_duration(s: str) -> int:
    if not isinstance(s, str):
        raise TypeError("parse_duration expects str")
    # strip only ASCII-ish whitespace consistent with str.strip()
    t = s.strip()
    if not t:
        raise ValueError("empty duration")
    neg = False
    if t.startswith("-"):
        neg = True
        t = t[1:]
    if t == "0":
        return 0

    m = _CLOCK.fullmatch(t)
    if m:
        a, b, c = m.groups()
        if c is None:
            total = int(a) * 60 + int(b)
        else:
            total = int(a) * 3600 + int(b) * 60 + int(c)
        return -total if neg else total

    if not _FORM_A.fullmatch(t):
        raise ValueError("invalid duration: %r" % s)
    total = Fraction(0)
    last = -1
    for num, unit in _UNIT_RE.findall(t):
        idx = _ORDER.index(unit)
        if idx <= last:
            raise ValueError("units out of order or repeated: %r" % s)
        last = idx
        total += Fraction(num) * _UNITS[unit]
    if total.denominator != 1:
        raise ValueError("not a whole number of seconds: %r" % s)
    total = int(total)
    return -total if neg else total
