"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

import re
from calendar import monthrange
from datetime import date, datetime


_MONTHS = {
    name: index
    for index, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
    )
}
_WEEKDAYS = {
    name: index for index, name in enumerate(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"))
}
_SHORTCUTS = {
    "@YEARLY": "0 0 1 1 *",
    "@ANNUALLY": "0 0 1 1 *",
    "@MONTHLY": "0 0 1 * *",
    "@WEEKLY": "0 0 * * 0",
    "@DAILY": "0 0 * * *",
    "@MIDNIGHT": "0 0 * * *",
    "@HOURLY": "0 * * * *",
}


def _value(token: str, minimum: int, maximum: int, names: dict[str, int]) -> int:
    if token in names:
        return names[token]
    if not re.fullmatch(r"[0-9]+", token):
        raise ValueError(f"Invalid cron value: {token!r}")
    value = int(token)
    if not minimum <= value <= maximum:
        raise ValueError(f"Cron value must be between {minimum} and {maximum}: {token!r}")
    return value


def _parse_field(field: str, minimum: int, maximum: int, names: dict[str, int]) -> set[int]:
    values: set[int] = set()
    for item in field.split(","):
        base, separator, step_text = item.partition("/")
        step = 1
        if separator:
            if not re.fullmatch(r"[0-9]+", step_text) or int(step_text) < 1:
                raise ValueError(f"Invalid cron step: {step_text!r}")
            step = int(step_text)
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start = _value(start_text, minimum, maximum, names)
            end = _value(end_text, minimum, maximum, names)
            if start > end:
                raise ValueError(f"Cron range must be ascending: {base!r}")
        else:
            start = _value(base, minimum, maximum, names)
            end = maximum if separator else start
        values.update(range(start, end + 1, step))
    return values


def _day_matches(day: date, fields: list[str], days: set[int], weekdays: set[int]) -> bool:
    is_month_day = day.day in days
    is_weekday = (day.weekday() + 1) % 7 in weekdays
    if fields[2] == "*":
        return fields[4] == "*" or is_weekday
    if fields[4] == "*":
        return is_month_day
    return is_month_day or is_weekday


def _search_limit(after: datetime) -> datetime:
    if after.year > 9994:
        return datetime.max
    year = after.year + 5
    day = min(after.day, monthrange(year, after.month)[1])
    return after.replace(year=year, day=day)


def next_run(expr: str, after: datetime) -> datetime:
    """Return the earliest matching minute strictly after a naive datetime.

    Args:
        expr: A five-field cron expression or supported shortcut.
        after: The exclusive lower bound for the search, without a time zone.

    Returns:
        The first matching datetime, with seconds and microseconds set to zero.

    Raises:
        TypeError: If expr is not a string.
        ValueError: If expr is invalid or no match exists within five years.
    """
    if not isinstance(expr, str):
        raise TypeError("Cron expression must be a string")
    expression = expr.strip().upper()
    fields = re.split(r"[ \t]+", _SHORTCUTS.get(expression, expression))
    if len(fields) != 5:
        raise ValueError("Cron expression must contain five fields")
    minutes = sorted(_parse_field(fields[0], 0, 59, {}))
    hours = sorted(_parse_field(fields[1], 0, 23, {}))
    days = _parse_field(fields[2], 1, 31, {})
    months = _parse_field(fields[3], 1, 12, _MONTHS)
    weekdays = {value % 7 for value in _parse_field(fields[4], 0, 7, _WEEKDAYS)}
    limit = _search_limit(after)
    for ordinal in range(after.toordinal(), limit.toordinal() + 1):
        day = date.fromordinal(ordinal)
        if day.month not in months or not _day_matches(day, fields, days, weekdays):
            continue
        for hour in hours:
            for minute in minutes:
                candidate = datetime(day.year, day.month, day.day, hour, minute)
                if after < candidate <= limit:
                    return candidate
    raise ValueError("No matching cron minute exists within five years after 'after'")
