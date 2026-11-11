"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

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

_DOW_NAMES = {
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

_DIGITS = re.compile(r"[0-9]+")
_FIELD_SEPARATOR = re.compile(r"[ \t]+")
_MAX_YEARS = 5


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly later than ``after``.

    Args:
        expr: A classic 5-field cron expression or one of the ``@`` shortcuts.
        after: Naive datetime used as the exclusive lower bound.

    Returns:
        The earliest matching datetime, with seconds and microseconds set to zero.

    Raises:
        TypeError: If ``expr`` is not a string.
        ValueError: If ``expr`` is invalid or no match exists within five years.
    """
    minute, hour, dom, month, dow, dom_restricted, dow_restricted = _parse_expression(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _add_years(after, _MAX_YEARS)

    hours = sorted(hour)
    minutes = sorted(minute)

    current = start.date()
    last = limit.date()
    while current <= last:
        if _date_matches(current, month, dom, dow, dom_restricted, dow_restricted):
            candidate = _first_time_on(current, start, hours, minutes)
            if candidate is not None and candidate <= limit:
                return candidate
        current += timedelta(days=1)

    raise ValueError(
        f"no matching run for {expr!r} within {_MAX_YEARS} years after {after!r}"
    )


def _parse_expression(
    expr: str,
) -> tuple[set[int], set[int], set[int], set[int], set[int], bool, bool]:
    if not isinstance(expr, str):
        raise TypeError(f"expr must be a str, not {type(expr).__name__}")

    text = expr.strip()
    if not text:
        raise ValueError("empty cron expression")

    text = _SHORTCUTS.get(text.lower(), text)
    fields = _FIELD_SEPARATOR.split(text)
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)} in {expr!r}")

    minute = _parse_field(fields[0], 0, 59, {})
    hour = _parse_field(fields[1], 0, 23, {})
    dom = _parse_field(fields[2], 1, 31, {})
    month = _parse_field(fields[3], 1, 12, _MONTH_NAMES)
    dow = _parse_field(fields[4], 0, 7, _DOW_NAMES, sunday_as_zero=True)

    return (
        minute,
        hour,
        dom,
        month,
        dow,
        fields[2] != "*",
        fields[4] != "*",
    )


def _parse_field(
    text: str,
    minimum: int,
    maximum: int,
    names: dict[str, int],
    *,
    sunday_as_zero: bool = False,
) -> set[int]:
    values: set[int] = set()
    for item in text.split(","):
        if not item:
            raise ValueError(f"empty item in field {text!r}")

        parts = item.split("/")
        if len(parts) > 2:
            raise ValueError(f"invalid item {item!r}")

        base = parts[0]
        step = 1
        if len(parts) == 2:
            step_text = parts[1]
            if _DIGITS.fullmatch(step_text) is None:
                raise ValueError(f"invalid step in item {item!r}")
            step = int(step_text)
            if step < 1:
                raise ValueError(f"step must be at least 1 in item {item!r}")

        if base == "*":
            first, last = minimum, maximum
        elif "-" in base:
            bounds = base.split("-")
            if len(bounds) != 2:
                raise ValueError(f"invalid range {base!r}")
            first = _parse_value(bounds[0], minimum, maximum, names)
            last = _parse_value(bounds[1], minimum, maximum, names)
            if first > last:
                raise ValueError(f"range start is after range end in {base!r}")
        else:
            first = _parse_value(base, minimum, maximum, names)
            last = maximum if len(parts) == 2 else first

        for value in range(first, last + 1, step):
            values.add(0 if sunday_as_zero and value == 7 else value)

    return values


def _parse_value(token: str, minimum: int, maximum: int, names: dict[str, int]) -> int:
    name = token.upper()
    if name in names:
        value = names[name]
    else:
        if _DIGITS.fullmatch(token) is None:
            raise ValueError(f"invalid value {token!r}")
        value = int(token)

    if value < minimum or value > maximum:
        raise ValueError(f"value {token!r} is outside {minimum}-{maximum}")
    return value


def _date_matches(
    current: date,
    month: set[int],
    dom: set[int],
    dow: set[int],
    dom_restricted: bool,
    dow_restricted: bool,
) -> bool:
    if current.month not in month:
        return False

    dom_match = current.day in dom
    dow_match = (current.weekday() + 1) % 7 in dow

    if dom_restricted and dow_restricted:
        return dom_match or dow_match
    if dom_restricted:
        return dom_match
    if dow_restricted:
        return dow_match
    return True


def _first_time_on(
    current: date,
    start: datetime,
    hours: list[int],
    minutes: list[int],
) -> datetime | None:
    if current == start.date():
        earliest_hour, earliest_minute = start.hour, start.minute
    else:
        earliest_hour, earliest_minute = 0, 0

    for hour in hours:
        if hour < earliest_hour:
            continue
        for minute in minutes:
            if hour == earliest_hour and minute < earliest_minute:
                continue
            return datetime(current.year, current.month, current.day, hour, minute)
    return None


def _add_years(value: datetime, years: int) -> datetime:
    target_year = value.year + years
    try:
        return value.replace(year=target_year)
    except ValueError:
        # February 29 does not exist in the target year.
        return value.replace(year=target_year, day=28)
