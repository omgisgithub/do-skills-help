"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from calendar import monthrange
from datetime import datetime, timedelta

MONTH_NAMES = {
    name: number
    for number, name in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)
}
DOW_NAMES = {
    name: number
    for number, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])
}

# (low, high, names) for minute, hour, day of month, month, day of week
FIELDS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, MONTH_NAMES),
    (0, 7, DOW_NAMES),
]

SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

# An item is `*`, `N`, or `A-B`, optionally followed by `/S`.
ITEM_RE = re.compile(r"(\*|[0-9A-Za-z]+)(?:-([0-9A-Za-z]+))?(?:/([0-9]+))?")


def _value(token, low, high, names):
    if re.fullmatch(r"[0-9]+", token):
        value = int(token)
    elif token.upper() in names:
        value = names[token.upper()]
    else:
        raise ValueError(f"invalid value {token!r}")
    if not low <= value <= high:
        raise ValueError(f"value {token!r} out of range")
    return value


def _parse_field(text, low, high, names):
    values = set()
    for item in text.split(","):
        match = ITEM_RE.fullmatch(item)
        if match is None:
            raise ValueError(f"invalid item {item!r}")
        base, end_token, step_token = match.groups()
        step = 1
        if step_token is not None:
            step = int(step_token)
            if step < 1:
                raise ValueError(f"step must be at least 1 in {item!r}")
        if base == "*":
            if end_token is not None:
                raise ValueError(f"invalid item {item!r}")
            start, end = low, high
        else:
            start = _value(base, low, high, names)
            if end_token is not None:
                end = _value(end_token, low, high, names)
                if start > end:
                    raise ValueError(f"range runs backwards in {item!r}")
            else:
                # `N/S` runs from N up to the field maximum; plain `N` is one value.
                end = high if step_token is not None else start
        values.update(range(start, end + 1, step))
    return values


def _parse(expr):
    shortcut = SHORTCUTS.get(expr.strip().lower())
    if shortcut is not None:
        expr = shortcut
    parts = re.split(r"[ \t]+", expr.strip(" \t"))
    if len(parts) != 5:
        raise ValueError(f"expected 5 fields in {expr!r}")
    minutes, hours, days_of_month, months, days_of_week = (
        _parse_field(part, low, high, names)
        for part, (low, high, names) in zip(parts, FIELDS)
    )
    # 7 is an alias for Sunday.
    days_of_week = {day % 7 for day in days_of_week}
    return (minutes, hours, days_of_month, months, days_of_week,
            parts[2] != "*", parts[4] != "*")


def _day_matches(day, days_of_month, days_of_week, dom_restricted, dow_restricted):
    dom_ok = day.day in days_of_month
    dow_ok = day.isoweekday() % 7 in days_of_week
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    # An unrestricted field covers every day, so `and` reduces to the restricted one.
    return dom_ok and dow_ok


def _horizon(after):
    """The latest moment a match may fall on: five years after `after`."""
    year = after.year + 5
    if year > datetime.max.year:
        return datetime.max
    day = min(after.day, monthrange(year, after.month)[1])
    return after.replace(year=year, day=day)


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    (minutes, hours, days_of_month, months, days_of_week,
     dom_restricted, dow_restricted) = _parse(expr)

    try:
        start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError(f"no matching time after {after}") from None
    limit = _horizon(after)

    first_day = start.date()
    for offset in range((limit.date() - first_day).days + 1):
        day = first_day + timedelta(days=offset)
        if day.month not in months:
            continue
        if not _day_matches(day, days_of_month, days_of_week, dom_restricted, dow_restricted):
            continue
        for hour in sorted(hours):
            for minute in sorted(minutes):
                candidate = datetime(day.year, day.month, day.day, hour, minute)
                if start <= candidate <= limit:
                    return candidate
    raise ValueError(f"no matching time within 5 years after {after}")
