"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTHS = {n: i + 1 for i, n in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
_DAYS = {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())}

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

# (min, max, names)
_FIELDS = [
    (0, 59, None),
    (0, 23, None),
    (1, 31, None),
    (1, 12, _MONTHS),
    (0, 7, _DAYS),
]


def _value(tok, lo, hi, names):
    if tok.isascii() and tok.isdigit():
        v = int(tok)
    elif names and tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("invalid value: %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names):
    result = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty item")
        parts = item.split("/")
        if len(parts) > 2:
            raise ValueError("invalid item: %r" % item)
        base = parts[0]
        step = None
        if len(parts) == 2:
            s = parts[1]
            if not (s.isascii() and s.isdigit()) or int(s) < 1:
                raise ValueError("invalid step: %r" % item)
            step = int(s)
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, _, b = base.partition("-")
            start = _value(a, lo, hi, names)
            end = _value(b, lo, hi, names)
            if start > end:
                raise ValueError("invalid range: %r" % item)
        else:
            start = _value(base, lo, hi, names)
            end = hi if step is not None else start
        result.update(range(start, end + 1, step or 1))
    return result


def _parse(expr):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    text = expr.strip(" \t")
    text = _SHORTCUTS.get(text.lower(), text)
    parts = re.split(r"[ \t]+", text)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, *f) for p, f in zip(parts, _FIELDS)]
    sets[4] = {v % 7 for v in sets[4]}
    return sets, parts[2] != "*", parts[4] != "*"


def next_run(expr, after):
    (minutes, hours, doms, months, dows), dom_r, dow_r = _parse(expr)
    minutes = sorted(minutes)
    hours = sorted(hours)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28)

    def day_ok(d):
        if d.month not in months:
            return False
        dm = d.day in doms
        dw = (d.weekday() + 1) % 7 in dows
        if dom_r and dow_r:
            return dm or dw
        if dom_r:
            return dm
        if dow_r:
            return dw
        return True

    day = start.date()
    last = limit.date()
    first = True
    while day <= last:
        if day_ok(day):
            for h in hours:
                for m in minutes:
                    if first and (h, m) < (start.hour, start.minute):
                        continue
                    cand = datetime(day.year, day.month, day.day, h, m)
                    if cand > limit:
                        raise ValueError("no matching time within 5 years")
                    return cand
        first = False
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")
