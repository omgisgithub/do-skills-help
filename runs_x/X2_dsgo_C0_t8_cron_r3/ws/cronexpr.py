"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

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

# (minimum, maximum, allowed names) for each of the five fields.
_FIELD_SPECS = (
    (0, 59, None),          # minute
    (0, 23, None),          # hour
    (1, 31, None),          # day of month
    (1, 12, _MONTH_NAMES),  # month
    (0, 7, _DOW_NAMES),     # day of week (0 and 7 are both Sunday)
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

_NUMBER = re.compile(r"[0-9]+\Z")


def _parse_value(token, low, high, names):
    """Turn a single numeric or named value into an int within [low, high]."""
    if names is not None:
        named = names.get(token.upper())
        if named is not None:
            return named
    if not _NUMBER.match(token):
        raise ValueError("invalid value: %r" % (token,))
    value = int(token)
    if value < low or value > high:
        raise ValueError("value out of range: %r" % (token,))
    return value


def _parse_field(text, low, high, names):
    """Expand one field into the set of values it selects."""
    values = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty list item")

        parts = item.split("/")
        if len(parts) > 2:
            raise ValueError("invalid item: %r" % (item,))

        base = parts[0]
        step = 1
        if len(parts) == 2:
            raw_step = parts[1]
            if not _NUMBER.match(raw_step):
                raise ValueError("invalid step: %r" % (raw_step,))
            step = int(raw_step)
            if step < 1:
                raise ValueError("invalid step: %r" % (raw_step,))

        if base == "*":
            start, end = low, high
        elif "-" in base:
            bounds = base.split("-")
            if len(bounds) != 2:
                raise ValueError("invalid range: %r" % (base,))
            start = _parse_value(bounds[0], low, high, names)
            end = _parse_value(bounds[1], low, high, names)
            if start > end:
                raise ValueError("range start after end: %r" % (base,))
        else:
            start = _parse_value(base, low, high, names)
            end = high if len(parts) == 2 else start

        values.update(range(start, end + 1, step))

    return values


def _parse(expr):
    """Validate *expr* and return the parsed field sets and restriction flags."""
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")

    text = expr.strip()
    shortcut = _SHORTCUTS.get(text.lower())
    if shortcut is not None:
        text = shortcut

    fields = re.split(r"[ \t]+", text) if text else []
    if len(fields) != 5:
        raise ValueError("expected exactly 5 fields, got %d" % (len(fields),))

    minutes = _parse_field(fields[0], *_FIELD_SPECS[0])
    hours = _parse_field(fields[1], *_FIELD_SPECS[1])
    days_of_month = _parse_field(fields[2], *_FIELD_SPECS[2])
    months = _parse_field(fields[3], *_FIELD_SPECS[3])
    days_of_week = _parse_field(fields[4], *_FIELD_SPECS[4])

    # 0 and 7 both mean Sunday.
    days_of_week = {0 if value == 7 else value for value in days_of_week}

    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"

    return (
        minutes,
        hours,
        days_of_month,
        months,
        days_of_week,
        dom_restricted,
        dow_restricted,
    )


def next_run(expr: str, after: datetime) -> datetime:
    """Return the earliest matching minute strictly later than *after*.

    Raises ``TypeError`` if *expr* is not a string, and ``ValueError`` if the
    expression is invalid or no matching minute occurs within five years.
    """
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    if not isinstance(after, datetime):
        raise TypeError("after must be a datetime")

    (
        minutes,
        hours,
        days_of_month,
        months,
        days_of_week,
        dom_restricted,
        dow_restricted,
    ) = _parse(expr)

    candidate = after.replace(second=0, microsecond=0)
    if candidate <= after:
        try:
            candidate += timedelta(minutes=1)
        except OverflowError:
            raise ValueError("no matching minute within 5 years")

    try:
        limit = after + timedelta(days=366 * 5)
    except OverflowError:
        limit = datetime.max
    last_day = limit.date()

    hours_sorted = sorted(hours)
    minutes_sorted = sorted(minutes)
    one_day = timedelta(days=1)

    day = candidate.date()
    while day <= last_day:
        if day.month in months:
            cron_dow = (day.weekday() + 1) % 7
            dom_match = day.day in days_of_month
            dow_match = cron_dow in days_of_week

            if dom_restricted and dow_restricted:
                day_matches = dom_match or dow_match
            elif dom_restricted:
                day_matches = dom_match
            elif dow_restricted:
                day_matches = dow_match
            else:
                day_matches = True

            if day_matches:
                for hour in hours_sorted:
                    for minute in minutes_sorted:
                        moment = datetime(day.year, day.month, day.day, hour, minute)
                        if moment < candidate:
                            continue
                        if moment > limit:
                            raise ValueError("no matching minute within 5 years")
                        return moment

        day += one_day

    raise ValueError("no matching minute within 5 years")
