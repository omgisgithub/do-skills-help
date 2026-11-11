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
_MONTHS = {name: number for number, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
_WEEKDAYS = {name: number for number, name in enumerate(
    ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"))}


def _field(text, minimum, maximum, names=None, sunday=False):
    """Parse one cron field, returning its selected values and restriction flag."""
    if not text:
        raise ValueError("empty cron field")

    def number(token):
        upper = token.upper()
        if names is not None and upper in names:
            return names[upper]
        if not token.isascii() or not token.isdigit():
            raise ValueError("invalid cron value")
        value = int(token)
        if not minimum <= value <= maximum:
            raise ValueError("cron value out of range")
        return value

    selected = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty cron list item")
        if item.count("/") > 1:
            raise ValueError("invalid cron step")
        if "/" in item:
            base, step_text = item.split("/")
            if not step_text.isascii() or not step_text.isdigit() or int(step_text) < 1:
                raise ValueError("invalid cron step")
            step = int(step_text)
        else:
            base, step = item, 1

        if base == "*":
            start, end = minimum, maximum
        elif base.count("-") == 1:
            left, right = base.split("-")
            start, end = number(left), number(right)
            if start > end:
                raise ValueError("descending cron range")
        elif "-" in base:
            raise ValueError("invalid cron range")
        else:
            start = number(base)
            # A stepped single value runs from that value through the field end.
            end = maximum if "/" in item else start

        selected.update(range(start, end + 1, step))

    if sunday:
        selected = {0 if value == 7 else value for value in selected}
    return selected, text != "*"


def _day_of_week(day):
    # datetime: Monday=0; cron: Sunday=0.
    return (day.weekday() + 1) % 7


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching cron minute strictly after ``after``."""
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")
    if not isinstance(after, datetime):
        raise TypeError("after must be a datetime")

    expression = _SHORTCUTS.get(expr.strip().lower(), expr.strip())
    fields = re.split(r"[ \t]+", expression) if expression else []
    if len(fields) != 5:
        raise ValueError("cron expression must have five fields")

    minutes, _ = _field(fields[0], 0, 59)
    hours, _ = _field(fields[1], 0, 23)
    month_days, dom_restricted = _field(fields[2], 1, 31)
    months, _ = _field(fields[3], 1, 12, _MONTHS)
    week_days, dow_restricted = _field(fields[4], 0, 7, _WEEKDAYS, sunday=True)

    # Clamp leap-day horizons to the last valid day in the target year.
    try:
        horizon = after.replace(year=after.year + 5)
    except ValueError:
        horizon = after.replace(year=after.year + 5, day=28)
    except OverflowError:
        raise ValueError("no matching minute within five years")

    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    hours = sorted(hours)
    minutes = sorted(minutes)
    while candidate <= horizon:
        current_date = candidate.date()
        if current_date.month in months:
            dom_match = current_date.day in month_days
            dow_match = _day_of_week(current_date) in week_days
            if (dom_match and dow_match if not (dom_restricted and dow_restricted)
                    else dom_match or dow_match):
                for hour in hours:
                    if hour < candidate.hour:
                        continue
                    for minute in minutes:
                        if hour == candidate.hour and minute < candidate.minute:
                            continue
                        result = candidate.replace(hour=hour, minute=minute)
                        if result <= horizon:
                            return result
                        break
        candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)

    raise ValueError("no matching minute within five years")
