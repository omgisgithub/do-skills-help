"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

import calendar
import re
from datetime import date, datetime
from typing import Mapping, Optional


_MONTHS = {
    name: index
    for index, name in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)
}
_WEEKDAYS = {name: index for index, name in enumerate("SUN MON TUE WED THU FRI SAT".split())}
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _value(token: str, minimum: int, maximum: int, names: Mapping[str, int]) -> int:
    if token.upper() in names:
        value = names[token.upper()]
    elif re.fullmatch(r"[0-9]+", token):
        value = int(token)
    else:
        raise ValueError(f"Invalid cron value: {token!r}")
    if not minimum <= value <= maximum:
        raise ValueError(f"Cron value outside {minimum}..{maximum}: {token!r}")
    return value


def _field(
    field: str, minimum: int, maximum: int, names: Optional[Mapping[str, int]] = None
) -> set[int]:
    values: set[int] = set()
    for item in field.split(","):
        base, slash, step_text = item.partition("/")
        if slash and not re.fullmatch(r"[0-9]+", step_text):
            raise ValueError(f"Invalid cron step: {item!r}")
        step = int(step_text) if slash else 1
        if step < 1:
            raise ValueError("Cron step must be positive")
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            first, last = base.split("-", 1)
            start = _value(first, minimum, maximum, names or {})
            end = _value(last, minimum, maximum, names or {})
        else:
            start = _value(base, minimum, maximum, names or {})
            end = maximum if slash else start
        if start > end:
            raise ValueError(f"Descending cron range: {base!r}")
        values.update(range(start, end + 1, step))
    return values


def _deadline(after: datetime) -> datetime:
    if after.year > datetime.max.year - 5:
        return datetime.max
    year = after.year + 5
    day = min(after.day, calendar.monthrange(year, after.month)[1])
    return after.replace(year=year, day=day)


def next_run(expr: str, after: datetime) -> datetime:
    """Return the earliest matching minute strictly after ``after``.

    Args:
        expr: A five-field cron expression or supported shortcut.
        after: A naive datetime marking the exclusive lower bound.

    Returns:
        The first matching minute within five calendar years.

    Raises:
        TypeError: If expr is not a string.
        ValueError: If expr is invalid or no matching minute exists in the window.
    """
    if not isinstance(expr, str):
        raise TypeError("Cron expression must be a string")
    expression = expr.strip()
    fields = re.split(r"[ \t]+", _SHORTCUTS.get(expression.lower(), expression))
    if len(fields) != 5:
        raise ValueError("Cron expression must have five fields")
    minutes = sorted(_field(fields[0], 0, 59))
    hours = sorted(_field(fields[1], 0, 23))
    days = _field(fields[2], 1, 31)
    months = _field(fields[3], 1, 12, _MONTHS)
    weekdays = {value % 7 for value in _field(fields[4], 0, 7, _WEEKDAYS)}
    deadline = _deadline(after)
    for ordinal in range(after.toordinal(), deadline.toordinal() + 1):
        day = date.fromordinal(ordinal)
        if day.month not in months:
            continue
        day_matches = day.day in days
        weekday_matches = (day.weekday() + 1) % 7 in weekdays
        if fields[2] == "*":
            matches = weekday_matches
        elif fields[4] == "*":
            matches = day_matches
        else:
            matches = day_matches or weekday_matches
        if not matches:
            continue
        for hour in hours:
            for minute in minutes:
                candidate = datetime(day.year, day.month, day.day, hour, minute)
                if after < candidate <= deadline:
                    return candidate
    raise ValueError("No matching cron minute within five years")
