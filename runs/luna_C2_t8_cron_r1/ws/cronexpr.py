"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import calendar
import re
from datetime import datetime, timedelta


_MONTHS = {name.upper(): i for i, name in enumerate(calendar.month_abbr) if name}
_DAYS = {name.upper(): (i + 1) % 7 for i, name in enumerate(calendar.day_abbr)}
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _field(source, low, high, names=None, sunday=False):
    values = set()

    def number(token):
        if names and token.upper() in names:
            return names[token.upper()]
        if not re.fullmatch(r"\d+", token):
            raise ValueError("invalid cron field")
        value = int(token)
        if not low <= value <= high:
            raise ValueError("cron value out of range")
        return value

    for item in source.split(","):
        if not item:
            raise ValueError("empty cron item")
        parts = item.split("/")
        if len(parts) > 2 or (len(parts) == 2 and not re.fullmatch(r"\d+", parts[1])):
            raise ValueError("invalid cron step")
        step = int(parts[1]) if len(parts) == 2 else 1
        if step < 1:
            raise ValueError("invalid cron step")
        base = parts[0]
        if base == "*":
            start, end = low, high
        elif "-" in base:
            ends = base.split("-")
            if len(ends) != 2:
                raise ValueError("invalid cron range")
            start, end = number(ends[0]), number(ends[1])
            if start > end:
                raise ValueError("reversed cron range")
        else:
            start = number(base)
            end = high if len(parts) == 2 else start
        values.update(range(start, end + 1, step))
    if sunday and 7 in values:
        values.remove(7)
        values.add(0)
    return values


def next_run(expr: str, after: datetime) -> datetime:
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")
    expr = _SHORTCUTS.get(expr.strip().lower(), expr.strip())
    fields = re.split(r"[ \t]+", expr) if expr else []
    if len(fields) != 5:
        raise ValueError("expected five cron fields")
    minute = _field(fields[0], 0, 59)
    hour = _field(fields[1], 0, 23)
    dom = _field(fields[2], 1, 31)
    month = _field(fields[3], 1, 12, _MONTHS)
    dow = _field(fields[4], 0, 7, _DAYS, sunday=True)
    dom_restricted, dow_restricted = fields[2] != "*", fields[4] != "*"
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:
        limit = after.replace(year=after.year + 5, day=28)
    day = after.date()
    while day <= limit.date():
        weekday = (day.weekday() + 1) % 7
        dow_match = weekday in dow
        if dom_restricted and dow_restricted:
            day_match = day.day in dom or dow_match
        elif dom_restricted:
            day_match = day.day in dom
        elif dow_restricted:
            day_match = dow_match
        else:
            day_match = True
        if day.month in month and day_match:
            for h in sorted(hour):
                for m in sorted(minute):
                    candidate = datetime(day.year, day.month, day.day, h, m)
                    if candidate > after and candidate <= limit:
                        return candidate
        day += timedelta(days=1)
    raise ValueError("no matching minute within five years")
