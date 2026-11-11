"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
from datetime import datetime, timedelta
import re


_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_MONTHS = dict(zip(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
    range(1, 13),
))
_WEEKDAYS = dict(zip(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"), range(7)))


def _value(text, names, minimum, maximum, dow=False):
    if text in names:
        return names[text]
    if not re.fullmatch(r"[0-9]+", text):
        raise ValueError("invalid cron value")
    value = int(text)
    if dow and value == 7:
        return 0
    if not minimum <= value <= maximum:
        raise ValueError("cron value out of range")
    return value


def _field(text, minimum, maximum, names=None, dow=False):
    names = names or {}
    allowed_max = 7 if dow else maximum
    values = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty cron list item")
        pieces = item.split("/")
        if len(pieces) > 2:
            raise ValueError("invalid step")
        base = pieces[0]
        step = 1
        if len(pieces) == 2:
            if not re.fullmatch(r"[0-9]+", pieces[1]) or int(pieces[1]) < 1:
                raise ValueError("invalid step")
            step = int(pieces[1])

        if base == "*":
            start, end = minimum, allowed_max
        elif "-" in base:
            bounds = base.split("-")
            if len(bounds) != 2 or not all(bounds):
                raise ValueError("invalid range")
            start = _value(bounds[0], names, minimum, maximum, dow)
            end = _value(bounds[1], names, minimum, maximum, dow)
            # DOW 7 is a Sunday endpoint but must retain its numeric ordering
            # while expanding a range such as 5-7.
            if dow:
                if bounds[0] == "7":
                    start = 7
                if bounds[1] == "7":
                    end = 7
            if start > end:
                raise ValueError("descending range")
        else:
            start = _value(base, names, minimum, maximum, dow)
            end = allowed_max
            if dow and base == "7":
                start = 7
            if len(pieces) == 1:
                end = start

        for value in range(start, end + 1, step):
            values.add(0 if dow and value == 7 else value)
    return values


def _anniversary(dt):
    try:
        return dt.replace(year=dt.year + 5)
    except ValueError:  # Feb 29 in a non-leap anniversary year
        return dt.replace(year=dt.year + 5, day=28)


def next_run(expr: str, after: datetime) -> datetime:
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")
    if not isinstance(after, datetime):
        raise TypeError("after must be a datetime")

    expression = expr.strip(" \t")
    expression = _SHORTCUTS.get(expression.lower(), expression).upper()
    fields = re.split(r"[ \t]+", expression) if expression else []
    if len(fields) != 5:
        raise ValueError("cron expression must contain five fields")

    minute_text, hour_text, dom_text, month_text, dow_text = fields
    minutes = _field(minute_text, 0, 59)
    hours = _field(hour_text, 0, 23)
    dom = _field(dom_text, 1, 31)
    months = _field(month_text, 1, 12, _MONTHS)
    dow = _field(dow_text, 0, 6, _WEEKDAYS, dow=True)
    dom_restricted = dom_text != "*"
    dow_restricted = dow_text != "*"

    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        deadline = _anniversary(after)
    except ValueError:
        deadline = datetime.max
    while candidate <= deadline:
        if candidate.month in months and candidate.hour in hours and candidate.minute in minutes:
            dom_match = candidate.day in dom
            # datetime Monday=0; cron Sunday=0.
            cron_dow = (candidate.weekday() + 1) % 7
            dow_match = cron_dow in dow
            if ((dom_match or dow_match) if dom_restricted and dow_restricted
                    else (dom_match if dom_restricted else dow_match if dow_restricted else True)):
                return candidate
        try:
            candidate += timedelta(minutes=1)
        except OverflowError:
            break
    raise ValueError("no matching minute within five years")
