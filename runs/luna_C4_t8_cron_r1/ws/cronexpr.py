"""Parse classic cron expressions and find their next matching minute."""

import calendar
import re
from datetime import datetime, timedelta


_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_MONTHS = {name.upper(): number for number, name in enumerate(calendar.month_abbr) if name}
_WEEKDAYS = {
    name.upper(): number
    for number, name in enumerate(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"))
}


def _field_values(field, minimum, maximum, names=None, sunday=False):
    """Parse one cron field into its selected values and restriction flag."""
    selected = set()
    for item in field.split(","):
        if not item:
            raise ValueError("empty cron field item")
        base, separator, step_text = item.partition("/")
        if separator:
            if not re.fullmatch(r"\d+", step_text) or int(step_text) < 1:
                raise ValueError("invalid cron step")
            step = int(step_text)
        else:
            step = 1

        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            if base.count("-") != 1:
                raise ValueError("invalid cron range")
            start_text, end_text = base.split("-")
            start = _value(start_text, minimum, maximum, names, sunday)
            end = _value(end_text, minimum, maximum, names, sunday)
            if start > end:
                raise ValueError("descending cron range")
        else:
            start = _value(base, minimum, maximum, names, sunday)
            end = maximum if separator else start
        selected.update(range(start, end + 1, step))
    return selected, field != "*"


def _value(text, minimum, maximum, names, sunday):
    if names is not None and text.upper() in names:
        value = names[text.upper()]
    elif re.fullmatch(r"\d+", text):
        value = int(text)
    else:
        raise ValueError("invalid cron value")
    if sunday and value == 7:
        value = 0
    if not minimum <= value <= maximum:
        raise ValueError("cron value outside field range")
    return value


def _deadline(after):
    year = after.year + 5
    day = min(after.day, calendar.monthrange(year, after.month)[1])
    return after.replace(year=year, day=day)


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first minute strictly after ``after`` that matches ``expr``."""
    if not isinstance(expr, str):
        raise TypeError("cron expression must be a string")
    normalized = expr.strip().lower()
    normalized = _SHORTCUTS.get(normalized, normalized)
    fields = re.split(r"[ \t]+", normalized) if normalized else []
    if len(fields) != 5:
        raise ValueError("cron expression must contain five fields")

    minutes, _ = _field_values(fields[0], 0, 59)
    hours, _ = _field_values(fields[1], 0, 23)
    month_days, month_day_restricted = _field_values(fields[2], 1, 31)
    months, _ = _field_values(fields[3], 1, 12, _MONTHS)
    week_days, week_day_restricted = _field_values(fields[4], 0, 6, _WEEKDAYS, sunday=True)

    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    deadline = _deadline(after)
    while candidate <= deadline:
        if candidate.month in months:
            month_day_matches = candidate.day in month_days
            week_day_matches = (candidate.weekday() + 1) % 7 in week_days
            if month_day_restricted and week_day_restricted:
                day_matches = month_day_matches or week_day_matches
            elif month_day_restricted:
                day_matches = month_day_matches
            elif week_day_restricted:
                day_matches = week_day_matches
            else:
                day_matches = True
            if day_matches and candidate.hour in hours and candidate.minute in minutes:
                return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("no matching minute within five years")
