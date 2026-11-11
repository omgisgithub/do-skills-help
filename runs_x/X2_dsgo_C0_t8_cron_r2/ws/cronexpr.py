"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_DOW_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
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
_DIGITS_RE = re.compile(r"[0-9]+\Z")


def _parse_value(token, names, lo, hi):
    """Parse a single numeric or named value into its numeric form."""
    upper = token.upper()
    if names is not None and upper in names:
        value = names[upper]
    elif _DIGITS_RE.fullmatch(token):
        value = int(token)
    else:
        raise ValueError("invalid value: %r" % (token,))
    if not lo <= value <= hi:
        raise ValueError("value out of range: %r" % (token,))
    return value


def _parse_field(field, lo, hi, names=None):
    """Parse one cron field and return the set of matching numeric values."""
    if not field:
        raise ValueError("empty field")

    values = set()
    for item in field.split(","):
        if not item:
            raise ValueError("empty list item")

        base, sep, step_text = item.partition("/")
        if sep:
            if "/" in step_text:
                raise ValueError("invalid step: %r" % (item,))
            if not _DIGITS_RE.fullmatch(step_text):
                raise ValueError("invalid step: %r" % (step_text,))
            step = int(step_text)
            if step < 1:
                raise ValueError("step must be at least 1")
        else:
            step = 1
        if not base:
            raise ValueError("missing value: %r" % (item,))

        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            bounds = base.split("-")
            if len(bounds) != 2 or not bounds[0] or not bounds[1]:
                raise ValueError("invalid range: %r" % (base,))
            start = _parse_value(bounds[0], names, lo, hi)
            end = _parse_value(bounds[1], names, lo, hi)
            if start > end:
                raise ValueError("range wraps around: %r" % (base,))
        else:
            start = _parse_value(base, names, lo, hi)
            # A bare value is a single value; with a step it runs to the max.
            end = hi if sep else start

        values.update(range(start, end + 1, step))

    return values


def _matches_day(day, dom_set, dom_restricted, dow_set, dow_restricted):
    cron_dow = (day.weekday() + 1) % 7
    if dom_restricted and dow_restricted:
        return day.day in dom_set or cron_dow in dow_set
    if dom_restricted:
        return day.day in dom_set
    if dow_restricted:
        return cron_dow in dow_set
    return True


def _five_years_later(moment):
    try:
        return moment.replace(year=moment.year + 5)
    except ValueError:
        # February 29: use the last day of the same month five years later.
        try:
            return moment.replace(year=moment.year + 5, day=28)
        except ValueError:
            return datetime.max


def next_run(expr, after):
    """Return the earliest matching minute strictly after ``after``."""
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")

    text = expr.strip()
    text = _SHORTCUTS.get(text.lower(), text)
    fields = re.split(r"[ \t]+", text)
    if len(fields) != 5:
        raise ValueError("expression must have exactly five fields")

    minute_field, hour_field, dom_field, month_field, dow_field = fields

    minutes = sorted(_parse_field(minute_field, 0, 59))
    hours = sorted(_parse_field(hour_field, 0, 23))
    doms = _parse_field(dom_field, 1, 31)
    months = _parse_field(month_field, 1, 12, _MONTH_NAMES)
    dows = {value % 7 for value in _parse_field(dow_field, 0, 7, _DOW_NAMES)}

    dom_restricted = dom_field != "*"
    dow_restricted = dow_field != "*"

    # The first candidate minute is the next whole minute after ``after``.
    try:
        start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no matching time within five years")
    limit = _five_years_later(after)
    if start > limit:
        raise ValueError("no matching time within five years")

    day = start.date()
    last_day = limit.date()
    first_day = True

    while day <= last_day:
        if day.month in months and _matches_day(
            day, doms, dom_restricted, dows, dow_restricted
        ):
            for hour in hours:
                for minute in minutes:
                    candidate = datetime(
                        day.year, day.month, day.day, hour, minute
                    )
                    if first_day and candidate < start:
                        continue
                    if candidate > limit:
                        raise ValueError("no matching time within five years")
                    return candidate
        first_day = False
        day += timedelta(days=1)

    raise ValueError("no matching time within five years")
