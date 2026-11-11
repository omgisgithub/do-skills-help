"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
from bisect import bisect_left
from calendar import monthrange
from datetime import datetime, timedelta
import re


_MONTHS = dict(zip(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), range(1, 13)
))
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


def _parse_field(field, minimum, maximum, names):
    """Expand a field before normalizing any Sunday aliases."""
    def value(token):
        if token.upper() in names:
            number = names[token.upper()]
        elif re.fullmatch(r"[0-9]+", token):
            number = int(token)
        else:
            raise ValueError("Invalid cron value: " + token)
        if not minimum <= number <= maximum:
            raise ValueError("Cron value out of range: " + token)
        return number

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
            bounds = base.split("-")
            if len(bounds) != 2:
                raise ValueError("Invalid cron range: " + base)
            start, end = map(value, bounds)
            if start > end:
                raise ValueError("Cron ranges cannot wrap around")
        else:
            start = value(base)
            end = maximum if len(parts) == 2 else start
        values.update(range(start, end + 1, step))
    return values


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after ``after``, within five years.

    The horizon is the calendar anniversary (February 28 for a leap-day
    anniversary in a non-leap year), capped at datetime.max.
    """
    if not isinstance(expr, str):
        raise TypeError("Cron expression must be a string")
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    fields = re.split(r"[ \t]+", expr)
    if len(fields) != 5:
        raise ValueError("Cron expression must contain five fields")

    minutes = _parse_field(fields[0], 0, 59, {})
    hours = _parse_field(fields[1], 0, 23, {})
    month_days = _parse_field(fields[2], 1, 31, {})
    months = _parse_field(fields[3], 1, 12, _MONTHS)
    week_days = {n % 7 for n in _parse_field(fields[4], 0, 7, _WEEKDAYS)}
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"

    if after.year + 5 > datetime.max.year:
        limit = datetime.max
    else:
        year = after.year + 5
        day = min(after.day, monthrange(year, after.month)[1])
        limit = after.replace(year=year, day=day)

    try:
        first = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("No matching minute within five years") from None

    times = sorted(hour * 60 + minute for hour in hours for minute in minutes)
    date = first.date()
    while date <= limit.date():
        dom_matches = date.day in month_days
        dow_matches = (date.weekday() + 1) % 7 in week_days
        if dom_restricted and dow_restricted:
            day_matches = dom_matches or dow_matches
        elif dom_restricted:
            day_matches = dom_matches
        elif dow_restricted:
            day_matches = dow_matches
        else:
            day_matches = True

        if date.month in months and day_matches:
            earliest = first.hour * 60 + first.minute if date == first.date() else 0
            index = bisect_left(times, earliest)
            if index < len(times):
                hour, minute = divmod(times[index], 60)
                candidate = datetime(date.year, date.month, date.day, hour, minute)
                if candidate <= limit:
                    return candidate
                break
        if date == limit.date():
            break
        date += timedelta(days=1)

    raise ValueError("No matching minute within five years")
