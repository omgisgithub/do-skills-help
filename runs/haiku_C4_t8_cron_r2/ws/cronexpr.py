"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

import re
from collections.abc import Iterator, Mapping
from datetime import date, datetime, time, timedelta
from itertools import product
from typing import NamedTuple

_DIGITS = re.compile(r"[0-9]+")
_FIELD_SEPARATOR = re.compile(r"[ \t]+")
_SHORTCUTS: Mapping[str, str] = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_MONTH_NAMES = {
    name: number
    for number, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
        start=1,
    )
}
_DAY_NAMES = {
    name: number for number, name in enumerate(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"))
}


class _FieldSpec(NamedTuple):
    """The allowed range and optional names for one cron field."""

    name: str
    low: int
    high: int
    names: Mapping[str, int]


_MINUTE_FIELD = _FieldSpec("minute", 0, 59, {})
_HOUR_FIELD = _FieldSpec("hour", 0, 23, {})
_DAY_OF_MONTH_FIELD = _FieldSpec("day of month", 1, 31, {})
_MONTH_FIELD = _FieldSpec("month", 1, 12, _MONTH_NAMES)
_DAY_OF_WEEK_FIELD = _FieldSpec("day of week", 0, 7, _DAY_NAMES)


class _Schedule(NamedTuple):
    """The parsed value sets of an expression, ready for matching."""

    minutes: tuple[int, ...]
    hours: tuple[int, ...]
    days_of_month: frozenset[int]
    months: frozenset[int]
    days_of_week: frozenset[int]
    is_day_of_month_restricted: bool
    is_day_of_week_restricted: bool


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first minute strictly after ``after`` that matches a cron expression.

    Seconds and microseconds of ``after`` are ignored: the search starts at the
    following whole minute. Datetimes are naive and no time zones are applied.

    Args:
        expr: A 5-field cron expression or one of the ``@`` shortcuts.
        after: The moment to search from.

    Returns:
        The earliest matching minute, with seconds and microseconds set to zero.

    Raises:
        TypeError: If ``expr`` is not a string.
        ValueError: If ``expr`` is invalid, or no match exists within 5 years of ``after``.
    """
    if not isinstance(expr, str):
        raise TypeError(f"expr must be str, not {type(expr).__name__}")
    schedule = _parse_expression(expr)
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    horizon = _five_years_after(after)
    candidate = next(_run_times(schedule, start, horizon), None)
    if candidate is None:
        raise ValueError(f"no run of {expr!r} within 5 years after {after.isoformat()}")
    return candidate


def _parse_expression(expr: str) -> _Schedule:
    """Parse an expression or shortcut into its value sets.

    Args:
        expr: A 5-field cron expression or one of the ``@`` shortcuts.

    Returns:
        The parsed schedule.

    Raises:
        ValueError: If the expression is malformed.
    """
    text = _SHORTCUTS.get(expr.strip().lower(), expr)
    fields = _FIELD_SEPARATOR.split(text.strip())
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)} in {expr!r}")
    minute_text, hour_text, day_text, month_text, weekday_text = fields
    weekdays = _parse_field(weekday_text, _DAY_OF_WEEK_FIELD)
    return _Schedule(
        minutes=tuple(sorted(_parse_field(minute_text, _MINUTE_FIELD))),
        hours=tuple(sorted(_parse_field(hour_text, _HOUR_FIELD))),
        days_of_month=_parse_field(day_text, _DAY_OF_MONTH_FIELD),
        months=_parse_field(month_text, _MONTH_FIELD),
        # 0 and 7 both mean Sunday, so fold 7 onto 0.
        days_of_week=frozenset(value % 7 for value in weekdays),
        is_day_of_month_restricted=day_text != "*",
        is_day_of_week_restricted=weekday_text != "*",
    )


def _parse_field(text: str, field: _FieldSpec) -> frozenset[int]:
    """Parse a comma-separated cron field into the set of values it allows.

    Args:
        text: The raw field text.
        field: The field's allowed range and names.

    Returns:
        The allowed values.

    Raises:
        ValueError: If any item is malformed or out of range.
    """
    values: set[int] = set()
    for item in text.split(","):
        values.update(_parse_item(item, field))
    return frozenset(values)


def _parse_item(item: str, field: _FieldSpec) -> range:
    """Parse one ``*``, ``N``, or ``A-B`` item with an optional ``/S`` step.

    Args:
        item: The raw item text.
        field: The field's allowed range and names.

    Returns:
        The values the item selects, in ascending order.

    Raises:
        ValueError: If the item is malformed or out of range.
    """
    body, has_step, step_text = item.partition("/")
    step = _parse_step(step_text) if has_step else 1
    start, end = _parse_bounds(body, field, has_step)
    return range(start, end + 1, step)


def _parse_bounds(body: str, field: _FieldSpec, has_step: bool) -> tuple[int, int]:
    """Resolve the inclusive bounds of an item body.

    Args:
        body: The item text before any ``/``.
        field: The field's allowed range and names.
        has_step: Whether the item had a ``/S`` step, which makes ``N`` run to the maximum.

    Returns:
        The inclusive ``(start, end)`` bounds.

    Raises:
        ValueError: If the body is malformed or a range runs backwards.
    """
    if body == "*":
        return field.low, field.high
    if "-" in body:
        first, _, last = body.partition("-")
        start = _parse_value(first, field)
        end = _parse_value(last, field)
        if start > end:
            raise ValueError(f"{field.name} range {body!r} runs backwards")
        return start, end
    start = _parse_value(body, field)
    return start, field.high if has_step else start


def _parse_step(text: str) -> int:
    """Parse the step after a ``/``.

    Args:
        text: The raw step text.

    Returns:
        A step of at least 1.

    Raises:
        ValueError: If the step is not a positive integer.
    """
    if not _DIGITS.fullmatch(text) or int(text) < 1:
        raise ValueError(f"invalid step {text!r}")
    return int(text)


def _parse_value(text: str, field: _FieldSpec) -> int:
    """Parse a single number or name within a field.

    Args:
        text: The raw value text.
        field: The field's allowed range and names.

    Returns:
        The numeric value.

    Raises:
        ValueError: If the value is not a number or name, or is out of range.
    """
    if _DIGITS.fullmatch(text):
        value = int(text)
    elif text.upper() in field.names:
        value = field.names[text.upper()]
    else:
        raise ValueError(f"invalid {field.name} value {text!r}")
    if not field.low <= value <= field.high:
        raise ValueError(f"{field.name} value {value} is outside {field.low}-{field.high}")
    return value


def _five_years_after(moment: datetime) -> datetime:
    """Return the datetime five calendar years after ``moment``.

    Args:
        moment: The starting datetime.

    Returns:
        The same wall-clock time five years later, or March 1 if that date has no Feb 29.
    """
    try:
        return moment.replace(year=moment.year + 5)
    except ValueError:
        # Only Feb 29 fails to exist; the target year is not a leap year.
        return moment.replace(year=moment.year + 5, month=3, day=1)


def _run_times(schedule: _Schedule, start: datetime, horizon: datetime) -> Iterator[datetime]:
    """Yield every matching minute in ``[start, horizon]``, earliest first.

    Args:
        schedule: The parsed schedule to match.
        start: The first minute to consider, inclusive.
        horizon: The last minute to consider, inclusive.

    Yields:
        Matching datetimes in ascending order.
    """
    day = start.date()
    while day <= horizon.date():
        if _day_matches(schedule, day):
            for hour, minute in product(schedule.hours, schedule.minutes):
                candidate = datetime.combine(day, time(hour, minute))
                if start <= candidate <= horizon:
                    yield candidate
        day += timedelta(days=1)


def _day_matches(schedule: _Schedule, day: date) -> bool:
    """Return whether ``day`` is selected by the month and day fields.

    Args:
        schedule: The parsed schedule to match.
        day: The calendar day to check.

    Returns:
        True if the day matches under the cron day-matching rules.
    """
    if day.month not in schedule.months:
        return False
    matches_day_of_month = day.day in schedule.days_of_month
    # isoweekday() is 1-7 with Sunday as 7; the schedule uses 0-6 with Sunday as 0.
    matches_day_of_week = day.isoweekday() % 7 in schedule.days_of_week
    if schedule.is_day_of_month_restricted and schedule.is_day_of_week_restricted:
        return matches_day_of_month or matches_day_of_week
    # An unrestricted field selects every value, so ANDing it has no effect.
    return matches_day_of_month and matches_day_of_week
