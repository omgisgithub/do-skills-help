"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

import calendar
import re
from collections import namedtuple
from datetime import datetime, timedelta

_ITEM_RE = re.compile(r"(\*|[0-9A-Za-z]+)(?:-([0-9A-Za-z]+))?(?:/([0-9]+))?")
_NUMBER_RE = re.compile(r"[0-9]+")
_NAME_RE = re.compile(r"[A-Za-z]+")
_FIELD_SEP_RE = re.compile(r"[ \t]+")

_MONTHS = {
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
_DOWS = {
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

# minutes, hours, doms, months, dows are sorted tuples.
# Day fields are restricted unless the field text is exactly "*".
_Parsed = namedtuple(
    "_Parsed",
    "minutes hours doms months dows dom_restricted dow_restricted",
)


def next_run(expr, after):
    """Return the earliest matching minute strictly later than ``after``.

    Raises TypeError if ``expr`` is not a str. Raises ValueError if ``expr``
    is invalid or no match exists within five years of ``after``.
    """
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    if not isinstance(after, datetime):
        raise TypeError("after must be a datetime")

    parsed = _parse(expr)
    try:
        candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no matching minute within 5 years")
    limit = _add_years(after, 5)

    while candidate <= limit:
        if candidate.month not in parsed.months:
            nxt = _next_month_start(candidate.year, candidate.month, parsed.months)
            if nxt is None or nxt > limit:
                break
            candidate = nxt
            continue

        if not _day_matches(candidate, parsed):
            candidate = _next_midnight(candidate)
            continue

        if candidate.hour not in parsed.hours:
            hour = _next_after(parsed.hours, candidate.hour)
            if hour is None:
                candidate = _next_midnight(candidate)
            else:
                candidate = candidate.replace(
                    hour=hour, minute=0, second=0, microsecond=0
                )
            continue

        if candidate.minute not in parsed.minutes:
            minute = _next_after(parsed.minutes, candidate.minute)
            if minute is None:
                if candidate.hour == 23:
                    candidate = _next_midnight(candidate)
                else:
                    candidate = candidate.replace(
                        hour=candidate.hour + 1, minute=0, second=0, microsecond=0
                    )
            else:
                candidate = candidate.replace(minute=minute, second=0, microsecond=0)
            continue

        return candidate

    raise ValueError("no matching minute within 5 years")


def _parse(expr):
    text = expr.strip()
    shortcut = _SHORTCUTS.get(text.lower())
    if shortcut is not None:
        text = shortcut
    if text == "":
        raise ValueError("invalid cron expression")
    fields = _FIELD_SEP_RE.split(text)
    if len(fields) != 5:
        raise ValueError("invalid cron expression")

    minutes, _ = _parse_field(fields[0], 0, 59, None, False)
    hours, _ = _parse_field(fields[1], 0, 23, None, False)
    doms, dom_restricted = _parse_field(fields[2], 1, 31, None, False)
    months, _ = _parse_field(fields[3], 1, 12, _MONTHS, False)
    dows, dow_restricted = _parse_field(fields[4], 0, 7, _DOWS, True)
    return _Parsed(
        minutes, hours, doms, months, dows, dom_restricted, dow_restricted
    )


def _parse_field(text, lo, hi, names, is_dow):
    parts = text.split(",")
    if any(part == "" for part in parts):
        raise ValueError("invalid cron expression")
    values = []
    for part in parts:
        values.extend(_expand_item(part, lo, hi, names))
    if is_dow:
        # 7 is Sunday, same as 0. Expand against 7 first so ranges like 5-7 work.
        values = [0 if value == 7 else value for value in values]
    if not values:
        raise ValueError("invalid cron expression")
    return tuple(sorted(set(values))), text != "*"


def _expand_item(item, lo, hi, names):
    match = _ITEM_RE.fullmatch(item)
    if match is None:
        raise ValueError("invalid cron expression")
    base, end, step_text = match.groups()
    if base == "*" and end is not None:
        raise ValueError("invalid cron expression")
    if step_text is None:
        step = 1
    else:
        step = int(step_text)
        if step < 1:
            raise ValueError("invalid cron expression")

    if base == "*":
        start = lo
        stop = hi
    else:
        start = _value(base, lo, hi, names)
        if end is None:
            # N/S runs through the field maximum; a bare N is just N.
            stop = hi if step_text is not None else start
        else:
            stop = _value(end, lo, hi, names)
            if start > stop:
                raise ValueError("invalid cron expression")

    values = []
    current = start
    while current <= stop:
        values.append(current)
        current += step
    return values


def _value(token, lo, hi, names):
    if _NUMBER_RE.fullmatch(token):
        value = int(token)
    elif names is not None and _NAME_RE.fullmatch(token):
        value = names.get(token.upper())
        if value is None:
            raise ValueError("invalid cron expression")
    else:
        raise ValueError("invalid cron expression")
    if value < lo or value > hi:
        raise ValueError("invalid cron expression")
    return value


def _day_matches(dt, parsed):
    """Apply the day-of-month / day-of-week OR rule.

    A field restricts the day only when it is not exactly ``*``. When both
    are restricted, either one matching is enough.
    """
    dom_ok = dt.day in parsed.doms
    dow_ok = (dt.weekday() + 1) % 7 in parsed.dows
    if parsed.dom_restricted and parsed.dow_restricted:
        return dom_ok or dow_ok
    if parsed.dom_restricted:
        return dom_ok
    if parsed.dow_restricted:
        return dow_ok
    return True


def _add_years(dt, years):
    year = dt.year + years
    if year > 9999:
        return datetime(9999, 12, 31, 23, 59, 59, 999999)
    last = calendar.monthrange(year, dt.month)[1]
    day = dt.day if dt.day <= last else last
    return dt.replace(year=year, day=day)


def _next_month_start(year, month, months):
    for _ in range(12):
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
        if year > 9999:
            return None
        if month in months:
            return datetime(year, month, 1)
    return None


def _next_midnight(dt):
    return dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _next_after(values, current):
    for value in values:
        if value > current:
            return value
    return None
