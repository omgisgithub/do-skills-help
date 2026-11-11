"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]

# (min, max, names: name -> value)
_FIELDS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, {n: i + 1 for i, n in enumerate(_MONTHS)}),
    (0, 7, {n: i for i, n in enumerate(_DAYS)}),
]


def _value(tok, lo, hi, names):
    if tok.isascii() and tok.isdigit():
        v = int(tok)
    elif tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("invalid value %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names):
    result = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty item")
        base, sep, step_s = item.partition("/")
        if sep:
            if not (step_s.isascii() and step_s.isdigit()) or int(step_s) < 1:
                raise ValueError("invalid step %r" % step_s)
            step = int(step_s)
        else:
            step = 1
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, _, b = base.partition("-")
            start, end = _value(a, lo, hi, names), _value(b, lo, hi, names)
            if start > end:
                raise ValueError("descending range")
        else:
            start = _value(base, lo, hi, names)
            end = hi if sep else start
        result.update(range(start, end + 1, step))
    return result


def _parse(expr):
    s = expr.strip(" \t")
    if s.lower() in _SHORTCUTS:
        s = _SHORTCUTS[s.lower()]
    parts = re.split(r"[ \t]+", s)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, *f) for p, f in zip(parts, _FIELDS)]
    sets[4] = {v % 7 for v in sets[4]}
    return sets, parts[2] != "*", parts[4] != "*"


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    (mins, hours, doms, months, dows), dom_r, dow_r = _parse(expr)
    mins, hours = sorted(mins), sorted(hours)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28) + timedelta(days=1)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months:
            dm = day.day in doms
            dw = (day.weekday() + 1) % 7 in dows
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
                    for m in mins:
                        cand = day.replace(hour=h, minute=m)
                        if cand >= start:
                            if cand > limit:
                                raise ValueError("no match within 5 years")
                            return cand
        day += timedelta(days=1)
    raise ValueError("no match within 5 years")
