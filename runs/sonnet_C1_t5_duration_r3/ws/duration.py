import re
from fractions import Fraction

_UNITS = [("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
_UNIT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK_RE = re.compile(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?")
_ASCII_WS = " \t\n\r\f\v"


def parse_duration(s: str) -> int:
    if not isinstance(s, str):
        raise TypeError("parse_duration expects a str")
    t = s.strip(_ASCII_WS)
    if not t:
        raise ValueError("empty duration")
    neg = False
    if t.startswith("-"):
        neg = True
        t = t[1:]
    if not t:
        raise ValueError("invalid duration")

    if t == "0":
        total = 0
    elif ":" in t:
        m = _CLOCK_RE.fullmatch(t)
        if not m or not m.group(1).isascii():
            raise ValueError("invalid clock duration")
        a, b, c = m.groups()
        if c is None:
            mins, secs = int(a), int(b)
            if secs > 59:
                raise ValueError("invalid seconds")
            total = mins * 60 + secs
        else:
            hrs, mins, secs = int(a), int(b), int(c)
            if mins > 59 or secs > 59:
                raise ValueError("invalid minutes/seconds")
            total = hrs * 3600 + mins * 60 + secs
    else:
        pos = 0
        last = -1
        acc = Fraction(0)
        order = {u: i for i, (u, _) in enumerate(_UNITS)}
        mult = dict(_UNITS)
        while True:
            m = _UNIT_RE.match(t, pos)
            if not m:
                raise ValueError("invalid duration")
            idx = order[m.group(2)]
            if idx <= last:
                raise ValueError("units out of order or repeated")
            last = idx
            acc += Fraction(m.group(1)) * mult[m.group(2)]
            pos = m.end()
            if pos == len(t):
                break
            if t[pos] == " ":
                pos += 1
        if acc.denominator != 1:
            raise ValueError("not a whole number of seconds")
        total = int(acc)
    return -total if neg else total
