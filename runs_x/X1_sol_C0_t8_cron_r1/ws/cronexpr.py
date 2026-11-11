"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
from bisect import bisect_left
from calendar import monthrange
from datetime import datetime, timedelta
import re


_MONTHS = dict(zip(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), range(1, 13)
))
_WEEKDAYS = dict(zip(
    ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"), range(7)
))
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _parse_field(field, minimum, maximum, names):
    def value(token):
        if token.upper() in names:
            result = names[token.upper()]
        elif re.fullmatch(r"[0-9]+", token):
            result = int(token)
        else:
            raise ValueError("Invalid cron value: " + token)
        if not minimum <= result <= maximum:
            raise ValueError("Cron value out of range: " + token)
        return result

    values = set()
    for item in field.split(","):
        parts = item.split("/")
        if len(parts) > 2:
            raise ValueError("Invalid cron step: " + item)
        step = 1
        if len(parts) == 2:
            if not re.fullmatch(r"[0-9]+", parts[1]):
                raise ValueError("Invalid cron step: " + item)
            step = int(parts[1])
            if step < 1:
                raise ValueError("Cron step must be positive")
        base = parts[0]
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            ends = base.split("-")
            if len(ends) != 2:
                raise ValueError("Invalid cron range: " + base)
            start, end = map(value, ends)
        else:
            start = value(base)
            end = maximum if len(parts) == 2 else start
        if start > end:
            raise ValueError("Cron ranges cannot wrap around")
        values.update(range(start, end + 1, step))
    return values


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after ``after``, within five years."""
    if not isinstance(expr, str):
        raise TypeError("Cron expression must be a string")
    expr = expr.strip(" \t")
    expr = _SHORTCUTS.get(expr.lower(), expr)
    fields = re.split(r"[ \t]+", expr)
    if len(fields) != 5:
        raise ValueError("Cron expression must contain five fields")
    minutes, hours, days, months, weekdays = (
        _parse_field(field, low, high, names)
        for field, low, high, names in zip(
            fields, (0, 0, 1, 1, 0), (59, 23, 31, 12, 7),
            ({}, {}, {}, _MONTHS, _WEEKDAYS)
        )
    )
    weekdays = {day % 7 for day in weekdays}
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"
    times = sorted(hour * 60 + minute for hour in hours for minute in minutes)

    # Clamp a leap-day anniversary to February's last day. At the datetime
    # ceiling, search all remaining representable minutes.
    if after.year + 5 > 9999:
        limit = datetime.max
    else:
        year = after.year + 5
        day = min(after.day, monthrange(year, after.month)[1])
        limit = after.replace(year=year, day=day)

    date = after.date()
    while date <= limit.date():
        dom_matches = date.day in days
        dow_matches = (date.weekday() + 1) % 7 in weekdays
        if dom_restricted and dow_restricted:
            day_matches = dom_matches or dow_matches
        elif dom_restricted:
            day_matches = dom_matches
        elif dow_restricted:
            day_matches = dow_matches
        else:
            day_matches = True
        if date.month in months and day_matches:
            first_minute = (
                after.hour * 60 + after.minute + 1 if date == after.date() else 0
            )
            index = bisect_left(times, first_minute)
            if index < len(times):
                hour, minute = divmod(times[index], 60)
                result = datetime(date.year, date.month, date.day, hour, minute)
                if result <= limit:
                    return result
        if date == limit.date():
            break
        date += timedelta(days=1)
    raise ValueError("No matching minute within five years")
