"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import calendar
import re
from datetime import datetime, timedelta


_MONTHS = dict(zip("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), range(1, 13)))
_WEEKDAYS = dict(zip("SUN MON TUE WED THU FRI SAT".split(), range(7)))
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_ITEM = re.compile(r"(\*|[0-9]+|[A-Za-z]+)(?:-([0-9]+|[A-Za-z]+))?(?:/([0-9]+))?")


def _parse_field(field, minimum, maximum, names=None):
    def value(token):
        if re.fullmatch(r"[0-9]+", token):
            number = int(token)
        else:
            number = (names or {}).get(token.upper())
        if number is None or not minimum <= number <= maximum:
            raise ValueError("Invalid cron value: " + token)
        return number

    values = set()
    for item in field.split(","):
        match = _ITEM.fullmatch(item)
        if match is None:
            raise ValueError("Invalid cron item: " + item)
        start, end, step = match.groups()
        stride = int(step) if step is not None else 1
        if stride < 1 or (start == "*" and end is not None):
            raise ValueError("Invalid cron item: " + item)
        if start == "*":
            first, last = minimum, maximum
        else:
            first = value(start)
            last = value(end) if end is not None else (maximum if step is not None else first)
        if first > last:
            raise ValueError("Descending cron range: " + item)
        values.update(range(first, last + 1, stride))
    return values


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after ``after``, within five years."""
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")
    expression = expr.strip()
    expression = _SHORTCUTS.get(expression.lower(), expression)
    fields = re.split(r"[ \t]+", expression)
    if len(fields) != 5:
        raise ValueError("A cron expression must have five fields")
    minutes = _parse_field(fields[0], 0, 59)
    hours = _parse_field(fields[1], 0, 23)
    days = _parse_field(fields[2], 1, 31)
    months = _parse_field(fields[3], 1, 12, _MONTHS)
    weekdays = {day % 7 for day in _parse_field(fields[4], 0, 7, _WEEKDAYS)}
    day_restricted = fields[2] != "*"
    weekday_restricted = fields[4] != "*"

    # A leap-day anniversary falls on February 28 in a non-leap year.
    if after.year + 5 <= datetime.max.year:
        year = after.year + 5
        last_day = calendar.monthrange(year, after.month)[1]
        deadline = after.replace(year=year, day=min(after.day, last_day))
    else:
        deadline = datetime.max

    times = [(hour, minute) for hour in sorted(hours) for minute in sorted(minutes)]
    current = after.replace(hour=0, minute=0, second=0, microsecond=0)
    while current.date() <= deadline.date():
        day_match = current.day in days
        weekday_match = (current.weekday() + 1) % 7 in weekdays
        if day_restricted and weekday_restricted:
            matches = day_match or weekday_match
        elif day_restricted:
            matches = day_match
        elif weekday_restricted:
            matches = weekday_match
        else:
            matches = True
        if current.month in months and matches:
            for hour, minute in times:
                candidate = current.replace(hour=hour, minute=minute)
                if after < candidate <= deadline:
                    return candidate
        if current.date() == deadline.date():
            break
        current += timedelta(days=1)
    raise ValueError("No matching minute within five years")
