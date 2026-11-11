"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta


_MONTHS = {
    name: number for number, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG",
         "SEP", "OCT", "NOV", "DEC"), 1
    )
}
_WEEKDAYS = {
    name: number for number, name in enumerate(
        ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
    )
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


def _field(text, minimum, maximum, names=None, sunday=False):
    """Parse one field, returning its selected values and whether it is restricted."""
    restricted = text != "*"
    selected = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty cron field item")
        pieces = item.split("/")
        if len(pieces) > 2 or (len(pieces) == 2 and not pieces[1].isdigit()):
            raise ValueError("invalid cron step")
        step = int(pieces[1]) if len(pieces) == 2 else 1
        if step < 1:
            raise ValueError("cron step must be positive")
        base = pieces[0]

        def value(token):
            token = token.upper()
            if names is not None and token in names:
                return names[token]
            if not token.isdigit():
                raise ValueError("invalid cron value")
            return int(token)

        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            ends = base.split("-")
            if len(ends) != 2 or not all(ends):
                raise ValueError("invalid cron range")
            start, end = map(value, ends)
        else:
            start = value(base)
            end = maximum if len(pieces) == 2 else start

        if start < minimum or start > maximum or end < minimum or end > maximum:
            raise ValueError("cron value out of range")
        if start > end:
            raise ValueError("descending cron range")
        vals = range(start, end + 1, step)
        if sunday:
            selected.update(0 if v == 7 else v for v in vals)
        else:
            selected.update(vals)
    return selected, restricted


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after *after*."""
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")
    if not isinstance(after, datetime):
        raise TypeError("after must be a datetime")
    expression = expr.strip()
    expression = _SHORTCUTS.get(expression.lower(), expression)
    fields = re.split(r"[ \t]+", expression) if expression else []
    if len(fields) != 5:
        raise ValueError("cron expression must have five fields")
    minute, _ = _field(fields[0], 0, 59)
    hour, _ = _field(fields[1], 0, 23)
    dom, dom_restricted = _field(fields[2], 1, 31)
    month, _ = _field(fields[3], 1, 12, _MONTHS)
    dow, dow_restricted = _field(fields[4], 0, 7, _WEEKDAYS, sunday=True)

    # Minute stepping ensures strictness for inputs with seconds and microseconds.
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # February 29 has no matching date in the target year.
        limit = after.replace(year=after.year + 5, day=28)
    except OverflowError:
        limit = datetime.max
    while candidate <= limit:
        if (candidate.minute in minute and candidate.hour in hour and
                candidate.month in month):
            day_of_month = candidate.day in dom
            # Python Monday=0; cron Sunday=0.
            day_of_week = (candidate.weekday() + 1) % 7 in dow
            if dom_restricted and dow_restricted:
                day_matches = day_of_month or day_of_week
            elif dom_restricted:
                day_matches = day_of_month
            elif dow_restricted:
                day_matches = day_of_week
            else:
                day_matches = True
            if day_matches:
                return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("no matching minute within five years")
