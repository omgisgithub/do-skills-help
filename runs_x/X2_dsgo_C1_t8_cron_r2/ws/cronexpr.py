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

_MONTH_NAMES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_DOW_NAMES = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}

_NUMBER_RE = re.compile(r"[0-9]+")


def _parse_value(token, names, lo, hi):
    """Resolve a single value or name, validating it against the field range."""
    upper = token.upper()
    if names is not None and upper in names:
        return names[upper]
    if not _NUMBER_RE.fullmatch(token):
        raise ValueError("invalid cron value: %r" % (token,))
    value = int(token)
    if value < lo or value > hi:
        raise ValueError("cron value out of range: %r" % (token,))
    return value


def _parse_field(text, lo, hi, names=None):
    """Parse one cron field into the set of allowed values."""
    values = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty cron item in %r" % (text,))

        parts = item.split("/")
        if len(parts) > 2:
            raise ValueError("invalid cron item: %r" % (item,))

        base = parts[0]
        step = None
        if len(parts) == 2:
            step_text = parts[1]
            if not _NUMBER_RE.fullmatch(step_text):
                raise ValueError("invalid step in %r" % (item,))
            step = int(step_text)
            if step < 1:
                raise ValueError("step must be at least 1: %r" % (item,))

        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            bounds = base.split("-")
            if len(bounds) != 2 or not bounds[0] or not bounds[1]:
                raise ValueError("invalid range: %r" % (item,))
            start = _parse_value(bounds[0], names, lo, hi)
            end = _parse_value(bounds[1], names, lo, hi)
            if start > end:
                raise ValueError("range start after end: %r" % (item,))
        else:
            value = _parse_value(base, names, lo, hi)
            if step is None:
                values.add(value)
                continue
            start, end = value, hi

        if step is None:
            step = 1
        values.update(range(start, end + 1, step))

    return values


def _parse_expression(expr):
    if not isinstance(expr, str):
        raise TypeError("cron expression must be a string")

    text = expr.strip()
    shortcut = _SHORTCUTS.get(text.lower())
    if shortcut is not None:
        fields = shortcut.split(" ")
    else:
        fields = re.split(r"[ \t]+", text)
        if len(fields) != 5:
            raise ValueError("cron expression must have five fields")

    minutes = _parse_field(fields[0], 0, 59)
    hours = _parse_field(fields[1], 0, 23)
    days_of_month = _parse_field(fields[2], 1, 31)
    months = _parse_field(fields[3], 1, 12, _MONTH_NAMES)
    days_of_week_raw = _parse_field(fields[4], 0, 7, _DOW_NAMES)

    # Normalise Sunday: both 0 and 7 mean Sunday.
    days_of_week = {0 if value == 7 else value for value in days_of_week_raw}

    return (
        minutes,
        hours,
        days_of_month,
        months,
        days_of_week,
        fields[2] != "*",
        fields[4] != "*",
    )


def _day_matches(date, days_of_month, days_of_week, dom_restricted, dow_restricted):
    # cron: Sunday == 0, Monday == 1, ... Saturday == 6
    weekday = (date.weekday() + 1) % 7
    dom_ok = date.day in days_of_month
    dow_ok = weekday in days_of_week

    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    if dom_restricted:
        return dom_ok
    if dow_restricted:
        return dow_ok
    return True


def _cutoff(after):
    """Return the last instant within five calendar years after *after*."""
    try:
        return after.replace(year=after.year + 5)
    except (ValueError, OverflowError):
        if after.month == 2 and after.day == 29:
            try:
                return after.replace(year=after.year + 5, day=28)
            except (ValueError, OverflowError):
                return datetime.max
        return datetime.max


def next_run(expr, after):
    """Return the earliest matching minute strictly after *after*."""
    minutes, hours, days_of_month, months, days_of_week, dom_restricted, dow_restricted = (
        _parse_expression(expr)
    )

    cutoff = _cutoff(after)
    try:
        start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no matching minute within five years after the given datetime")

    if start > cutoff:
        raise ValueError("no matching minute within five years after the given datetime")

    sorted_minutes = sorted(minutes)
    sorted_hours = sorted(hours)
    start_date = start.date()

    current_date = start_date
    while True:
        midnight = datetime(current_date.year, current_date.month, current_date.day)
        if midnight > cutoff:
            raise ValueError("no matching minute within five years after the given datetime")

        if current_date.month in months and _day_matches(
            current_date, days_of_month, days_of_week, dom_restricted, dow_restricted
        ):
            for hour in sorted_hours:
                if current_date == start_date and hour < start.hour:
                    continue
                for minute in sorted_minutes:
                    if current_date == start_date and hour == start.hour and minute < start.minute:
                        continue
                    candidate = datetime(
                        current_date.year, current_date.month, current_date.day, hour, minute
                    )
                    if candidate > cutoff:
                        raise ValueError(
                            "no matching minute within five years after the given datetime"
                        )
                    return candidate

        try:
            current_date += timedelta(days=1)
        except OverflowError:
            raise ValueError("no matching minute within five years after the given datetime")
