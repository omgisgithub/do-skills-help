"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
from datetime import datetime, timedelta
import re


_MONTHS = {
    name: number
    for number, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
        1,
    )
}
_WEEKDAYS = {
    name: number
    for number, name in enumerate(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"))
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
_INTEGER = re.compile(r"[0-9]+\Z")


def _parse_field(text, minimum, maximum, names=None, sunday=False):
    """Return the allowed values and whether the field is exactly '*'."""
    if not text:
        raise ValueError("empty cron field")
    values = set()

    def parse_value(value):
        upper = value.upper()
        if names is not None and upper in names:
            return names[upper]
        if not _INTEGER.fullmatch(value):
            raise ValueError("invalid cron value")
        number = int(value)
        if not minimum <= number <= maximum:
            raise ValueError("cron value out of range")
        return number

    for item in text.split(","):
        if not item:
            raise ValueError("empty cron list item")
        if item.count("/") > 1:
            raise ValueError("invalid cron step")
        if "/" in item:
            base, step_text = item.split("/")
            if not _INTEGER.fullmatch(step_text) or int(step_text) < 1:
                raise ValueError("invalid cron step")
            step = int(step_text)
        else:
            base, step = item, 1

        if base == "*":
            start, end = minimum, maximum
        elif base.count("-") == 1:
            start_text, end_text = base.split("-")
            start, end = parse_value(start_text), parse_value(end_text)
            if start > end:
                raise ValueError("reversed cron range")
        elif "-" in base:
            raise ValueError("invalid cron range")
        else:
            start = parse_value(base)
            end = maximum

        values.update(range(start, end + 1, step))

    if sunday and 7 in values:
        values.remove(7)
        values.add(0)
    return values, text == "*"


def _parse_expression(expr):
    stripped = expr.strip()
    expression = _SHORTCUTS.get(stripped.lower(), stripped)
    fields = re.split(r"[ \t]+", expression.strip(" \t"))
    if len(fields) != 5 or any(not field for field in fields):
        raise ValueError("cron expression must have five fields")
    minute = _parse_field(fields[0], 0, 59)[0]
    hour = _parse_field(fields[1], 0, 23)[0]
    day, day_unrestricted = _parse_field(fields[2], 1, 31)
    month = _parse_field(fields[3], 1, 12, _MONTHS)[0]
    weekday, weekday_unrestricted = _parse_field(fields[4], 0, 7, _WEEKDAYS, sunday=True)
    return minute, hour, day, day_unrestricted, month, weekday, weekday_unrestricted


def _day_matches(current, day_values, day_unrestricted, weekdays, weekday_unrestricted):
    day_match = current.day in day_values
    weekday_match = ((current.weekday() + 1) % 7) in weekdays
    if day_unrestricted and weekday_unrestricted:
        return True
    if day_unrestricted:
        return weekday_match
    if weekday_unrestricted:
        return day_match
    return day_match or weekday_match


def next_run(expr: str, after: datetime) -> datetime:
    if not isinstance(expr, str):
        raise TypeError("expr must be a string")

    minutes, hours, days, day_unrestricted, months, weekdays, weekday_unrestricted = _parse_expression(expr)

    # Cron schedules have minute precision, and the result must be strictly later.
    try:
        first = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no matching minute within five years")

    if after.year <= 9994:
        cutoff_year = after.year + 5
        cutoff_day = min(after.day, 28)
        cutoff = after.replace(year=cutoff_year, day=cutoff_day)
        # Restore the original day when it exists in the target month.
        try:
            cutoff = cutoff.replace(day=after.day)
        except ValueError:
            pass
    else:
        # A datetime near year 9999 cannot represent a five-year horizon.
        cutoff = datetime.max

    current_date = first.date()
    final_date = cutoff.date()
    while current_date <= final_date:
        if current_date.month in months and _day_matches(
            current_date, days, day_unrestricted, weekdays, weekday_unrestricted
        ):
            for hour in sorted(hours):
                for minute in sorted(minutes):
                    candidate = datetime(
                        current_date.year, current_date.month, current_date.day, hour, minute
                    )
                    if candidate >= first and candidate <= cutoff:
                        return candidate
        if current_date == final_date:
            break
        current_date += timedelta(days=1)

    raise ValueError("no matching minute within five years")
