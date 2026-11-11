"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

# (min, max, names -> value)
_FIELDS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, {n: i + 1 for i, n in enumerate(_MONTHS)}),
    (0, 7, {n: i for i, n in enumerate(_DAYS)}),
]

_NUM = re.compile(r"[0-9]+")


def _value(tok, lo, hi, names):
    if _NUM.fullmatch(tok):
        v = int(tok)
    elif tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("invalid value: %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names):
    result = set()
    for item in text.split(","):
        if item == "":
            raise ValueError("empty item")
        base, sep, step_s = item.partition("/")
        if sep:
            if not _NUM.fullmatch(step_s) or int(step_s) < 1:
                raise ValueError("invalid step: %r" % item)
            step = int(step_s)
        else:
            step = 1
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            parts = base.split("-")
            if len(parts) != 2:
                raise ValueError("invalid range: %r" % item)
            a = _value(parts[0], lo, hi, names)
            b = _value(parts[1], lo, hi, names)
            if a > b:
                raise ValueError("descending range: %r" % item)
        else:
            a = _value(base, lo, hi, names)
            b = hi if sep else a
        result.update(range(a, b + 1, step))
    return result


def _parse(expr):
    expr = expr.strip()
    if expr.startswith("@"):
        expr = _SHORTCUTS.get(expr.lower())
        if expr is None:
            raise ValueError("unknown shortcut")
    parts = re.split(r"[ \t]+", expr)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, lo, hi, names)
            for p, (lo, hi, names) in zip(parts, _FIELDS)]
    sets[4] = {v % 7 for v in sets[4]}
    return sets, parts[2] != "*", parts[4] != "*"


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    (mins, hours, doms, months, dows), dom_r, dow_r = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28)
    mins_s, hours_s = sorted(mins), sorted(hours)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        py_dow = (day.weekday() + 1) % 7  # Sunday = 0
        if day.month in months:
            dm, dw = day.day in doms, py_dow in dows
            if dom_r and dow_r:
                ok = dm or dw
            elif dom_r:
                ok = dm
            elif dow_r:
                ok = dw
            else:
                ok = True
            if ok:
                for h in hours_s:
                    for m in mins_s:
                        cand = day.replace(hour=h, minute=m)
                        if cand >= start:
                            if cand > limit:
                                raise ValueError("no matching time within 5 years")
                            return cand
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")
