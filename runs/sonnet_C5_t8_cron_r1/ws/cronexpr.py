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
_MONTHS = {n: i + 1 for i, n in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
_DAYS = {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())}

# (min, max, names)
_FIELDS = [(0, 59, {}), (0, 23, {}), (1, 31, {}), (1, 12, _MONTHS), (0, 7, _DAYS)]


def _num(tok, lo, hi, names):
    if tok.isascii() and tok.isdigit():
        v = int(tok)
    elif tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("invalid value: %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names):
    values = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty item")
        base, sep, step_s = item.partition("/")
        if sep:
            if not (step_s.isascii() and step_s.isdigit()) or int(step_s) < 1:
                raise ValueError("invalid step: %r" % item)
            step = int(step_s)
        else:
            step = 1
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, _, b = base.partition("-")
            start, end = _num(a, lo, hi, names), _num(b, lo, hi, names)
            if start > end:
                raise ValueError("invalid range: %r" % item)
        else:
            start = _num(base, lo, hi, names)
            end = hi if sep else start
        values.update(range(start, end + 1, step))
    return values


def _parse(expr):
    s = expr.strip()
    s = _SHORTCUTS.get(s.lower(), s)
    parts = s.replace("\t", " ").split(" ")
    parts = [p for p in parts if p]
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, *f) for p, f in zip(parts, _FIELDS)]
    sets[4] = {v % 7 for v in sets[4]}
    return sets, parts[2] != "*", parts[4] != "*"


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    (minutes, hours, doms, months, dows), dom_r, dow_r = _parse(expr)
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
                                raise ValueError("no matching time within 5 years")
                            return cand
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")
