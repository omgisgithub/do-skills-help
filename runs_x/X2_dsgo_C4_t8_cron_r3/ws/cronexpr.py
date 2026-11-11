"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import FrozenSet, Mapping, Set

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

_WEEKDAY_NAMES = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
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


@dataclass(frozen=True)
class _FieldSpec:
    minimum: int
    maximum: int
    names: Mapping[str, int]


@dataclass(frozen=True)
class _Schedule:
    minutes: FrozenSet[int]
    hours: FrozenSet[int]
    days_of_month: FrozenSet[int]
    months: FrozenSet[int]
    weekdays: FrozenSet[int]
    day_of_month_restricted: bool
    day_of_week_restricted: bool


_FIELD_SPECS = (
    _FieldSpec(0, 59, {}),
    _FieldSpec(0, 23, {}),
    _FieldSpec(1, 31, {}),
    _FieldSpec(1, 12, _MONTH_NAMES),
    _FieldSpec(0, 7, _WEEKDAY_NAMES),
)


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after ``after``.

    Args:
        expr: A five-field cron expression or a supported ``@`` shortcut.
        after: Naive datetime from which the search starts.

    Returns:
        The earliest matching minute, with seconds and microseconds set to zero.

    Raises:
        TypeError: If ``expr`` is not a string.
        ValueError: If ``expr`` is invalid or no match exists within five years.
    """
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")

    schedule = _parse_expression(expr)

    try:
        first = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except (OverflowError, ValueError):
        raise ValueError("no matching minute within five years") from None

    limit = _add_years(after, 5)
    hours = sorted(schedule.hours)
    minutes = sorted(schedule.minutes)
    first_date = first.date()
    end_date = limit.date()

    current = first_date
    while current <= end_date:
        if _day_matches(current, schedule):
            start_hour = first.hour if current == first_date else 0
            start_minute = first.minute if current == first_date else 0

            for hour in hours:
                if hour < start_hour:
                    continue
                earliest_minute = start_minute if hour == start_hour else 0
                for minute in minutes:
                    if minute < earliest_minute:
                        continue

                    candidate = after.replace(
                        year=current.year,
                        month=current.month,
                        day=current.day,
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0,
                    )
                    if candidate > limit:
                        raise ValueError("no matching minute within five years")
                    return candidate

        if current == end_date:
            break
        current += timedelta(days=1)

    raise ValueError("no matching minute within five years")


def _parse_expression(expr: str) -> _Schedule:
    text = expr.strip()
    text = _SHORTCUTS.get(text.lower(), text)
    parts = re.split(r"[ \t]+", text)
    if len(parts) != 5:
        raise ValueError("cron expression must have exactly five fields")

    minute_text, hour_text, day_of_month_text, month_text, day_of_week_text = parts
    minute_values = _parse_field(minute_text, _FIELD_SPECS[0])
    hour_values = _parse_field(hour_text, _FIELD_SPECS[1])
    day_of_month_values = _parse_field(day_of_month_text, _FIELD_SPECS[2])
    month_values = _parse_field(month_text, _FIELD_SPECS[3])
    day_of_week_values = _parse_field(day_of_week_text, _FIELD_SPECS[4])

    # Python's weekday() is Monday=0, Sunday=6. Normalize cron's Sunday 0/7 to 6.
    weekday_values = frozenset((value - 1) % 7 for value in day_of_week_values)

    return _Schedule(
        minutes=minute_values,
        hours=hour_values,
        days_of_month=day_of_month_values,
        months=month_values,
        weekdays=weekday_values,
        day_of_month_restricted=day_of_month_text != "*",
        day_of_week_restricted=day_of_week_text != "*",
    )


def _parse_field(text: str, spec: _FieldSpec) -> FrozenSet[int]:
    values: Set[int] = set()
    for item in text.split(","):
        values.update(_parse_item(item, spec))
    return frozenset(values)


def _parse_item(item: str, spec: _FieldSpec) -> range:
    if not item or item.count("/") > 1:
        raise ValueError(f"invalid cron field item: {item!r}")

    base, slash, step_text = item.partition("/")
    if not base:
        raise ValueError(f"invalid cron field item: {item!r}")

    if slash:
        if not _is_ascii_digits(step_text):
            raise ValueError(f"invalid cron step: {step_text!r}")
        step = int(step_text)
        if step < 1:
            raise ValueError("cron step must be at least 1")
    else:
        step = 1

    if base == "*":
        start = spec.minimum
        end = spec.maximum
    elif "-" in base:
        if base.count("-") != 1:
            raise ValueError(f"invalid cron range: {base!r}")
        start_text, end_text = base.split("-")
        start = _parse_value(start_text, spec)
        end = _parse_value(end_text, spec)
        if start > end:
            raise ValueError(f"cron range start exceeds end: {base!r}")
    else:
        start = _parse_value(base, spec)
        end = spec.maximum if slash else start

    return range(start, end + 1, step)


def _parse_value(token: str, spec: _FieldSpec) -> int:
    named_value = spec.names.get(token.upper())
    if named_value is not None:
        value = named_value
    elif _is_ascii_digits(token):
        value = int(token)
    else:
        raise ValueError(f"invalid cron value: {token!r}")

    if not spec.minimum <= value <= spec.maximum:
        raise ValueError(f"cron value out of range: {token!r}")
    return value


def _is_ascii_digits(text: str) -> bool:
    return bool(text) and all("0" <= character <= "9" for character in text)


def _day_matches(day: date, schedule: _Schedule) -> bool:
    if day.month not in schedule.months:
        return False

    day_of_month_matches = day.day in schedule.days_of_month
    day_of_week_matches = day.weekday() in schedule.weekdays

    if schedule.day_of_month_restricted and schedule.day_of_week_restricted:
        return day_of_month_matches or day_of_week_matches
    if schedule.day_of_month_restricted:
        return day_of_month_matches
    if schedule.day_of_week_restricted:
        return day_of_week_matches
    return True


def _add_years(value: datetime, years: int) -> datetime:
    target_year = value.year + years
    if target_year > datetime.max.year:
        return value.replace(
            year=datetime.max.year,
            month=datetime.max.month,
            day=datetime.max.day,
            hour=datetime.max.hour,
            minute=datetime.max.minute,
            second=datetime.max.second,
            microsecond=datetime.max.microsecond,
        )

    if value.month == 2 and value.day == 29 and not calendar.isleap(target_year):
        return value.replace(year=target_year, day=28)
    return value.replace(year=target_year)
