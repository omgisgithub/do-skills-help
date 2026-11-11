"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTHS = {n: i + 1 for i, n in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
_DOWS = {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())}
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_NUM = re.compile(r"[0-9]+", re.ASCII)
_NAME = re.compile(r"[A-Za-z]{3}", re.ASCII)


def _value(tok, lo, hi, names):
    if _NUM.fullmatch(tok):
        v = int(tok)
    elif names and _NAME.fullmatch(tok) and tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("invalid value %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names=None):
    out = set()
    for item in text.split(","):
        if item == "":
            raise ValueError("empty item")
        base, sep, step = item.partition("/")
        if sep:
            if not _NUM.fullmatch(step) or int(step) < 1:
                raise ValueError("invalid step %r" % step)
            step = int(step)
        else:
            step = None
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            x, _, y = base.partition("-")
            a, b = _value(x, lo, hi, names), _value(y, lo, hi, names)
            if a > b:
                raise ValueError("invalid range %r" % base)
        else:
            a = _value(base, lo, hi, names)
            b = hi if step else a
        out.update(range(a, b + 1, step or 1))
    return out


def _parse(expr):
    s = expr.strip(" \t")
    s = _SHORTCUTS.get(s.lower(), s)
    fields = re.split(r"[ \t]+", s)
    if len(fields) != 5:
        raise ValueError("expected 5 fields")
    mi = _parse_field(fields[0], 0, 59)
    ho = _parse_field(fields[1], 0, 23)
    dom = _parse_field(fields[2], 1, 31)
    mo = _parse_field(fields[3], 1, 12, _MONTHS)
    dow = {d % 7 for d in _parse_field(fields[4], 0, 7, _DOWS)}
    return (sorted(mi), sorted(ho), dom, mo, dow,
            fields[2] != "*", fields[4] != "*")


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    minutes, hours, dom, months, dow, dom_r, dow_r = _parse(expr)
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:
        limit = after.replace(year=after.year + 5, day=28)
    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months:
            dm = day.day in dom
            dw = (day.weekday() + 1) % 7 in dow
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
                    for m in minutes:
                        c = day.replace(hour=h, minute=m)
                        if c >= start:
                            if c > limit:
                                raise ValueError("no match within 5 years")
                            return c
        day += timedelta(days=1)
    raise ValueError("no match within 5 years")
