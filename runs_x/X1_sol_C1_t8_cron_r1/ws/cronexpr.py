"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import calendar
import re
from datetime import datetime, timedelta


_MONTHS = {name: index for index, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
_WEEKDAYS = {name: index for index, name in enumerate(
    ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"))}
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _parse_field(field, minimum, maximum, names=None):
    """Expand a field before normalizing the Sunday alias."""
    def value(token):
        if names and token.upper() in names:
            result = names[token.upper()]
        elif re.fullmatch(r"[0-9]+", token):
            result = int(token)
        else:
            raise ValueError("Invalid cron value: " + token)
        if not minimum <= result <= maximum:
            raise ValueError("Cron value outside field range: " + token)
        return result

    values = set()
    for item in field.split(","):
        parts = item.split("/")
        if len(parts) > 2:
            raise ValueError("Invalid cron step")
        step = 1
        if len(parts) == 2:
            if not re.fullmatch(r"[0-9]+", parts[1]):
                raise ValueError("Invalid cron step")
            step = int(parts[1])
            if step < 1:
                raise ValueError("Cron step must be positive")
        base = parts[0]
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            ends = base.split("-")
            if len(ends) != 2:
                raise ValueError("Invalid cron range")
            start, end = map(value, ends)
            if start > end:
                raise ValueError("Cron ranges cannot wrap around")
        else:
            start = value(base)
            end = maximum if len(parts) == 2 else start
        values.update(range(start, end + 1, step))
    return values


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after ``after``, within five years."""
    if not isinstance(expr, str):
        raise TypeError("Cron expression must be a string")
    expression = expr.strip()
    expression = _SHORTCUTS.get(expression.lower(), expression)
    fields = re.split(r"[ \t]+", expression)
    if len(fields) != 5:
        raise ValueError("Cron expression must have five fields")
    minutes, hours, days, months, weekdays = (
        _parse_field(fields[0], 0, 59),
        _parse_field(fields[1], 0, 23),
        _parse_field(fields[2], 1, 31),
        _parse_field(fields[3], 1, 12, _MONTHS),
        _parse_field(fields[4], 0, 7, _WEEKDAYS),
    )
    weekdays = {day % 7 for day in weekdays}
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"

    # Clamp a leap-day anniversary to the final day of February.
    if after.year + 5 <= datetime.max.year:
        year = after.year + 5
        day = min(after.day, calendar.monthrange(year, after.month)[1])
        limit = after.replace(year=year, day=day)
    else:
        limit = datetime.max

    date = after.date()
    times = [(hour, minute) for hour in sorted(hours) for minute in sorted(minutes)]
    while date <= limit.date():
        dom_match = date.day in days
        dow_match = (date.weekday() + 1) % 7 in weekdays
        if dom_restricted and dow_restricted:
            day_matches = dom_match or dow_match
        elif dom_restricted:
            day_matches = dom_match
        elif dow_restricted:
            day_matches = dow_match
        else:
            day_matches = True
        if date.month in months and day_matches:
            for hour, minute in times:
                candidate = datetime(date.year, date.month, date.day, hour, minute)
                if after < candidate <= limit:
                    return candidate
        if date == limit.date():
            break
        date += timedelta(days=1)
    raise ValueError("No matching minute within five years")
