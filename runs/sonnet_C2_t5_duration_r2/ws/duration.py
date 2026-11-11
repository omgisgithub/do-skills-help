import re
from fractions import Fraction

_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(r"%s(?: ?%s)*" % (_PART, _PART))
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")
_SECS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a str")
    t = s.strip()
    neg = t.startswith("-")
    if neg:
        t = t[1:]
    if t == "0":
        return 0
    m = _CLOCK.fullmatch(t)
    if m:
        a, b, c = m.groups()
        total = int(a) * 60 + int(b) if c is None else int(a) * 3600 + int(b) * 60 + int(c)
    elif _UNIT_FORM.fullmatch(t):
        parts = _PART_RE.findall(t)
        idx = [_ORDER.index(u) for _, u in parts]
        if any(x >= y for x, y in zip(idx, idx[1:])):
            raise ValueError("units must strictly decrease: %r" % s)
        total = sum(Fraction(n) * _SECS[u] for n, u in parts)
        if total.denominator != 1:
            raise ValueError("not a whole number of seconds: %r" % s)
        total = int(total)
    else:
        raise ValueError("invalid duration: %r" % s)
    return -total if neg else total


if __name__ == "__main__":
    ok = {"1h30m": 5400, " 2d 4h ": 187200, "1.5h": 5400, "1w2d3h4m5s": 788645, "1:02:03": 3723,
          "-45s": -45, "0": 0, "-0s": 0, "0.1h": 360, "1.5m": 90, "05m": 300, "90:00": 5400,
          "-1:30": -90, "1h 30m": 5400}
    for k, v in ok.items():
        assert parse_duration(k) == v, k
    for k in ["", "  ", "5", "1.5", ".5h", "5.h", "1 h", "30m1h", "1h1h", "1h  30m", "0.3s", "1:60",
              "1:5", "+1h", "1H", "1:30.5", "--1h", "- 1h", "1h\n30m", "1,5h", "٣s"]:
        try:
            parse_duration(k)
        except ValueError:
            continue
        raise AssertionError(k)
    try:
        parse_duration(5)
    except TypeError:
        pass
    else:
        raise AssertionError("TypeError")
    print("ok")
