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

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_NUMBER_RE = re.compile(r"[0-9]+\Z")


def _parse_value(token, low, high, names):
    """Parse a single number or (if allowed for the field) a name."""
    if _NUMBER_RE.match(token):
        value = int(token)
    else:
        if names is None:
            raise ValueError("names are not allowed in this field")
        try:
            value = names[token.upper()]
        except KeyError:
            raise ValueError("invalid value: %r" % (token,))
    if not low <= value <= high:
        raise ValueError("value out of range: %r" % (token,))
    return value


def _parse_field(text, low, high, names):
    """Parse one cron field into a set of integer values."""
    values = set()

    for item in text.split(","):
        if item == "":
            raise ValueError("empty list item")

        if item.count("/") > 1:
            raise ValueError("invalid item: %r" % (item,))

        if "/" in item:
            base, step_text = item.split("/")
            if not _NUMBER_RE.match(step_text):
                raise ValueError("invalid step: %r" % (step_text,))
            step = int(step_text)
            if step < 1:
                raise ValueError("step must be at least 1")
        else:
            base = item
            step = None

        if base == "*":
            start, end = low, high
        elif "-" in base:
            if base.count("-") != 1:
                raise ValueError("invalid range: %r" % (base,))
            left, right = base.split("-")
            start = _parse_value(left, low, high, names)
            end = _parse_value(right, low, high, names)
            if start > end:
                raise ValueError("range start is after range end: %r" % (base,))
        else:
            start = _parse_value(base, low, high, names)
            end = high if step is not None else start

        if step is None:
            step = 1

        for value in range(start, end + 1, step):
            values.add(value)

    return values


def _cron_weekday(day):
    """Python weekday (Mon=0) to cron weekday (Sun=0)."""
    return (day.weekday() + 1) % 7


def _day_matches(day, dom_values, dow_values, dom_restricted, dow_restricted):
    dom_ok = day.day in dom_values
    dow_ok = _cron_weekday(day) in dow_values

    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    if dom_restricted:
        return dom_ok
    if dow_restricted:
        return dow_ok
    return True


def _earliest_time(hours, minutes, threshold):
    """Earliest (hour, minute) at or after *threshold* minutes, or None."""
    threshold_hour, threshold_minute = divmod(threshold, 60)

    for hour in hours:
        if hour < threshold_hour:
            continue
        if hour == threshold_hour:
            for minute in minutes:
                if minute >= threshold_minute:
                    return hour, minute
        else:
            return hour, minutes[0]

    return None


def next_run(expr, after):
    """Return the first matching minute strictly after *after*.

    Raises ValueError for invalid expressions or when no match exists within
    five years, and TypeError when *expr* is not a string.
    """
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")

    text = expr.strip()
    text = _SHORTCUTS.get(text.lower(), text)

    fields = re.split(r"[ \t]+", text)
    if len(fields) != 5:
        raise ValueError("cron expression must have exactly five fields")

    minute_text, hour_text, dom_text, month_text, dow_text = fields

    minutes = sorted(_parse_field(minute_text, 0, 59, None))
    hours = sorted(_parse_field(hour_text, 0, 23, None))
    dom_values = _parse_field(dom_text, 1, 31, None)
    month_values = _parse_field(month_text, 1, 12, _MONTH_NAMES)
    dow_raw = _parse_field(dow_text, 0, 7, _DOW_NAMES)

    # 7 and 0 both mean Sunday.
    dow_values = {0 if value == 7 else value for value in dow_raw}

    dom_restricted = dom_text != "*"
    dow_restricted = dow_text != "*"

    try:
        start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no matching time within five years")

    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:
        try:
            limit = after.replace(year=after.year + 5, day=28)
        except ValueError:
            limit = datetime.max

    end_day = limit.date()
    day = start.date()
    first_day = True

    while day <= end_day:
        if day.month in month_values and _day_matches(
            day, dom_values, dow_values, dom_restricted, dow_restricted
        ):
            threshold = start.hour * 60 + start.minute if first_day else 0
            found = _earliest_time(hours, minutes, threshold)
            if found is not None:
                candidate = datetime(day.year, day.month, day.day, found[0], found[1])
                if candidate > limit:
                    raise ValueError("no matching time within five years")
                return candidate

        first_day = False
        if day == end_day:
            break
        day += timedelta(days=1)

    raise ValueError("no matching time within five years")
