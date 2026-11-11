"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import calendar
import re
from bisect import bisect_right
from datetime import date, datetime


_MONTHS = {name: i for i, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
_WEEKDAYS = {name: i for i, name in enumerate(
    ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"))}
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
        if re.fullmatch(r"[0-9]+", token):
            number = int(token)
        elif names is not None and token.upper() in names:
            number = names[token.upper()]
        else:
            raise ValueError("Invalid cron value: " + token)
        if not minimum <= number <= maximum:
            raise ValueError("Cron value out of range: " + token)
        return number

    result = set()
    for item in field.split(","):
        parts = item.split("/")
        if len(parts) > 2:
            raise ValueError("Invalid cron step: " + item)
        base = parts[0]
        step = 1
        if len(parts) == 2:
            if not re.fullmatch(r"[0-9]+", parts[1]):
                raise ValueError("Invalid cron step: " + item)
            step = int(parts[1])
            if step < 1:
                raise ValueError("Cron step must be positive")
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            ends = base.split("-")
            if len(ends) != 2:
                raise ValueError("Invalid cron range: " + item)
            start, end = map(value, ends)
            if start > end:
                raise ValueError("Cron ranges cannot wrap around")
        else:
            start = value(base)
            end = maximum if len(parts) == 2 else start
        result.update(range(start, end + 1, step))
    return result


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after ``after``, within five years."""
    if not isinstance(expr, str):
        raise TypeError("Cron expression must be a string")
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    fields = re.split(r"[ \t]+", expr)
    if len(fields) != 5:
        raise ValueError("Cron expressions require five fields")
    minutes = _parse_field(fields[0], 0, 59)
    hours = _parse_field(fields[1], 0, 23)
    month_days = _parse_field(fields[2], 1, 31)
    months = _parse_field(fields[3], 1, 12, _MONTHS)
    week_days = {n % 7 for n in _parse_field(fields[4], 0, 7, _WEEKDAYS)}
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"
    times = sorted(hour * 60 + minute for hour in hours for minute in minutes)

    # Preserve the calendar anniversary, clamping February 29 to February 28.
    # Near datetime.max, search all remaining representable minutes.
    if after.year + 5 > datetime.max.year:
        deadline = datetime.max
    else:
        last_day = calendar.monthrange(after.year + 5, after.month)[1]
        deadline = after.replace(year=after.year + 5, day=min(after.day, last_day))

    first_day = after.date().toordinal()
    for ordinal in range(first_day, deadline.date().toordinal() + 1):
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
        index = bisect_right(times, after.hour * 60 + after.minute) if ordinal == first_day else 0
        if index < len(times):
            hour, minute = divmod(times[index], 60)
            candidate = datetime(day.year, day.month, day.day, hour, minute)
            if candidate <= deadline:
                return candidate
    raise ValueError("No matching minute within five years")
