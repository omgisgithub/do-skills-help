"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, time, timedelta

_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
_WEEKDAYS = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

# (field name, lowest value, highest value, named values) in expression order.
_FIELDS = (
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day of month", 1, 31, {}),
    ("month", 1, 12, _MONTHS),
    ("day of week", 0, 7, _WEEKDAYS),
)

_ITEM = re.compile(
    r"(?P<start>\*|[0-9]+|[A-Za-z]+)(?:-(?P<end>[0-9]+|[A-Za-z]+))?(?:/(?P<step>[0-9]+))?"
)


def _value(token, names, low, high):
    if token.isdigit():
        value = int(token)
    else:
        value = names.get(token.upper())
        if value is None:
            raise ValueError(f"unknown name {token!r}")
    if not low <= value <= high:
        raise ValueError(f"{token!r} is out of range {low}-{high}")
    return value


def _parse_field(text, name, low, high, names):
    """Return the sorted list of values a field allows."""
    values = set()
    for item in text.split(","):
        match = _ITEM.fullmatch(item)
        if match is None:
            raise ValueError(f"bad item {item!r} in {name} field")
        start, end, step = match.group("start", "end", "step")
        step_size = int(step) if step is not None else 1
        if step_size < 1:
            raise ValueError(f"step must be at least 1 in {item!r}")
        if start == "*":
            if end is not None:
                raise ValueError(f"'*' cannot be a range in {item!r}")
            first, last = low, high
        else:
            first = _value(start, names, low, high)
            if end is not None:
                last = _value(end, names, low, high)
                if first > last:
                    raise ValueError(f"range {item!r} runs backwards")
            elif step is None:
                last = first
            else:
                last = high
        for value in range(first, last + 1, step_size):
            # Day of week 7 is Sunday, same as 0.
            values.add(value % 7 if name == "day of week" else value)
    return sorted(values)


def _five_years_later(moment):
    try:
        return moment.replace(year=moment.year + 5)
    except ValueError:  # 29 February with no matching day in the target year
        return moment.replace(year=moment.year + 5, day=28)


def _day_matches(day, days_of_month, days_of_week, dom_restricted, dow_restricted):
    dom_ok = day.day in days_of_month
    dow_ok = day.isoweekday() % 7 in days_of_week
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def next_run(expr: str, after: datetime) -> datetime:
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    text = expr.strip()
    text = _SHORTCUTS.get(text.lower(), text)
    raw_fields = re.split(r"[ \t]+", text)
    if len(raw_fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(raw_fields)}: {expr!r}")

    minutes, hours, days_of_month, months, days_of_week = (
        _parse_field(raw, *spec) for raw, spec in zip(raw_fields, _FIELDS)
    )
    dom_restricted = raw_fields[2] != "*"
    dow_restricted = raw_fields[4] != "*"

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _five_years_later(after)
    day = start.date()
    while day <= limit.date():
        if day.month in months and _day_matches(
            day, days_of_month, days_of_week, dom_restricted, dow_restricted
        ):
            for hour in hours:
                for minute in minutes:
                    candidate = datetime.combine(day, time(hour, minute))
                    if start <= candidate <= limit:
                        return candidate
        day += timedelta(days=1)
    raise ValueError(f"no matching time within 5 years of {after} for {expr!r}")
