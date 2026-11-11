"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
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
_WS = " \t"


def _num(text, names, offset, lo, hi):
    if text.isascii() and text.isdigit():
        val = int(text)
    elif names and text.upper() in names:
        val = names.index(text.upper()) + offset
    else:
        raise ValueError("invalid value: %r" % text)
    if not lo <= val <= hi:
        raise ValueError("value out of range: %r" % text)
    return val


def _parse_field(text, lo, hi, names=None, offset=0):
    values = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty item")
        base, sep, step_text = item.partition("/")
        if sep:
            if not (step_text.isascii() and step_text.isdigit()):
                raise ValueError("invalid step: %r" % step_text)
            step = int(step_text)
            if step < 1:
                raise ValueError("step must be >= 1")
        else:
            step = 1
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, _, b = base.partition("-")
            start = _num(a, names, offset, lo, hi)
            end = _num(b, names, offset, lo, hi)
            if start > end:
                raise ValueError("invalid range: %r" % base)
        else:
            start = _num(base, names, offset, lo, hi)
            end = hi if sep else start
        values.update(range(start, end + 1, step))
    return values


def _parse(expr):
    expr = expr.strip(_WS)
    if expr.lower() in _SHORTCUTS:
        expr = _SHORTCUTS[expr.lower()]
    fields = expr.replace("\t", " ").split(" ")
    fields = [f for f in fields if f]
    if len(fields) != 5:
        raise ValueError("expected 5 fields")
    minute = _parse_field(fields[0], 0, 59)
    hour = _parse_field(fields[1], 0, 23)
    dom = _parse_field(fields[2], 1, 31)
    month = _parse_field(fields[3], 1, 12, _MONTHS, 1)
    dow = {v % 7 for v in _parse_field(fields[4], 0, 7, _DAYS, 0)}
    return (sorted(minute), sorted(hour), dom, month, dow,
            fields[2] != "*", fields[4] != "*")


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    minutes, hours, dom, month, dow, dom_r, dow_r = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28) + timedelta(days=1)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in month:
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
                    for m in minutes:
                        cand = day.replace(hour=h, minute=m)
                        if cand >= start:
                            if cand > limit:
                                raise ValueError("no matching time within 5 years")
                            return cand
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")
