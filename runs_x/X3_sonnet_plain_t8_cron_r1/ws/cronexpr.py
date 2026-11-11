"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_NUM = re.compile(r"[0-9]+\Z")


def _value(tok, lo, hi, names):
    if _NUM.match(tok):
        v = int(tok)
    elif names and tok.upper() in names:
        v = names.index(tok.upper()) + (1 if names is _MONTHS else 0)
    else:
        raise ValueError("invalid value: %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names=None):
    out = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty item")
        base, sep, step = item.partition("/")
        if sep:
            if not _NUM.match(step) or int(step) < 1:
                raise ValueError("invalid step: %r" % item)
            s = int(step)
        else:
            s = None
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            x, _, y = base.partition("-")
            a, b = _value(x, lo, hi, names), _value(y, lo, hi, names)
            if a > b:
                raise ValueError("invalid range: %r" % item)
        else:
            a = _value(base, lo, hi, names)
            b = hi if s is not None else a
        out.update(range(a, b + 1, s or 1))
    return out


def _parse(expr):
    expr = expr.strip()
    if expr.startswith("@"):
        key = expr.lower()
        if key not in _SHORTCUTS:
            raise ValueError("unknown shortcut: %r" % expr)
        expr = _SHORTCUTS[key]
    fields = re.split(r"[ \t]+", expr)
    if len(fields) != 5:
        raise ValueError("expected 5 fields")
    mi = _parse_field(fields[0], 0, 59)
    ho = _parse_field(fields[1], 0, 23)
    dom = _parse_field(fields[2], 1, 31)
    mon = _parse_field(fields[3], 1, 12, _MONTHS)
    dow = {d % 7 for d in _parse_field(fields[4], 0, 7, _DAYS)}
    return (sorted(mi), sorted(ho), dom, mon, dow,
            fields[2] != "*", fields[4] != "*")


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    mins, hours, dom, mon, dow, dom_r, dow_r = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28) + timedelta(days=1)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in mon:
            cd = day.day in dom
            cw = (day.weekday() + 1) % 7 in dow
            if dom_r and dow_r:
                ok = cd or cw
            elif dom_r:
                ok = cd
            elif dow_r:
                ok = cw
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
