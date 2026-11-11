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
_NUMBER = re.compile(r"[0-9]+")
_SEPARATOR = re.compile(r"[ \t]+")


def _parse_value(text, low, high, names):
    if _NUMBER.fullmatch(text):
        value = int(text)
    elif text.upper() in names:
        value = names[text.upper()]
    else:
        raise ValueError(f"invalid value {text!r}")
    if not low <= value <= high:
        raise ValueError(f"value {value} out of range {low}-{high}")
    return value


def _parse_field(text, low, high, names=None):
    names = names or {}
    values = set()
    for item in text.split(","):
        base, slash, step_text = item.partition("/")
        step = 1
        if slash:
            if not _NUMBER.fullmatch(step_text) or int(step_text) < 1:
                raise ValueError(f"invalid step in {item!r}")
            step = int(step_text)
        if base == "*":
            start, end = low, high
        elif "-" in base:
            first, _, last = base.partition("-")
            start = _parse_value(first, low, high, names)
            end = _parse_value(last, low, high, names)
            if start > end:
                raise ValueError(f"descending range {item!r}")
        else:
            start = _parse_value(base, low, high, names)
            end = high if slash else start
        values.update(range(start, end + 1, step))
    return values


def _parse(expr):
    expr = expr.strip(" \t")
    expr = _SHORTCUTS.get(expr.lower(), expr)
    parts = _SEPARATOR.split(expr)
    if len(parts) != 5:
        raise ValueError(f"expected 5 fields, got {len(parts)}")
    minutes = _parse_field(parts[0], 0, 59)
    hours = _parse_field(parts[1], 0, 23)
    days = _parse_field(parts[2], 1, 31)
    months = _parse_field(parts[3], 1, 12, _MONTHS)
    weekdays = {d % 7 for d in _parse_field(parts[4], 0, 7, _DAYS)}
    return (sorted(minutes), sorted(hours), days, months, weekdays,
            parts[2] != "*", parts[4] != "*")


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    minutes, hours, days, months, weekdays, dom_set, dow_set = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28)
    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months and _day_matches(
                day, days, weekdays, dom_set, dow_set):
            for hour in hours:
                for minute in minutes:
                    candidate = day.replace(hour=hour, minute=minute)
                    if candidate >= start:
                        if candidate > limit:
                            raise ValueError("no matching time within 5 years")
                        return candidate
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")


def _day_matches(day, days, weekdays, dom_set, dow_set):
    dom_ok = day.day in days
    dow_ok = (day.weekday() + 1) % 7 in weekdays
    if dom_set and dow_set:
        return dom_ok or dow_ok
    if dom_set:
        return dom_ok
    if dow_set:
        return dow_ok
    return True
