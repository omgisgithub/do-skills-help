"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_NUMBER_RE = re.compile(r"[0-9]+")
_WHITESPACE_RE = re.compile(r"[ \t]+")

_MONTH_NAMES = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Cron day-of-week numbering: Sunday is 0 (and 7), Monday is 1, ... Saturday is 6.
_DAY_NAMES = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
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

_SEARCH_YEARS = 5


@dataclass(frozen=True)
class _Schedule:
    """A parsed cron expression."""

    minutes: frozenset[int]
    hours: frozenset[int]
    days_of_month: frozenset[int]
    months: frozenset[int]
    days_of_week: frozenset[int]
    dom_restricted: bool
    dow_restricted: bool


def _parse_field_value(
    token: str,
    minimum: int,
    maximum: int,
    names: dict[str, int] | None,
    field_name: str,
) -> int:
    """Parse a single number or name from one field."""
    if names is not None:
        named = names.get(token.lower())
        if named is not None:
            return named
    if _NUMBER_RE.fullmatch(token) is None:
        raise ValueError(f"invalid {field_name} value: {token!r}")
    value = int(token)
    if not minimum <= value <= maximum:
        raise ValueError(
            f"{field_name} value out of range {minimum}-{maximum}: {token!r}"
        )
    return value


def _parse_field(
    field: str,
    minimum: int,
    maximum: int,
    names: dict[str, int] | None,
    field_name: str,
) -> set[int]:
    """Expand one comma-separated field into the set of values it matches."""
    values: set[int] = set()
    for item in field.split(","):
        if item == "":
            raise ValueError(f"empty item in {field_name} field: {field!r}")

        has_step = "/" in item
        if has_step:
            base, _, step_text = item.partition("/")
            if _NUMBER_RE.fullmatch(step_text) is None:
                raise ValueError(f"invalid step in {field_name} field: {item!r}")
            step = int(step_text)
            if step < 1:
                raise ValueError(f"step must be at least 1 in {field_name} field: {item!r}")
        else:
            base = item
            step = 1

        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            left, _, right = base.partition("-")
            if "-" in right:
                raise ValueError(f"invalid range in {field_name} field: {item!r}")
            start = _parse_field_value(left, minimum, maximum, names, field_name)
            end = _parse_field_value(right, minimum, maximum, names, field_name)
            if start > end:
                raise ValueError(
                    f"range start exceeds range end in {field_name} field: {item!r}"
                )
        else:
            start = _parse_field_value(base, minimum, maximum, names, field_name)
            end = maximum if has_step else start

        values.update(range(start, end + 1, step))
    return values


def _parse_expression(expr: str) -> _Schedule:
    """Parse a cron expression (or shortcut) into a :class:`_Schedule`."""
    text = expr.strip()
    shortcut = _SHORTCUTS.get(text.lower())
    if shortcut is not None:
        text = shortcut

    fields = _WHITESPACE_RE.split(text)
    if len(fields) != 5:
        raise ValueError(
            f"expected 5 fields in cron expression, got {len(fields)}: {expr!r}"
        )
    minute_field, hour_field, dom_field, month_field, dow_field = fields

    days_of_week = {
        0 if value == 7 else value
        for value in _parse_field(dow_field, 0, 7, _DAY_NAMES, "day-of-week")
    }

    return _Schedule(
        minutes=frozenset(_parse_field(minute_field, 0, 59, None, "minute")),
        hours=frozenset(_parse_field(hour_field, 0, 23, None, "hour")),
        days_of_month=frozenset(
            _parse_field(dom_field, 1, 31, None, "day-of-month")
        ),
        months=frozenset(_parse_field(month_field, 1, 12, _MONTH_NAMES, "month")),
        days_of_week=frozenset(days_of_week),
        dom_restricted=dom_field != "*",
        dow_restricted=dow_field != "*",
    )


def _day_matches(schedule: _Schedule, day: date) -> bool:
    """Return whether a calendar day satisfies the day-of-month/day-of-week fields."""
    cron_dow = (day.weekday() + 1) % 7
    if schedule.dom_restricted and schedule.dow_restricted:
        return (
            day.day in schedule.days_of_month
            or cron_dow in schedule.days_of_week
        )
    if schedule.dom_restricted:
        return day.day in schedule.days_of_month
    if schedule.dow_restricted:
        return cron_dow in schedule.days_of_week
    return True


def _search_limit(after: datetime) -> datetime:
    """Return the inclusive upper bound of the search window."""
    target_year = after.year + _SEARCH_YEARS
    if target_year > datetime.max.year:
        return datetime.max
    try:
        return after.replace(year=target_year)
    except ValueError:
        # The only replacement that can fail here is 29 February in a non-leap year.
        return after.replace(year=target_year, day=28)


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first minute strictly after ``after`` that matches ``expr``.

    Args:
        expr: A classic 5-field cron expression or one of the ``@`` shortcuts.
        after: The lower bound (exclusive). Seconds and microseconds are dropped
            before searching, so the earliest possible result is the next whole
            minute.

    Returns:
        The earliest matching minute with ``second`` and ``microsecond`` set to 0.

    Raises:
        TypeError: If ``expr`` is not a string or ``after`` is not a datetime.
        ValueError: If ``expr`` is invalid or no match exists within five years
            after ``after``.
    """
    if not isinstance(expr, str):
        raise TypeError(f"expr must be a string, got {type(expr).__name__}")
    if not isinstance(after, datetime):
        raise TypeError(f"after must be a datetime, got {type(after).__name__}")

    schedule = _parse_expression(expr)

    try:
        start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError as exc:
        raise ValueError("no matching time within 5 years") from exc

    limit = _search_limit(after)
    minutes = sorted(schedule.minutes)
    hours = sorted(schedule.hours)
    start_date = start.date()
    current = start_date
    last_date = limit.date()

    while current <= last_date:
        if current.month in schedule.months and _day_matches(schedule, current):
            first_hour = start.hour if current == start_date else 0
            first_minute = start.minute if current == start_date else 0
            for hour in hours:
                if hour < first_hour:
                    continue
                low_minute = first_minute if hour == first_hour else 0
                index = bisect_left(minutes, low_minute)
                if index == len(minutes):
                    continue
                candidate = datetime(
                    current.year,
                    current.month,
                    current.day,
                    hour,
                    minutes[index],
                    tzinfo=after.tzinfo,
                )
                if candidate > limit:
                    raise ValueError("no matching time within 5 years")
                return candidate
        if current == last_date:
            break
        current += timedelta(days=1)

    raise ValueError("no matching time within 5 years")
