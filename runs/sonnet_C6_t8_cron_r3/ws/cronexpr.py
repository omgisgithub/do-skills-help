"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

# (min, max, names: name -> value)
_FIELDS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, {n: i + 1 for i, n in enumerate(_MONTHS)}),
    (0, 7, {n: i for i, n in enumerate(_DAYS)}),
]

_ITEM = re.compile(r"(\*|([0-9]+|[A-Za-z]{3})(?:-([0-9]+|[A-Za-z]{3}))?)(?:/([0-9]+))?")


def _value(tok, lo, hi, names):
    if tok.isascii() and tok.isdigit():
        v = int(tok)
    else:
        v = names.get(tok.upper())
        if v is None:
            raise ValueError("invalid value %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names):
    out = set()
    for item in text.split(","):
        m = _ITEM.fullmatch(item)
        if not m:
            raise ValueError("invalid item %r" % item)
        base, a, b, step = m.groups()
        if step is not None:
            step = int(step)
            if step < 1:
                raise ValueError("step must be >= 1")
        if base == "*":
            start, end = lo, hi
        elif b is not None:
            start, end = _value(a, lo, hi, names), _value(b, lo, hi, names)
            if start > end:
                raise ValueError("descending range")
        else:
            start = _value(a, lo, hi, names)
            end = hi if step is not None else start
        out.update(range(start, end + 1, step or 1))
    return out


def _parse(expr):
    if not isinstance(expr, str):
        raise TypeError("expr must be str")
    s = expr.strip(" \t")
    s = _SHORTCUTS.get(s.lower(), s)
    parts = re.split(r"[ \t]+", s)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, *f) for p, f in zip(parts, _FIELDS)]
    sets[4] = {v % 7 for v in sets[4]}
    return sets, parts[2] != "*", parts[4] != "*"


def next_run(expr, after):
    (mins, hours, doms, months, dows), dom_r, dow_r = _parse(expr)
    if not isinstance(after, datetime):
        raise TypeError("after must be datetime")
    mins, hours = sorted(mins), sorted(hours)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28)
    day = after.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= limit:
        if day.month in months:
            dm, dw = day.day in doms, (day.weekday() + 1) % 7 in dows
            if dom_r and dow_r:
                ok = dm or dw
            elif dom_r:
                ok = dm
            elif dow_r:
                ok = dw
            else:
                ok = True
            if ok:
                for h in hours:
                    for mi in mins:
                        c = day.replace(hour=h, minute=mi)
                        if c > after:
                            if c > limit:
                                raise ValueError("no match within 5 years")
                            return c
        day += timedelta(days=1)
    raise ValueError("no match within 5 years")
