"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta


_MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_DOW_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
}

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _is_uint(text):
    return bool(text) and all("0" <= ch <= "9" for ch in text)


def _field_value(text, names, lo, hi):
    if not text:
        raise ValueError("empty field value")
    if names is not None and text.upper() in names:
        value = names[text.upper()]
    elif _is_uint(text):
        value = int(text)
    else:
        raise ValueError("invalid field value: %r" % (text,))
    if value < lo or value > hi:
        raise ValueError("value out of range: %r" % (text,))
    return value


def _parse_field(token, lo, hi, names=None):
    """Expand one cron field into the set of matching integer values."""
    values = set()
    for item in token.split(","):
        if not item:
            raise ValueError("empty list item")

        step = None
        base = item
        if "/" in item:
            parts = item.split("/")
            if len(parts) != 2:
                raise ValueError("invalid step: %r" % (item,))
            base, step_text = parts
            if not _is_uint(step_text):
                raise ValueError("invalid step: %r" % (item,))
            step = int(step_text)
            if step < 1:
                raise ValueError("invalid step: %r" % (item,))

        if base == "*":
            start, end = lo, hi
            values.update(range(start, end + 1, step if step else 1))
            continue

        if "-" in base:
            parts = base.split("-")
            if len(parts) != 2:
                raise ValueError("invalid range: %r" % (base,))
            start = _field_value(parts[0], names, lo, hi)
            end = _field_value(parts[1], names, lo, hi)
            if start > end:
                raise ValueError("descending range: %r" % (base,))
            values.update(range(start, end + 1, step if step else 1))
            continue

        start = _field_value(base, names, lo, hi)
        if step is None:
            values.add(start)
        else:
            values.update(range(start, hi + 1, step))
    return values


def _parse_expression(expr):
    text = expr.strip()
    text = _SHORTCUTS.get(text.lower(), text)

    fields = re.split(r"[ \t]+", text)
    if len(fields) != 5:
        raise ValueError("expected 5 fields, got %d" % (len(fields),))

    minute = _parse_field(fields[0], 0, 59)
    hour = _parse_field(fields[1], 0, 23)
    day = _parse_field(fields[2], 1, 31)
    month = _parse_field(fields[3], 1, 12, _MONTH_NAMES)
    weekday = {value % 7 for value in _parse_field(fields[4], 0, 7, _DOW_NAMES)}

    return (
        sorted(minute),
        sorted(hour),
        day,
        month,
        weekday,
        fields[2] != "*",
        fields[4] != "*",
    )


def _five_years_after(value):
    try:
        return value.replace(year=value.year + 5)
    except ValueError:  # 29 February in a non-leap target year
        return value.replace(year=value.year + 5, day=28)


def next_run(expr, after):
    """Return the earliest minute strictly after ``after`` matching ``expr``."""
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")

    minutes, hours, days, months, weekdays, dom_restricted, dow_restricted = (
        _parse_expression(expr)
    )

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _five_years_after(after)

    current = start.date()
    last = limit.date()

    while current <= last:
        if current.month in months:
            cron_dow = (current.weekday() + 1) % 7
            dom_match = current.day in days
            dow_match = cron_dow in weekdays
            if dom_restricted and dow_restricted:
                day_match = dom_match or dow_match
            elif dom_restricted:
                day_match = dom_match
            elif dow_restricted:
                day_match = dow_match
            else:
                day_match = True

            if day_match:
                for hour in hours:
                    for minute in minutes:
                        candidate = datetime(
                            current.year, current.month, current.day, hour, minute
                        )
                        if candidate >= start:
                            if candidate > limit:
                                raise ValueError("no matching minute found")
                            return candidate

        current += timedelta(days=1)

    raise ValueError("no matching minute found")
