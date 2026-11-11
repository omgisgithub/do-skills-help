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

# (min, max, names)
_FIELDS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, {n: i + 1 for i, n in enumerate(_MONTHS)}),
    (0, 7, {n: i for i, n in enumerate(_DAYS)}),
]
_NUM = re.compile(r"[0-9]+\Z")


def _value(tok, lo, hi, names):
    if _NUM.match(tok):
        v = int(tok)
    elif tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("invalid value: %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names):
    out = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty item")
        base, sep, step_s = item.partition("/")
        if sep:
            if not _NUM.match(step_s) or int(step_s) < 1:
                raise ValueError("invalid step: %r" % item)
            step = int(step_s)
        else:
            step = 1
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            x, _, y = base.partition("-")
            a, b = _value(x, lo, hi, names), _value(y, lo, hi, names)
            if a > b:
                raise ValueError("invalid range: %r" % item)
        else:
            a = _value(base, lo, hi, names)
            b = hi if sep else a
        out.update(range(a, b + 1, step))
    return out


def _parse(expr):
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    parts = re.split(r"[ \t]+", expr)
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
            wd = (day.weekday() + 1) % 7  # Sunday = 0
            if dom_r and dow_r:
                ok = day.day in doms or wd in dows
            elif dom_r:
                ok = day.day in doms
            elif dow_r:
                ok = wd in dows
            else:
                ok = True
            if ok:
                for h in hours:
                    for m in mins:
                        cand = day.replace(hour=h, minute=m)
                        if cand >= start:
                            return cand if cand <= limit else _fail()
        day += timedelta(days=1)
    _fail()


def _fail():
    raise ValueError("no matching time within 5 years")
