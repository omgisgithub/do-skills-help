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
_NUM = re.compile(r"[0-9]+")


def _value(tok, lo, hi, names, offset):
    if _NUM.fullmatch(tok):
        v = int(tok)
    elif names and tok.upper() in names:
        v = names.index(tok.upper()) + offset
    else:
        raise ValueError("invalid value: %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names=None, offset=0):
    result = set()
    for item in text.split(","):
        base, slash, step_s = item.partition("/")
        if slash:
            if not _NUM.fullmatch(step_s) or int(step_s) < 1:
                raise ValueError("invalid step: %r" % item)
            step = int(step_s)
        else:
            step = 1
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            left, _, right = base.partition("-")
            a = _value(left, lo, hi, names, offset)
            b = _value(right, lo, hi, names, offset)
            if a > b:
                raise ValueError("invalid range: %r" % item)
        else:
            a = _value(base, lo, hi, names, offset)
            b = hi if slash else a
        result.update(range(a, b + 1, step))
    return result


def _parse(expr):
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    parts = re.split(r"[ \t]+", expr)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    minute = _parse_field(parts[0], 0, 59)
    hour = _parse_field(parts[1], 0, 23)
    dom = _parse_field(parts[2], 1, 31)
    month = _parse_field(parts[3], 1, 12, _MONTHS, 1)
    dow = {v % 7 for v in _parse_field(parts[4], 0, 7, _DAYS, 0)}
    return (minute, hour, dom, month, dow,
            parts[2] != "*", parts[4] != "*")


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    minutes, hours, doms, months, dows, dom_r, dow_r = _parse(expr)
    minutes, hours = sorted(minutes), sorted(hours)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months:
            dom_ok = day.day in doms
            dow_ok = (day.weekday() + 1) % 7 in dows
            if dom_r and dow_r:
                ok = dom_ok or dow_ok
            elif dom_r:
                ok = dom_ok
            elif dow_r:
                ok = dow_ok
            else:
                ok = True
            if ok:
                for h in hours:
                    for m in minutes:
                        cand = day.replace(hour=h, minute=m)
                        if cand >= start:
                            if cand > limit:
                                raise ValueError("no match within 5 years")
                            return cand
        day += timedelta(days=1)
    raise ValueError("no match within 5 years")
