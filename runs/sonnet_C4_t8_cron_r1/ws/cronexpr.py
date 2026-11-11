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
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), start=1)}
_DAYS = {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())}
_NUMBER = re.compile(r"[0-9]+")


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


def _parse_item(item, low, high, names):
    base, sep, step_text = item.partition("/")
    step = 1
    if sep:
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
        end = high if sep else start
    return range(start, end + 1, step)


def _parse_field(text, low, high, names=None):
    names = names or {}
    values = set()
    for item in text.split(","):
        values.update(_parse_item(item, low, high, names))
    return values


def _parse(expr):
    text = expr.strip(" \t")
    text = _SHORTCUTS.get(text.lower(), text)
    fields = re.split(r"[ \t]+", text)
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}")
    minutes = _parse_field(fields[0], 0, 59)
    hours = _parse_field(fields[1], 0, 23)
    dom = _parse_field(fields[2], 1, 31)
    months = _parse_field(fields[3], 1, 12, _MONTHS)
    dow = {v % 7 for v in _parse_field(fields[4], 0, 7, _DAYS)}
    return (minutes, hours, dom, months, dow, fields[2] != "*", fields[4] != "*")


def _day_matches(day, dom, dow, dom_restricted, dow_restricted):
    dom_ok = day.day in dom
    dow_ok = (day.weekday() + 1) % 7 in dow
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    if dom_restricted:
        return dom_ok
    if dow_restricted:
        return dow_ok
    return True


def next_run(expr, after):
    """Return the earliest matching minute strictly later than ``after``.

    Raises:
        TypeError: If ``expr`` is not a string.
        ValueError: If ``expr`` is invalid or nothing matches within 5 years.
    """
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    minutes, hours, dom, months, dow, dom_r, dow_r = _parse(expr)
    sorted_times = [(h, m) for h in sorted(hours) for m in sorted(minutes)]

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, month=3, day=1)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months and _day_matches(day, dom, dow, dom_r, dow_r):
            for hour, minute in sorted_times:
                candidate = day.replace(hour=hour, minute=minute)
                if candidate >= start:
                    if candidate > limit:
                        raise ValueError("no matching time within 5 years")
                    return candidate
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")
