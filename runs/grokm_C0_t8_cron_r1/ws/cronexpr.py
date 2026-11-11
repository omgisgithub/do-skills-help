"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

from datetime import datetime, timedelta
import re

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


def next_run(expr, after):
    """Earliest minute strictly after ``after`` that matches ``expr``.

    Datetimes are naive. Raises TypeError if ``expr`` is not a str, and
    ValueError if ``expr`` is invalid or nothing matches within 5 years.
    """
    if not isinstance(expr, str):
        raise TypeError("expr must be str")
    minutes, hours, doms, months, dows, dom_restricted, dow_restricted = _parse(expr)
    limit = _add_years(after, 5)
    dt = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while dt <= limit:
        if dt.month not in months:
            dt = _next_month(dt, months)
            continue
        if not _day_matches(dt, doms, dows, dom_restricted, dow_restricted):
            dt = _next_day(dt)
            continue
        if dt.hour not in hours:
            dt = _next_hour(dt, hours)
            continue
        if dt.minute not in minutes:
            dt = _next_minute(dt, minutes)
            continue
        return dt
    raise ValueError("no matching minute within 5 years")


def _parse(expr):
    text = expr.strip()
    shortcut = _SHORTCUTS.get(text.lower())
    if shortcut is not None:
        text = shortcut
    fields = re.split(r"[ \t]+", text) if text else []
    if len(fields) != 5:
        raise ValueError("invalid cron expression")
    minutes, _ = _parse_field(fields[0], 0, 59, None, False)
    hours, _ = _parse_field(fields[1], 0, 23, None, False)
    doms, dom_restricted = _parse_field(fields[2], 1, 31, None, False)
    months, _ = _parse_field(fields[3], 1, 12, _MONTHS, False)
    # 0 and 7 are both Sunday; 7 is normalized to 0 after the range is expanded.
    dows, dow_restricted = _parse_field(fields[4], 0, 7, _DOWS, True)
    return minutes, hours, doms, months, dows, dom_restricted, dow_restricted


def _parse_field(field, lo, hi, names, dow):
    # Restricted unless the field is exactly "*"; "*/2" and "*,*" are restricted.
    restricted = field != "*"
    values = set()
    for item in field.split(","):
        values.update(_parse_item(item, lo, hi, names, dow))
    if not values:
        raise ValueError("invalid cron expression")
    return values, restricted


def _parse_item(item, lo, hi, names, dow):
    if not item or item.count("/") > 1:
        raise ValueError("invalid cron expression")
    if "/" in item:
        base, step_token = item.split("/", 1)
        step = _parse_step(step_token)
        has_step = True
    else:
        base = item
        step = 1
        has_step = False
    if base == "*":
        start, end = lo, hi
    elif "-" in base:
        if base.count("-") != 1:
            raise ValueError("invalid cron expression")
        left, right = base.split("-", 1)
        start = _parse_value(left, lo, hi, names)
        end = _parse_value(right, lo, hi, names)
        if start > end:
            raise ValueError("invalid cron expression")
    else:
        start = _parse_value(base, lo, hi, names)
        # N/S runs from N through the field maximum; a bare N is just N.
        end = hi if has_step else start
    values = set()
    value = start
    while value <= end:
        values.add(0 if dow and value == 7 else value)
        value += step
    if not values:
        raise ValueError("invalid cron expression")
    return values


def _parse_step(token):
    if not token or any(c not in "0123456789" for c in token):
        raise ValueError("invalid cron expression")
    step = int(token)
    if step < 1:
        raise ValueError("invalid cron expression")
    return step


def _parse_value(token, lo, hi, names):
    if not token:
        raise ValueError("invalid cron expression")
    if names is not None:
        named = names.get(token.upper())
        if named is not None:
            return named
    if any(c not in "0123456789" for c in token):
        raise ValueError("invalid cron expression")
    value = int(token)
    if value < lo or value > hi:
        raise ValueError("invalid cron expression")
    return value


def _add_years(dt, years):
    year = dt.year + years
    try:
        return dt.replace(year=year)
    except ValueError:
        # Feb 29 rolled onto a non-leap year: clamp to Feb 28, same clock time.
        return dt.replace(year=year, day=28)


def _dow(dt):
    # datetime: Monday=1 .. Sunday=7. Cron: Sunday=0 .. Saturday=6.
    return dt.isoweekday() % 7


def _day_matches(dt, doms, dows, dom_restricted, dow_restricted):
    # If both day fields are restricted, either one matching is enough.
    dom_ok = dt.day in doms
    dow_ok = _dow(dt) in dows
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    if dom_restricted:
        return dom_ok
    if dow_restricted:
        return dow_ok
    return True


def _next_day(dt):
    nxt = dt + timedelta(days=1)
    return nxt.replace(hour=0, minute=0, second=0, microsecond=0)


def _next_month(dt, months):
    year = dt.year
    month = dt.month
    while True:
        month += 1
        if month > 12:
            month = 1
            year += 1
        if month in months:
            return datetime(year, month, 1)


def _next_hour(dt, hours):
    hour = dt.hour + 1
    while hour < 24:
        if hour in hours:
            return dt.replace(hour=hour, minute=0, second=0, microsecond=0)
        hour += 1
    return _next_day(dt)


def _next_minute(dt, minutes):
    minute = dt.minute + 1
    while minute < 60:
        if minute in minutes:
            return dt.replace(minute=minute, second=0, microsecond=0)
        minute += 1
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
