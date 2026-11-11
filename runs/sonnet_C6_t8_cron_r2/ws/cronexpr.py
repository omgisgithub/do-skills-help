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
        raise ValueError("invalid value %r" % tok)
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
            if not _NUM.fullmatch(step_s):
                raise ValueError("invalid step %r" % step_s)
            step = int(step_s)
            if step < 1:
                raise ValueError("step must be >= 1")
        else:
            step = 1
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, b = base.split("-", 1) if base.count("-") == 1 else (None, None)
            if a is None:
                raise ValueError("invalid range %r" % base)
            start = _value(a, lo, hi, names)
            end = _value(b, lo, hi, names)
            if start > end:
                raise ValueError("invalid range %r" % base)
        else:
            start = _value(base, lo, hi, names)
            end = hi if sep else start
        result.update(range(start, end + 1, step))
    return result


def _parse(expr):
    s = expr.strip(" \t")
    if s.startswith("@"):
        s = _SHORTCUTS.get(s.lower())
        if s is None:
            raise ValueError("unknown shortcut")
    parts = re.split(r"[ \t]+", s)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, lo, hi, names)
            for p, (lo, hi, names) in zip(parts, _FIELDS)]
    sets[4] = {v % 7 for v in sets[4]}
    dom_restricted = parts[2] != "*"
    dow_restricted = parts[4] != "*"
    return sets, dom_restricted, dow_restricted


def _day_matches(d, doms, dows, dom_r, dow_r):
    dom_ok = d.day in doms
    dow_ok = (d.isoweekday() % 7) in dows
    if dom_r and dow_r:
        return dom_ok or dow_ok
    if dom_r:
        return dom_ok
    if dow_r:
        return dow_ok
    return True


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    (minutes, hours, doms, months, dows), dom_r, dow_r = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28) + timedelta(days=1)

    mins = sorted(minutes)
    hrs = sorted(hours)
    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months and _day_matches(day, doms, dows, dom_r, dow_r):
            for h in hrs:
                for m in mins:
                    c = day.replace(hour=h, minute=m)
                    if c >= start:
                        if c > limit:
                            raise ValueError("no matching time within 5 years")
                        return c
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")
