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

# (min, max, names {NAME: value})
_FIELDS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, {n: i + 1 for i, n in enumerate(_MONTHS)}),
    (0, 7, {n: i for i, n in enumerate(_DAYS)}),
]


def _value(tok, lo, hi, names):
    if re.fullmatch(r"[0-9]+", tok):
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
        base, sep, step = item.partition("/")
        if sep:
            if not re.fullmatch(r"[0-9]+", step) or int(step) < 1:
                raise ValueError("invalid step: %r" % step)
            step = int(step)
        else:
            step = None
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            parts = base.split("-")
            if len(parts) != 2:
                raise ValueError("invalid range: %r" % base)
            a = _value(parts[0], lo, hi, names)
            b = _value(parts[1], lo, hi, names)
            if a > b:
                raise ValueError("invalid range: %r" % base)
        else:
            a = _value(base, lo, hi, names)
            b = hi if step is not None else a
        out.update(range(a, b + 1, step or 1))
    return out


def _parse(expr):
    expr = expr.strip(" \t")
    expr = _SHORTCUTS.get(expr.lower(), expr)
    parts = re.split(r"[ \t]+", expr)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, *f) for p, f in zip(parts, _FIELDS)]
    minutes, hours, doms, months, dows = sets
    dows = {d % 7 for d in dows}
    return (sorted(minutes), sorted(hours), doms, months, dows,
            parts[2] != "*", parts[4] != "*")


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    minutes, hours, doms, months, dows, dom_r, dow_r = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28) + timedelta(days=1)

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
