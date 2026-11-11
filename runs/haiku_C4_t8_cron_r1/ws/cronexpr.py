"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import NamedTuple

_SEARCH_YEARS = 5

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_MONTH_NAMES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_DAY_OF_WEEK_NAMES = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}

_NUMBER = re.compile(r"[0-9]+")


class _FieldSpec(NamedTuple):
    """Bounds and symbolic names allowed in one cron field."""

    name: str
    minimum: int
    maximum: int
    names: Mapping[str, int]


_MINUTE = _FieldSpec("minute", 0, 59, {})
_HOUR = _FieldSpec("hour", 0, 23, {})
_DAY_OF_MONTH = _FieldSpec("day of month", 1, 31, {})
_MONTH = _FieldSpec("month", 1, 12, _MONTH_NAMES)
_DAY_OF_WEEK = _FieldSpec("day of week", 0, 7, _DAY_OF_WEEK_NAMES)


@dataclass(frozen=True)
class _Field:
    """The values one cron field matches, and whether the field was restricted.

    An unrestricted field is written exactly as ``*``; this matters for day matching.
    """

    values: frozenset[int]
    is_restricted: bool


@dataclass(frozen=True)
class _Schedule:
    """A parsed cron expression. Day-of-week values are normalized to 0-6."""

    minutes: frozenset[int]
    hours: frozenset[int]
    days_of_month: _Field
    months: frozenset[int]
    days_of_week: _Field


def next_run(expr: str, after: datetime) -> datetime:
    """Return the earliest whole minute strictly after ``after`` matching ``expr``.

    Args:
        expr: A 5-field cron expression or one of the ``@`` shortcuts.
        after: The moment to search after. Seconds and microseconds are ignored
            for the search, so the result is always strictly later than the
            next whole minute boundary at or after ``after``.

    Returns:
        The matching naive datetime, with seconds and microseconds set to 0.

    Raises:
        TypeError: If ``expr`` is not a ``str``.
        ValueError: If ``expr`` is invalid, or no match exists within five years.
    """
    if not isinstance(expr, str):
        raise TypeError(f"expr must be a str, not {type(expr).__name__}")
    schedule = _parse_schedule(expr)
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    deadline = _add_years(start, _SEARCH_YEARS)
    for day in _days_from(start.date()):
        if day > deadline.date():
            break
        if not _day_matches(day, schedule):
            continue
        for candidate in _times_on(day, schedule):
            if candidate < start:
                continue
            if candidate > deadline:
                break
            return candidate
    raise ValueError(f"no matching time for {expr!r} within {_SEARCH_YEARS} years of {after}")


def _parse_schedule(expr: str) -> _Schedule:
    """Parse a cron expression or shortcut into a schedule.

    Args:
        expr: The raw expression text.

    Returns:
        The parsed schedule.

    Raises:
        ValueError: If the expression is malformed or has out-of-range values.
    """
    text = expr.strip(" \t")
    text = _SHORTCUTS.get(text.lower(), text)
    parts = re.split(r"[ \t]+", text)
    if len(parts) != 5:
        raise ValueError(f"expected 5 cron fields, got {len(parts)} in {expr!r}")
    minute, hour, day_of_month, month, day_of_week = (
        _parse_field(part, spec)
        for part, spec in zip(parts, (_MINUTE, _HOUR, _DAY_OF_MONTH, _MONTH, _DAY_OF_WEEK))
    )
    # Sunday is both 0 and 7 in day-of-week; fold 7 onto 0 so matching uses isoweekday() % 7.
    normalized_week = _Field(
        frozenset(value % 7 for value in day_of_week.values), day_of_week.is_restricted
    )
    return _Schedule(
        minutes=minute.values,
        hours=hour.values,
        days_of_month=day_of_month,
        months=month.values,
        days_of_week=normalized_week,
    )


def _parse_field(text: str, spec: _FieldSpec) -> _Field:
    """Parse one comma-separated cron field.

    Args:
        text: The raw field text, without surrounding whitespace.
        spec: The bounds and names allowed in this field.

    Returns:
        The matching values and whether the field was restricted.

    Raises:
        ValueError: If any item in the field is invalid.
    """
    values: set[int] = set()
    for item in text.split(","):
        values |= _parse_item(item, spec)
    return _Field(frozenset(values), is_restricted=text != "*")


def _parse_item(item: str, spec: _FieldSpec) -> set[int]:
    """Parse one item such as ``*``, ``N``, ``A-B``, or any of those followed by ``/S``.

    Args:
        item: The raw item text.
        spec: The bounds and names allowed in this field.

    Returns:
        The set of values the item selects.

    Raises:
        ValueError: If the item is malformed or out of range.
    """
    base, has_step, step_text = item.partition("/")
    step = _parse_step(step_text, spec) if has_step else 1
    if base == "*":
        low, high = spec.minimum, spec.maximum
    elif "-" in base:
        low, high = _parse_range(base, spec)
    else:
        low = _parse_value(base, spec)
        high = spec.maximum if has_step else low
    return set(range(low, high + 1, step))


def _parse_range(text: str, spec: _FieldSpec) -> tuple[int, int]:
    """Parse an inclusive ``A-B`` range.

    Args:
        text: The raw range text, containing exactly one ``-``.
        spec: The bounds and names allowed in this field.

    Returns:
        The inclusive low and high ends of the range.

    Raises:
        ValueError: If the range has extra dashes or ``A`` is greater than ``B``.
    """
    parts = text.split("-")
    if len(parts) != 2:
        raise ValueError(f"invalid range {text!r} in {spec.name} field")
    low = _parse_value(parts[0], spec)
    high = _parse_value(parts[1], spec)
    if low > high:
        raise ValueError(f"range {text!r} runs backwards in {spec.name} field")
    return low, high


def _parse_value(text: str, spec: _FieldSpec) -> int:
    """Parse a single numeric or symbolic value, checking it against the field bounds.

    Args:
        text: The raw value text.
        spec: The bounds and names allowed in this field.

    Returns:
        The integer value.

    Raises:
        ValueError: If the value is not a number or name, or is out of range.
    """
    if _NUMBER.fullmatch(text):
        value = int(text)
    elif text.upper() in spec.names:
        value = spec.names[text.upper()]
    else:
        raise ValueError(f"invalid {spec.name} value {text!r}")
    if not spec.minimum <= value <= spec.maximum:
        raise ValueError(
            f"{spec.name} value {value} is outside {spec.minimum}-{spec.maximum}"
        )
    return value


def _parse_step(text: str, spec: _FieldSpec) -> int:
    """Parse the ``S`` in an ``/S`` suffix.

    Args:
        text: The raw step text.
        spec: The field being parsed, used for error messages.

    Returns:
        The step, which is at least 1.

    Raises:
        ValueError: If the step is not a positive integer.
    """
    if not _NUMBER.fullmatch(text) or int(text) < 1:
        raise ValueError(f"invalid step {text!r} in {spec.name} field")
    return int(text)


def _day_matches(day: date, schedule: _Schedule) -> bool:
    """Return whether a calendar day satisfies the month and day constraints.

    If both day fields are restricted, a match on either one is enough.

    Args:
        day: The calendar day to test.
        schedule: The parsed schedule.

    Returns:
        True if the day is a match.
    """
    if day.month not in schedule.months:
        return False
    is_day_of_month_match = day.day in schedule.days_of_month.values
    is_day_of_week_match = day.isoweekday() % 7 in schedule.days_of_week.values
    if schedule.days_of_month.is_restricted and schedule.days_of_week.is_restricted:
        return is_day_of_month_match or is_day_of_week_match
    return is_day_of_month_match and is_day_of_week_match


def _times_on(day: date, schedule: _Schedule) -> Iterator[datetime]:
    """Yield every matching minute on a day, in chronological order.

    Args:
        day: The calendar day to enumerate.
        schedule: The parsed schedule.

    Yields:
        Naive datetimes with seconds and microseconds set to 0.
    """
    for hour in sorted(schedule.hours):
        for minute in sorted(schedule.minutes):
            yield datetime.combine(day, time(hour, minute))


def _days_from(first: date) -> Iterator[date]:
    """Yield consecutive calendar days, without end.

    Args:
        first: The first day to yield.

    Yields:
        ``first``, then each following day.
    """
    day = first
    while True:
        yield day
        day += timedelta(days=1)


def _add_years(moment: datetime, years: int) -> datetime:
    """Add whole calendar years, clamping February 29 to February 28.

    Args:
        moment: The starting datetime.
        years: The number of years to add.

    Returns:
        The shifted datetime.
    """
    try:
        return moment.replace(year=moment.year + years)
    except ValueError:
        return moment.replace(year=moment.year + years, day=28)
