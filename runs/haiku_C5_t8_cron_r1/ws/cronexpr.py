"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, time, timedelta

_MONTHS = {
    name: number
    for number, name in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
        start=1,
    )
}
_DAYS = {name: number for number, name in enumerate(
    ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])}

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

# (name, minimum, maximum, names allowed in this field)
_FIELDS = (
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day of month", 1, 31, {}),
    ("month", 1, 12, _MONTHS),
    ("day of week", 0, 7, _DAYS),
)

# `*`, `N`, or `A-B`, optionally followed by `/S`.
_ITEM = re.compile(r"(\*|([0-9A-Za-z]+)(?:-([0-9A-Za-z]+))?)(?:/([0-9]+))?")
_NUMBER = re.compile(r"[0-9]+")


def _value(token, names, low, high, name):
    if _NUMBER.fullmatch(token):
        value = int(token)
    elif token.upper() in names:
        value = names[token.upper()]
    else:
        raise ValueError(f"invalid {name} value: {token!r}")
    if not low <= value <= high:
        raise ValueError(f"{name} value out of range: {token!r}")
    return value


def _parse_field(text, name, low, high, names):
    values = set()
    for item in text.split(","):
        match = _ITEM.fullmatch(item)
        if match is None:
            raise ValueError(f"invalid {name} item: {item!r}")
        token, start, end, step_text = match.groups()
        step = 1
        if step_text is not None:
            step = int(step_text)
            if step == 0:
                raise ValueError(f"step must be at least 1: {item!r}")
        if token == "*":
            first, last = low, high
        elif end is not None:
            first = _value(start, names, low, high, name)
            last = _value(end, names, low, high, name)
            if first > last:
                raise ValueError(f"range start after end: {item!r}")
        else:
            first = _value(start, names, low, high, name)
            last = high if step_text is not None else first
        values.update(range(first, last + 1, step))
    return values


def _parse(expr):
    if not isinstance(expr, str):
        raise TypeError(f"expr must be str, not {type(expr).__name__}")
    text = expr.strip()
    text = _SHORTCUTS.get(text.lower(), text)
    parts = re.split(r"[ \t]+", text)
    if len(parts) != 5:
        raise ValueError(f"expected 5 fields, got {len(parts)}: {expr!r}")

    sets, restricted = [], []
    for part, (name, low, high, names) in zip(parts, _FIELDS):
        values = _parse_field(part, name, low, high, names)
        if name == "day of week":
            # 7 is an alias for Sunday (0).
            values = {value % 7 for value in values}
        sets.append(values)
        restricted.append(part != "*")
    return sets, restricted


def _day_matches(day, dom_set, dow_set, dom_restricted, dow_restricted):
    dom_ok = day.day in dom_set
    dow_ok = (day.weekday() + 1) % 7 in dow_set  # cron: Sunday = 0
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def _five_years_after(after):
    try:
        return after.replace(year=after.year + 5)
    except ValueError:  # Feb 29 with no Feb 29 five years on
        return after.replace(year=after.year + 5, month=3, day=1)


def next_run(expr, after):
    """Return the first minute strictly after `after` matching the cron `expr`."""
    (minutes, hours, days_of_month, months, days_of_week), restricted = _parse(expr)
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _five_years_after(after)

    day = start.date()
    while day <= limit.date():
        if day.month in months and _day_matches(
            day, days_of_month, days_of_week, restricted[2], restricted[4]
        ):
            for hour in sorted(hours):
                for minute in sorted(minutes):
                    candidate = datetime.combine(day, time(hour, minute))
                    if candidate < start:
                        continue
                    if candidate > limit:
                        raise ValueError(f"no matching time within 5 years: {expr!r}")
                    return candidate
        day += timedelta(days=1)
    raise ValueError(f"no matching time within 5 years: {expr!r}")
