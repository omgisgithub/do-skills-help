"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

import re
from calendar import monthrange
from datetime import date, datetime
from typing import Mapping


_MONTHS = {
    name: value
    for value, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
    )
}
_WEEKDAYS = {
    name: value
    for value, name in enumerate(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"))
}
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


def _value(token: str, minimum: int, maximum: int, names: Mapping[str, int]) -> int:
    if token in names:
        value = names[token]
    elif re.fullmatch(r"[0-9]+", token):
        value = int(token)
    else:
        raise ValueError(f"Invalid cron value: {token!r}")
    if not minimum <= value <= maximum:
        raise ValueError(f"Cron value outside {minimum}–{maximum}: {token!r}")
    return value


def _parse_field(
    field: str, minimum: int, maximum: int, names: Mapping[str, int]
) -> set[int]:
    values: set[int] = set()
    for item in field.upper().split(","):
        match = _ITEM.fullmatch(item)
        if match is None:
            raise ValueError(f"Invalid cron item: {item!r}")
        start_token, end_token, step_token = match.groups()
        step = int(step_token) if step_token is not None else 1
        if step < 1:
            raise ValueError("Cron steps must be positive")
        if start_token == "*":
            if end_token is not None:
                raise ValueError("A wildcard cannot be a range endpoint")
            start, end = minimum, maximum
        else:
            start = _value(start_token, minimum, maximum, names)
            end = maximum if step_token is not None else start
            if end_token is not None:
                end = _value(end_token, minimum, maximum, names)
        if start > end:
            raise ValueError("Cron ranges must be ascending")
        values.update(range(start, end + 1, step))
    return values


def _matches_day(
    day: date, days: set[int], weekdays: set[int], restrict_day: bool, restrict_weekday: bool
) -> bool:
    day_matches = day.day in days
    weekday_matches = (day.weekday() + 1) % 7 in weekdays
    if restrict_day and restrict_weekday:
        return day_matches or weekday_matches
    if restrict_day:
        return day_matches
    if restrict_weekday:
        return weekday_matches
    return True


def next_run(expr: str, after: datetime) -> datetime:
    """Return the earliest matching minute strictly after a naive datetime.

    Args:
        expr: A five-field cron expression or a supported shortcut.
        after: The exclusive lower bound for the search, without a time zone.

    Returns:
        The first matching minute within five calendar years of ``after``.

    Raises:
        TypeError: If the expression is not a string.
        ValueError: If the expression is invalid or no matching minute exists
            within five years. A leap-day deadline is clamped to February 28.
    """
    if not isinstance(expr, str):
        raise TypeError("Cron expression must be a string")
    expression = expr.strip()
    expression = _SHORTCUTS.get(expression.lower(), expression)
    fields = re.split(r"[ \t]+", expression)
    if len(fields) != 5:
        raise ValueError("Cron expressions must have exactly five fields")
    minutes = sorted(_parse_field(fields[0], 0, 59, {}))
    hours = sorted(_parse_field(fields[1], 0, 23, {}))
    days = _parse_field(fields[2], 1, 31, {})
    months = _parse_field(fields[3], 1, 12, _MONTHS)
    weekdays = {value % 7 for value in _parse_field(fields[4], 0, 7, _WEEKDAYS)}

    if after.year + 5 > datetime.max.year:
        deadline = datetime.max
    else:
        last_day = monthrange(after.year + 5, after.month)[1]
        deadline = after.replace(year=after.year + 5, day=min(after.day, last_day))
    for ordinal in range(after.toordinal(), deadline.toordinal() + 1):
        day = date.fromordinal(ordinal)
        if day.month not in months or not _matches_day(
            day, days, weekdays, fields[2] != "*", fields[4] != "*"
        ):
            continue
        for hour in hours:
            for minute in minutes:
                candidate = datetime(day.year, day.month, day.day, hour, minute)
                if after < candidate <= deadline:
                    return candidate
    raise ValueError("No matching cron minute exists within five years")
