"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_MONTHS = {n: i + 1 for i, n in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
_DOWS = {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())}
_VAL = r"(?:[0-9]+|[A-Za-z]+)"
_ITEM = re.compile(r"(\*|(%s)(?:-(%s))?)(?:/([0-9]+))?" % (_VAL, _VAL))


def _value(tok, lo, hi, names):
    if tok.isascii() and tok.isdigit():
        v = int(tok)
    elif names and tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("invalid value %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names=None):
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
                raise ValueError("invalid range %r" % item)
        else:
            start = _value(a, lo, hi, names)
            end = hi if step is not None else start
        out.update(range(start, end + 1, step or 1))
    return out


def _parse(expr):
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    parts = re.split(r"[ \t]+", expr)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    mi = _parse_field(parts[0], 0, 59)
    ho = _parse_field(parts[1], 0, 23)
    dom = _parse_field(parts[2], 1, 31)
    mo = _parse_field(parts[3], 1, 12, _MONTHS)
    dow = {d % 7 for d in _parse_field(parts[4], 0, 7, _DOWS)}
    return mi, ho, dom, mo, dow, parts[2] != "*", parts[4] != "*"


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    mi, ho, dom, mo, dow, dom_r, dow_r = _parse(expr)
    mins, hours = sorted(mi), sorted(ho)
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28) + timedelta(days=1)
    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in mo:
            wd = (day.weekday() + 1) % 7
            if dom_r and dow_r:
                ok = day.day in dom or wd in dow
            elif dom_r:
                ok = day.day in dom
            elif dow_r:
                ok = wd in dow
            else:
                ok = True
            if ok:
                for h in hours:
                    for m in mins:
                        c = day.replace(hour=h, minute=m)
                        if c >= start:
                            if c > limit:
                                raise ValueError("no match within 5 years")
                            return c
        day += timedelta(days=1)
    raise ValueError("no match within 5 years")
