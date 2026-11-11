"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import calendar
import re
from datetime import datetime, timedelta


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


def _parse_field(field, minimum, maximum, names=None):
    def number(token):
        if names and token.upper() in names:
            return names[token.upper()]
        if not re.fullmatch(r"[0-9]+", token):
            raise ValueError("Invalid cron value: " + token)
        value = int(token)
        if not minimum <= value <= maximum:
            raise ValueError("Cron value outside field range: " + token)
        return value

    values = set()
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
            bounds = base.split("-")
            if len(bounds) != 2:
                raise ValueError("Invalid cron range: " + item)
            start, end = map(number, bounds)
            if start > end:
                raise ValueError("Cron ranges cannot wrap around")
        else:
            start = number(base)
            end = maximum if len(parts) == 2 else start
        values.update(range(start, end + 1, step))
    return values


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute after ``after``, within five years.

    The horizon is the calendar anniversary, clamped to February 28 when
    necessary and to datetime's representable range.
    """
    if not isinstance(expr, str):
        raise TypeError("Cron expression must be a string")
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    fields = re.split(r"[ \t]+", expr)
    if len(fields) != 5:
        raise ValueError("Cron expression must contain five fields")
    minutes = sorted(_parse_field(fields[0], 0, 59))
    hours = sorted(_parse_field(fields[1], 0, 23))
    month_days = _parse_field(fields[2], 1, 31)
    months = _parse_field(fields[3], 1, 12, _MONTHS)
    # Expand ranges and steps before folding Sunday 7 into Sunday 0.
    week_days = {day % 7 for day in _parse_field(fields[4], 0, 7, _WEEKDAYS)}
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"

    if after.year + 5 > datetime.max.year:
        limit = datetime.max
    else:
        year = after.year + 5
        day = min(after.day, calendar.monthrange(year, after.month)[1])
        limit = after.replace(year=year, day=day)
    try:
        first = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("No matching minute within five years") from None

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
            for hour in hours:
                for minute in minutes:
                    candidate = datetime(date.year, date.month, date.day, hour, minute)
                    if first <= candidate <= limit:
                        return candidate
        if date == limit.date():
            break
        date += timedelta(days=1)
    raise ValueError("No matching minute within five years")
