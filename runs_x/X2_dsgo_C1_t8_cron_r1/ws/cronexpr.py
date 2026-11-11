"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTH_NAMES = {
    name: number
    for number, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
        1,
    )
}
_DOW_NAMES = {
    name: number
    for number, name in enumerate(
        ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"),
        0,
    )
}

# name, minimum, maximum, allowed names
_FIELDS = (
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day of month", 1, 31, {}),
    ("month", 1, 12, _MONTH_NAMES),
    ("day of week", 0, 7, _DOW_NAMES),
)

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_ITEM_RE = re.compile(r"(\*|(\d+|[A-Za-z]+)(?:-(\d+|[A-Za-z]+))?)(?:/(\d+))?")


def _field_value(token, lo, hi, names, field):
    if token.isdigit():
        value = int(token)
    else:
        value = names.get(token.upper())
        if value is None:
            raise ValueError(
                "invalid value %r in %s field" % (token, field)
            )
    if not lo <= value <= hi:
        raise ValueError("value %r out of range in %s field" % (token, field))
    return value


def _parse_field(text, lo, hi, names, field):
    """Return the set of values selected by one field."""
    values = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty item in %s field" % field)
        match = _ITEM_RE.fullmatch(item)
        if match is None:
            raise ValueError("invalid item %r in %s field" % (item, field))
        base, single, range_end, step_text = match.groups()

        step = 1 if step_text is None else int(step_text)
        if step < 1:
            raise ValueError("step must be at least 1 in %s field" % field)

        if base == "*":
            start, end = lo, hi
        else:
            start = _field_value(single, lo, hi, names, field)
            if range_end is not None:
                end = _field_value(range_end, lo, hi, names, field)
                if start > end:
                    raise ValueError(
                        "range start after end in %s field" % field
                    )
            elif step_text is not None:
                end = hi
            else:
                end = start
        values.update(range(start, end + 1, step))
    return values


def _parse(expr):
    """Parse an expression into per-field sets and restriction flags."""
    if not isinstance(expr, str):
        raise TypeError("cron expression must be a string")

    text = expr.strip()
    if not text:
        raise ValueError("empty cron expression")

    if text.startswith("@"):
        shortcut = _SHORTCUTS.get(text.lower())
        if shortcut is None:
            raise ValueError("unknown shortcut %r" % text)
        text = shortcut

    parts = re.split(r"[ \t]+", text)
    if len(parts) != 5:
        raise ValueError("expected 5 fields, got %d" % len(parts))

    parsed = []
    for part, (field, lo, hi, names) in zip(parts, _FIELDS):
        parsed.append(_parse_field(part, lo, hi, names, field))

    minute, hour, dom, month, dow = parsed
    # 7 is another spelling of Sunday.
    dow = {0 if value == 7 else value for value in dow}

    return {
        "minute": minute,
        "hour": hour,
        "dom": dom,
        "month": month,
        "dow": dow,
        "dom_restricted": parts[2] != "*",
        "dow_restricted": parts[4] != "*",
    }


def _day_matches(day, dom, dow, dom_restricted, dow_restricted):
    if dom_restricted and dow_restricted:
        return day.day in dom or (day.isoweekday() % 7) in dow
    if dom_restricted:
        return day.day in dom
    if dow_restricted:
        return (day.isoweekday() % 7) in dow
    return True


def _add_years(value, years):
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # 29 February in a non-leap target year
        return value.replace(year=value.year + years, month=2, day=28)


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly later than *after*."""
    spec = _parse(expr)

    no_match = "no matching minute within 5 years of %s" % after
    try:
        start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError(no_match)
    try:
        limit = _add_years(after, 5)
    except (ValueError, OverflowError):  # too close to datetime.max
        limit = datetime.max

    hours = sorted(spec["hour"])
    minutes = sorted(spec["minute"])
    dom = spec["dom"]
    dow = spec["dow"]
    month = spec["month"]
    dom_restricted = spec["dom_restricted"]
    dow_restricted = spec["dow_restricted"]

    day = start.date()
    last_day = limit.date()
    while day <= last_day:
        if day.month in month and _day_matches(
            day, dom, dow, dom_restricted, dow_restricted
        ):
            for hour in hours:
                for minute in minutes:
                    candidate = datetime(
                        day.year, day.month, day.day, hour, minute
                    )
                    if candidate < start:
                        continue
                    if candidate > limit:
                        raise ValueError(no_match)
                    return candidate
        try:
            day += timedelta(days=1)
        except OverflowError:
            break

    raise ValueError(no_match)
