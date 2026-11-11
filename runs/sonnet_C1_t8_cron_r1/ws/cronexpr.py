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
_MONTHS = {n: i for i, n in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
_DAYS = {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())}

# (min, max, names)
_FIELDS = [(0, 59, {}), (0, 23, {}), (1, 31, {}), (1, 12, _MONTHS), (0, 7, _DAYS)]


def _value(tok, lo, hi, names):
    if tok.isascii() and tok.isdigit():
        v = int(tok)
    elif tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("invalid value %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value %r out of range" % tok)
    return v


def _parse_field(text, lo, hi, names):
    out = set()
    if text == "":
        raise ValueError("empty field")
    for item in text.split(","):
        if item == "":
            raise ValueError("empty item")
        base, sep, step_s = item.partition("/")
        step = 1
        if sep:
            if not (step_s.isascii() and step_s.isdigit()):
                raise ValueError("invalid step %r" % step_s)
            step = int(step_s)
            if step < 1:
                raise ValueError("step must be >= 1")
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
        out.update(range(start, end + 1, step))
    return out


def _parse(expr):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    s = expr.strip(" \t")
    s = _SHORTCUTS.get(s.lower(), s)
    parts = re.split(r"[ \t]+", s)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, *f) for p, f in zip(parts, _FIELDS)]
    minutes, hours, doms, months, dows = sets
    dows = {d % 7 for d in dows}
    dom_r, dow_r = parts[2] != "*", parts[4] != "*"
    return minutes, hours, doms, months, dows, dom_r, dow_r


def next_run(expr, after):
    minutes, hours, doms, months, dows, dom_r, dow_r = _parse(expr)
    if not isinstance(after, datetime):
        raise TypeError("after must be a datetime")
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:
        limit = after.replace(year=after.year + 5, day=28) + timedelta(days=1)
    mins, hrs = sorted(minutes), sorted(hours)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months:
            cron_dow = (day.weekday() + 1) % 7
            if dom_r and dow_r:
                ok = day.day in doms or cron_dow in dows
            elif dom_r:
                ok = day.day in doms
            elif dow_r:
                ok = cron_dow in dows
            else:
                ok = True
            if ok:
                for h in hrs:
                    for m in mins:
                        cand = day.replace(hour=h, minute=m)
                        if cand >= start:
                            if cand > limit:
                                raise ValueError("no match within 5 years")
                            return cand
        day += timedelta(days=1)
    raise ValueError("no match within 5 years")
