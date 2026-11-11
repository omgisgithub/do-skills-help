"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MINUTE = 0
_HOUR = 1
_DOM = 2
_MONTH = 3
_DOW = 4

_MONTH_NAMES = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_DOW_NAMES = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}

# (minimum, maximum, allowed names) for each of the five fields.
_FIELDS = {
    _MINUTE: (0, 59, None),
    _HOUR: (0, 23, None),
    _DOM: (1, 31, None),
    _MONTH: (1, 12, _MONTH_NAMES),
    _DOW: (0, 7, _DOW_NAMES),
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


def _parse_value(text, field_index):
    """Parse one numeric value or name for a field."""
    minimum, maximum, names = _FIELDS[field_index]
    if names is not None and text.lower() in names:
        value = names[text.lower()]
    elif text.isdigit():
        value = int(text)
    else:
        raise ValueError("invalid value %r" % (text,))
    if value < minimum or value > maximum:
        raise ValueError("value %r out of range" % (text,))
    return value


def _parse_field(text, field_index):
    """Return (set of allowed values, restricted flag) for one field."""
    minimum, maximum, _ = _FIELDS[field_index]
    restricted = text != "*"
    values = set()

    for item in text.split(","):
        if not item:
            raise ValueError("empty item")

        if "/" in item:
            if item.count("/") != 1:
                raise ValueError("invalid step %r" % (item,))
            base, step_text = item.split("/")
            if not step_text.isdigit():
                raise ValueError("invalid step %r" % (step_text,))
            step = int(step_text)
            if step < 1:
                raise ValueError("invalid step %r" % (step_text,))
        else:
            base = item
            step = 1

        if base == "*":
            low, high = minimum, maximum
        elif "-" in base:
            if base.count("-") != 1:
                raise ValueError("invalid range %r" % (base,))
            start_text, end_text = base.split("-")
            low = _parse_value(start_text, field_index)
            high = _parse_value(end_text, field_index)
            if low > high:
                raise ValueError("invalid range %r" % (base,))
        else:
            value = _parse_value(base, field_index)
            if step == 1:
                low = high = value
            else:
                # "N/S" runs from N up to the field maximum.
                low, high = value, maximum

        values.update(range(low, high + 1, step))

    return values, restricted


def _parse(expr):
    """Parse a whole expression into (minute, hour, dom, month, dow, flags)."""
    text = expr.strip()
    if text.startswith("@"):
        shortcut = _SHORTCUTS.get(text.lower())
        if shortcut is None:
            raise ValueError("unknown shortcut %r" % (expr,))
        text = shortcut

    fields = re.split(r"[ \t]+", text)
    if len(fields) != 5:
        raise ValueError("expected 5 fields")

    minute, _ = _parse_field(fields[_MINUTE], _MINUTE)
    hour, _ = _parse_field(fields[_HOUR], _HOUR)
    dom, dom_restricted = _parse_field(fields[_DOM], _DOM)
    month, _ = _parse_field(fields[_MONTH], _MONTH)
    dow, dow_restricted = _parse_field(fields[_DOW], _DOW)

    # In cron, 7 is also Sunday.
    if 7 in dow:
        dow.discard(7)
        dow.add(0)

    return minute, hour, dom, month, dow, dom_restricted, dow_restricted


def _add_years(moment, years):
    try:
        return moment.replace(year=moment.year + years)
    except ValueError:
        try:
            # February 29 in a non-leap target year.
            return moment.replace(year=moment.year + years, day=28)
        except ValueError:
            # Target year would exceed datetime's range.
            return datetime.max


def next_run(expr, after):
    """Return the earliest matching minute strictly after ``after``."""
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    if not isinstance(after, datetime):
        raise TypeError("after must be a datetime")

    minute_set, hour_set, dom_set, month_set, dow_set, dom_restricted, dow_restricted = _parse(expr)

    minutes = sorted(minute_set)
    hours = sorted(hour_set)

    try:
        start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no matching minute within 5 years")
    limit = _add_years(after, 5)

    def day_matches(day):
        dom_ok = day.day in dom_set
        dow_ok = ((day.weekday() + 1) % 7) in dow_set
        if dom_restricted and dow_restricted:
            return dom_ok or dow_ok
        if dom_restricted:
            return dom_ok
        if dow_restricted:
            return dow_ok
        return True

    day = start.date()
    last_day = limit.date()
    while day <= last_day:
        if day.month in month_set and day_matches(day):
            same_day = day == start.date()
            for hour in hours:
                if same_day and hour < start.hour:
                    continue
                for minute in minutes:
                    if same_day and hour == start.hour and minute < start.minute:
                        continue
                    candidate = datetime(day.year, day.month, day.day, hour, minute)
                    if candidate <= limit:
                        return candidate
                    # Nothing later can fit within the limit.
                    raise ValueError("no matching minute within 5 years")
        day += timedelta(days=1)

    raise ValueError("no matching minute within 5 years")
