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
_NUM = re.compile(r"[0-9]+")


def _value(tok, names, lo, hi):
    if _NUM.fullmatch(tok):
        val = int(tok)
    elif tok.upper() in names:
        val = names[tok.upper()]
    else:
        raise ValueError(f"invalid value {tok!r}")
    if not lo <= val <= hi:
        raise ValueError(f"value {tok!r} out of range {lo}-{hi}")
    return val


def _parse_field(field, lo, hi, names=None):
    names = names or {}
    result = set()
    for item in field.split(","):
        base, sep, step_s = item.partition("/")
        step = 1
        if sep:
            if not _NUM.fullmatch(step_s) or int(step_s) < 1:
                raise ValueError(f"invalid step in {item!r}")
            step = int(step_s)
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, _, b = base.partition("-")
            start, end = _value(a, names, lo, hi), _value(b, names, lo, hi)
            if start > end:
                raise ValueError(f"invalid range {item!r}")
        else:
            start = _value(base, names, lo, hi)
            end = hi if sep else start
        result.update(range(start, end + 1, step))
    return result


def _parse(expr):
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    fields = [f for f in re.split(r"[ \t]+", expr)]
    if len(fields) != 5:
        raise ValueError("expression must have 5 fields")
    minute, hour, dom, month, dow = fields
    minutes = sorted(_parse_field(minute, 0, 59))
    hours = sorted(_parse_field(hour, 0, 23))
    doms = _parse_field(dom, 1, 31)
    months = _parse_field(month, 1, 12, _MONTHS)
    dows = {d % 7 for d in _parse_field(dow, 0, 7, _DAYS)}
    return minutes, hours, doms, months, dows, dom != "*", dow != "*"


def next_run(expr, after):
    """Return the earliest matching minute strictly later than ``after``."""
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
        if day.month in months and _day_matches(day, doms, dows, dom_r, dow_r):
            for h in hours:
                for m in minutes:
                    cand = day.replace(hour=h, minute=m)
                    if cand >= start:
                        if cand > limit:
                            raise ValueError("no matching time within 5 years")
                        return cand
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")


def _day_matches(day, doms, dows, dom_r, dow_r):
    dom_ok = day.day in doms
    dow_ok = (day.weekday() + 1) % 7 in dows
    if dom_r and dow_r:
        return dom_ok or dow_ok
    if dom_r:
        return dom_ok
    if dow_r:
        return dow_ok
    return True
