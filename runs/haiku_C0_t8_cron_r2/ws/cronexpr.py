"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, time, timedelta

_NUMBER = re.compile(r"[0-9]+")
_SEPARATOR = re.compile(r"[ \t]+")

_MONTH_NAMES = {name: i for i, name in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
_WEEKDAY_NAMES = {name: i for i, name in enumerate(
    "SUN MON TUE WED THU FRI SAT".split())}

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _value(token, lo, hi, names):
    if token.upper() in names:
        return names[token.upper()]
    if not _NUMBER.fullmatch(token):
        raise ValueError(f"invalid value {token!r}")
    n = int(token)
    if not lo <= n <= hi:
        raise ValueError(f"value {n} out of range {lo}-{hi}")
    return n


def _parse_item(item, lo, hi, names):
    base, slash, step_text = item.partition("/")
    step = 1
    if slash:
        if not _NUMBER.fullmatch(step_text) or int(step_text) < 1:
            raise ValueError(f"invalid step in {item!r}")
        step = int(step_text)

    if base == "*":
        start, end = lo, hi
    elif "-" in base:
        a, _, b = base.partition("-")
        start = _value(a, lo, hi, names)
        end = _value(b, lo, hi, names)
        if start > end:
            raise ValueError(f"range {base!r} runs backwards")
    else:
        start = _value(base, lo, hi, names)
        # N/S means N, N+S, ... up to the field maximum
        end = hi if slash else start
    return range(start, end + 1, step)


def _parse_field(text, lo, hi, names=None):
    values = set()
    for item in text.split(","):
        values.update(_parse_item(item, lo, hi, names or {}))
    return values


def _parse(expr):
    text = _SHORTCUTS.get(expr.strip().lower(), expr.strip())
    fields = _SEPARATOR.split(text)
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}: {expr!r}")
    minute_f, hour_f, dom_f, month_f, dow_f = fields

    minutes = sorted(_parse_field(minute_f, 0, 59))
    hours = sorted(_parse_field(hour_f, 0, 23))
    days = _parse_field(dom_f, 1, 31)
    months = _parse_field(month_f, 1, 12, _MONTH_NAMES)
    # 7 is an alternative spelling of Sunday (0)
    weekdays = {d % 7 for d in _parse_field(dow_f, 0, 7, _WEEKDAY_NAMES)}

    return (minutes, hours, days, months, weekdays,
            dom_f != "*", dow_f != "*")


def _day_matches(day, days, weekdays, dom_restricted, dow_restricted):
    dom_ok = day.day in days
    # Python: Monday=0 ... Sunday=6; cron: Sunday=0 ... Saturday=6
    dow_ok = (day.weekday() + 1) % 7 in weekdays
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def _horizon(after):
    # Five calendar years after `after`; 29 Feb falls back to 1 Mar
    try:
        return after.replace(year=after.year + 5)
    except ValueError:
        return after.replace(year=after.year + 5, month=3, day=1)


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError(f"expr must be str, not {type(expr).__name__}")

    minutes, hours, days, months, weekdays, dom_r, dow_r = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _horizon(after)

    day = start.date()
    while day <= limit.date():
        if day.month in months and _day_matches(day, days, weekdays, dom_r, dow_r):
            for hour in hours:
                for minute in minutes:
                    candidate = datetime.combine(day, time(hour, minute))
                    if candidate >= start:
                        if candidate > limit:
                            break
                        return candidate
        day += timedelta(days=1)

    raise ValueError(f"no matching time within 5 years of {after} for {expr!r}")
