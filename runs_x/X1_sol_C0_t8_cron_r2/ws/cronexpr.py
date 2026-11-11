"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
from bisect import bisect_left
from calendar import monthrange
from datetime import date, datetime
import re


_MONTHS = dict(zip(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
    range(1, 13),
))
_WEEKDAYS = dict(zip(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"), range(7)))
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _parse_field(field, minimum, maximum, names=None):
    def value(token):
        if names and token.upper() in names:
            return names[token.upper()]
        if not re.fullmatch(r"[0-9]+", token):
            raise ValueError("Invalid cron value: {!r}".format(token))
        number = int(token)
        if not minimum <= number <= maximum:
            raise ValueError("Cron value out of range: {!r}".format(token))
        return number

    result = set()
    for item in field.split(","):
        parts = item.split("/")
        if len(parts) > 2:
            raise ValueError("Invalid cron item: {!r}".format(item))
        step = 1
        if len(parts) == 2:
            if not re.fullmatch(r"[0-9]+", parts[1]):
                raise ValueError("Invalid cron step: {!r}".format(parts[1]))
            step = int(parts[1])
            if step < 1:
                raise ValueError("Cron step must be positive")
        base = parts[0]
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            bounds = base.split("-")
            if len(bounds) != 2:
                raise ValueError("Invalid cron range: {!r}".format(base))
            start, end = map(value, bounds)
            if start > end:
                raise ValueError("Cron ranges must be ascending")
        else:
            start = value(base)
            end = maximum if len(parts) == 2 else start
        result.update(range(start, end + 1, step))
    return result


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after ``after``, within five years.

    The five-year boundary is the same calendar date and time five years later;
    February 29 is clamped to February 28 when necessary.
    """
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")
    expression = expr.strip()
    expression = _SHORTCUTS.get(expression.lower(), expression)
    fields = re.split(r"[ \t]+", expression)
    if len(fields) != 5:
        raise ValueError("A cron expression must contain five fields")
    minutes = _parse_field(fields[0], 0, 59)
    hours = _parse_field(fields[1], 0, 23)
    month_days = _parse_field(fields[2], 1, 31)
    months = _parse_field(fields[3], 1, 12, _MONTHS)
    week_days = {day % 7 for day in _parse_field(fields[4], 0, 7, _WEEKDAYS)}
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"
    times = sorted(hour * 60 + minute for hour in hours for minute in minutes)

    if after.year + 5 > datetime.max.year:
        deadline = datetime.max
    else:
        year = after.year + 5
        day = min(after.day, monthrange(year, after.month)[1])
        deadline = after.replace(year=year, day=day)

    for ordinal in range(after.date().toordinal(), deadline.date().toordinal() + 1):
        day = date.fromordinal(ordinal)
        if day.month not in months:
            continue
        dom_matches = day.day in month_days
        dow_matches = (day.weekday() + 1) % 7 in week_days
        if dom_restricted and dow_restricted:
            matches = dom_matches or dow_matches
        elif dom_restricted:
            matches = dom_matches
        elif dow_restricted:
            matches = dow_matches
        else:
            matches = True
        if not matches:
            continue
        earliest = after.hour * 60 + after.minute + 1 if day == after.date() else 0
        index = bisect_left(times, earliest)
        if index < len(times):
            hour, minute = divmod(times[index], 60)
            candidate = datetime(day.year, day.month, day.day, hour, minute)
            if candidate <= deadline:
                return candidate
    raise ValueError("No matching minute exists within five years")
