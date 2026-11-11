"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

SEARCH_YEARS = 5

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_NUMBER = re.compile(r"[0-9]+")
_FIELD_SEPARATOR = re.compile(r"[ \t]+")

_MONTH_NAMES = {
    name: number
    for number, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
        start=1,
    )
}
_DAY_NAMES = {
    name: number
    for number, name in enumerate(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"))
}


@dataclass(frozen=True)
class _FieldSpec:
    """Allowed range and symbolic names for one cron field."""

    label: str
    minimum: int
    maximum: int
    names: dict[str, int]


@dataclass(frozen=True)
class _Schedule:
    """Parsed cron expression. Day-of-week values use 0 for Sunday through 6 for Saturday."""

    minutes: tuple[int, ...]
    hours: tuple[int, ...]
    days_of_month: frozenset[int]
    months: frozenset[int]
    days_of_week: frozenset[int]
    is_dom_restricted: bool
    is_dow_restricted: bool


_MINUTE = _FieldSpec("minute", 0, 59, {})
_HOUR = _FieldSpec("hour", 0, 23, {})
_DAY_OF_MONTH = _FieldSpec("day of month", 1, 31, {})
_MONTH = _FieldSpec("month", 1, 12, _MONTH_NAMES)
_DAY_OF_WEEK = _FieldSpec("day of week", 0, 7, _DAY_NAMES)


def next_run(expr: str, after: datetime) -> datetime:
    """Return the earliest matching minute strictly later than ``after``.

    Seconds and microseconds of ``after`` are ignored, so the result always has
    them set to zero. Datetimes are naive; no time zone or DST handling is done.

    Args:
        expr: A 5-field cron expression, or one of the ``@`` shortcuts.
        after: The reference time. The result is strictly later than this.

    Returns:
        The first matching minute after ``after``.

    Raises:
        TypeError: If ``expr`` is not a string.
        ValueError: If ``expr`` is invalid, or nothing matches within
            ``SEARCH_YEARS`` years after ``after``.
    """
    if not isinstance(expr, str):
        raise TypeError(f"expr must be str, not {type(expr).__name__}")
    schedule = _parse(expr)
    earliest = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    horizon = _years_later(after, SEARCH_YEARS)
    day = earliest.date()
    while day <= horizon.date():
        candidate = _first_time_on_day(schedule, day, earliest)
        if candidate is not None and candidate <= horizon:
            return candidate
        day += timedelta(days=1)
    raise ValueError(f"no time matches {expr!r} within {SEARCH_YEARS} years after {after}")


def _parse(expr: str) -> _Schedule:
    """Parse a cron expression or shortcut into a schedule.

    Raises:
        ValueError: If the expression does not have exactly five valid fields.
    """
    text = expr.strip(" \t")
    text = _SHORTCUTS.get(text.lower(), text)
    fields = _FIELD_SEPARATOR.split(text)
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, found {len(fields)} in {expr!r}")
    minute_text, hour_text, dom_text, month_text, dow_text = fields
    days_of_week = _parse_field(dow_text, _DAY_OF_WEEK)
    return _Schedule(
        minutes=tuple(sorted(_parse_field(minute_text, _MINUTE))),
        hours=tuple(sorted(_parse_field(hour_text, _HOUR))),
        days_of_month=_parse_field(dom_text, _DAY_OF_MONTH),
        months=_parse_field(month_text, _MONTH),
        # Both 0 and 7 mean Sunday.
        days_of_week=frozenset(0 if day == 7 else day for day in days_of_week),
        is_dom_restricted=dom_text != "*",
        is_dow_restricted=dow_text != "*",
    )


def _parse_field(text: str, spec: _FieldSpec) -> frozenset[int]:
    """Expand a comma-separated field into the set of values it allows."""
    values: set[int] = set()
    for item in text.split(","):
        values.update(_parse_item(item, spec))
    return frozenset(values)


def _parse_item(item: str, spec: _FieldSpec) -> range:
    """Expand one item such as ``*/5``, ``1-4/2``, ``7`` or ``FRI``."""
    base, has_step, step_text = item.partition("/")
    step = _parse_step(step_text, item) if has_step else 1
    if base == "*":
        return range(spec.minimum, spec.maximum + 1, step)
    start_text, has_range, end_text = base.partition("-")
    start = _parse_value(start_text, spec)
    if has_range:
        end = _parse_value(end_text, spec)
        if end < start:
            raise ValueError(f"{spec.label} range {base!r} runs backwards in {item!r}")
    elif has_step:
        end = spec.maximum
    else:
        end = start
    return range(start, end + 1, step)


def _parse_step(step_text: str, item: str) -> int:
    """Parse the ``S`` in ``/S``, which must be a positive integer."""
    if not _NUMBER.fullmatch(step_text) or int(step_text) < 1:
        raise ValueError(f"invalid step {step_text!r} in {item!r}")
    return int(step_text)


def _parse_value(token: str, spec: _FieldSpec) -> int:
    """Convert a number or a field name such as ``MON`` to an in-range value."""
    if _NUMBER.fullmatch(token):
        value = int(token)
    elif token.upper() in spec.names:
        value = spec.names[token.upper()]
    else:
        raise ValueError(f"invalid {spec.label} value {token!r}")
    if not spec.minimum <= value <= spec.maximum:
        raise ValueError(
            f"{spec.label} value {value} is outside {spec.minimum}-{spec.maximum}"
        )
    return value


def _day_matches(schedule: _Schedule, day: date) -> bool:
    """Return whether ``day`` is allowed by the month and day fields.

    When both day fields are restricted, either one may match. Otherwise
    both must match, and an unrestricted field matches every day.
    """
    if day.month not in schedule.months:
        return False
    is_dom_match = day.day in schedule.days_of_month
    # Python counts Monday as 0; cron counts Sunday as 0.
    is_dow_match = (day.weekday() + 1) % 7 in schedule.days_of_week
    if schedule.is_dom_restricted and schedule.is_dow_restricted:
        return is_dom_match or is_dow_match
    return is_dom_match and is_dow_match


def _first_time_on_day(schedule: _Schedule, day: date, earliest: datetime) -> datetime | None:
    """Return the first matching minute on ``day`` that is not before ``earliest``."""
    if not _day_matches(schedule, day):
        return None
    for hour in schedule.hours:
        for minute in schedule.minutes:
            candidate = datetime.combine(day, time(hour, minute))
            if candidate >= earliest:
                return candidate
    return None


def _years_later(moment: datetime, years: int) -> datetime:
    """Return ``moment`` shifted forward by whole years, mapping Feb 29 to Feb 28 if needed."""
    try:
        return moment.replace(year=moment.year + years)
    except ValueError:
        return moment.replace(year=moment.year + years, day=28)
