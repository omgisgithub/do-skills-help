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
_FIELDS = [
    (0, 59, None),
    (0, 23, None),
    (1, 31, None),
    (1, 12, _MONTHS),
    (0, 7, _DAYS),
]

_NUM = re.compile(r"[0-9]+\Z")
_NAME = re.compile(r"[A-Za-z]+\Z")


def _value(tok, lo, hi, names):
    if _NUM.match(tok):
        v = int(tok)
    elif names is not None and _NAME.match(tok) and tok.upper() in names:
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
        base, slash, step_s = item.partition("/")
        step = 1
        if slash:
            if not _NUM.match(step_s):
                raise ValueError("invalid step: %r" % item)
            step = int(step_s)
            if step < 1:
                raise ValueError("step must be >= 1")
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, sep, b = base.partition("-")
            start = _value(a, lo, hi, names)
            end = _value(b, lo, hi, names)
            if start > end:
                raise ValueError("invalid range: %r" % item)
        else:
            start = _value(base, lo, hi, names)
            end = hi if slash else start
        result.update(range(start, end + 1, step))
    return result


def _parse(expr):
    s = expr.strip()
    s = _SHORTCUTS.get(s.lower(), s)
    parts = re.split(r"[ \t]+", s)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, *f) for p, f in zip(parts, _FIELDS)]
    minutes, hours, doms, months, dows = sets
    dows = {d % 7 for d in dows}
    dom_restricted = parts[2] != "*"
    dow_restricted = parts[4] != "*"
    return minutes, hours, doms, months, dows, dom_restricted, dow_restricted


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    minutes, hours, doms, months, dows, dom_r, dow_r = _parse(expr)
    mins_sorted = sorted(minutes)
    hours_sorted = sorted(hours)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        end = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        end = after.replace(year=after.year + 5, day=28)
    except OverflowError:
        raise ValueError("no matching time")

    def day_ok(d):
        if d.month not in months:
            return False
        dom_ok = d.day in doms
        dow_ok = (d.weekday() + 1) % 7 in dows
        if dom_r and dow_r:
            return dom_ok or dow_ok
        if dom_r:
            return dom_ok
        if dow_r:
            return dow_ok
        return True

    day = start.replace(hour=0, minute=0)
    while day <= end:
        if day_ok(day):
            for h in hours_sorted:
                for m in mins_sorted:
                    cand = day.replace(hour=h, minute=m)
                    if cand >= start:
                        if cand > end:
                            raise ValueError("no matching time within 5 years")
                        return cand
        try:
            day += timedelta(days=1)
        except OverflowError:
            break
    raise ValueError("no matching time within 5 years")
