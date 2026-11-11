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
_MONTHS = {n: i + 1 for i, n in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
_DAYS = {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())}
_NUM = re.compile(r"[0-9]+")


def _value(tok, names, lo, hi):
    if _NUM.fullmatch(tok):
        v = int(tok)
    elif names and tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("invalid value: %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names=None):
    result = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty item")
        base, sep, step_s = item.partition("/")
        if sep:
            if not _NUM.fullmatch(step_s) or int(step_s) < 1:
                raise ValueError("invalid step: %r" % item)
            step = int(step_s)
        else:
            step = 1
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, _, b = base.partition("-")
            start, end = _value(a, names, lo, hi), _value(b, names, lo, hi)
            if start > end:
                raise ValueError("invalid range: %r" % item)
        else:
            start = _value(base, names, lo, hi)
            end = hi if sep else start
        result.update(range(start, end + 1, step))
    return result


def _parse(expr):
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    fields = re.split(r"[ \t]+", expr)
    if len(fields) != 5:
        raise ValueError("expected 5 fields")
    mi = _parse_field(fields[0], 0, 59)
    ho = _parse_field(fields[1], 0, 23)
    dom = _parse_field(fields[2], 1, 31)
    mo = _parse_field(fields[3], 1, 12, _MONTHS)
    dow = {d % 7 for d in _parse_field(fields[4], 0, 7, _DAYS)}
    return (sorted(mi), sorted(ho), dom, mo, dow,
            fields[2] != "*", fields[4] != "*")


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    mins, hours, dom, months, dow, dom_r, dow_r = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28) + timedelta(days=1)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months:
            d_ok = day.day in dom
            w_ok = (day.weekday() + 1) % 7 in dow
            if dom_r and dow_r:
                ok = d_ok or w_ok
            elif dom_r:
                ok = d_ok
            elif dow_r:
                ok = w_ok
            else:
                ok = True
            if ok:
                for h in hours:
                    for m in mins:
                        cand = day.replace(hour=h, minute=m)
                        if cand >= start:
                            if cand > limit:
                                raise ValueError("no matching time within 5 years")
                            return cand
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")
