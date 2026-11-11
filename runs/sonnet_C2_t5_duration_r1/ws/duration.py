import re
from fractions import Fraction

_PART = r"[0-9]+(?:\.[0-9]+)?[wdhms]"
_UNIT_FORM = re.compile(f"{_PART}(?: ?{_PART})*")
_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([wdhms])")
_CLOCK = re.compile(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?")
_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "wdhms"


def parse_duration(s):
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a str")
    s = s.strip()
    sign = 1
    if s.startswith("-"):
        sign, s = -1, s[1:]
    if s == "0":
        return 0

    if _UNIT_FORM.fullmatch(s):
        parts = _PART_RE.findall(s)
        units = [u for _, u in parts]
        idx = [_ORDER.index(u) for u in units]
        if any(a >= b for a, b in zip(idx, idx[1:])):
            raise ValueError(f"units out of order or repeated: {s!r}")
        total = sum(Fraction(n) * _SECONDS[u] for n, u in parts)
        if total.denominator != 1:
            raise ValueError(f"not a whole number of seconds: {s!r}")
        return sign * int(total)

    m = _CLOCK.fullmatch(s)
    if m:
        a, b, c = m.groups()
        if c is None:
            return sign * (int(a) * 60 + int(b))
        return sign * (int(a) * 3600 + int(b) * 60 + int(c))

    raise ValueError(f"invalid duration: {s!r}")


if __name__ == "__main__":
    ok = {"1h30m": 5400, " 2d 4h ": 187200, "1.5h": 5400, "1w2d3h4m5s": 788645,
          "1:02:03": 3723, "-45s": -45, "0": 0, "0.1h": 360, "05m": 300,
          "90:00": 5400, "-1:30": -90, "-0s": 0, "1h 30m": 5400}
    for k, v in ok.items():
        assert parse_duration(k) == v, k
    for bad in ["", " ", "5", "1.5", ".5h", "5.h", "1 h", "30m1h", "1h1h", "0.3s",
                "1:60", "1:5", "+1h", "1h  30m", "1H", "1:30.5", "--1h", "1h,30m", "1h\n30m", "١h"]:
        try:
            parse_duration(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    try:
        parse_duration(5)
    except TypeError:
        pass
    else:
        raise AssertionError("TypeError")
