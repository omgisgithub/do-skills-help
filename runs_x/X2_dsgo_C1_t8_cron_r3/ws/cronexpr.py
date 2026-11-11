"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MINUTE, _HOUR, _DOM, _MONTH, _DOW = range(5)

# Inclusive (minimum, maximum) for each field, in field order.
_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))

_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_DOW_NAMES = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6,
}
_NAMES = {_MONTH: _MONTH_NAMES, _DOW: _DOW_NAMES}

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_UINT = re.compile(r"[0-9]+")


def _parse_value(token, field):
    """Parse a single number or a name valid for ``field``."""
    names = _NAMES.get(field)
    if names is not None:
        value = names.get(token.lower())
        if value is not None:
            return value
    if _UINT.fullmatch(token) is None:
        raise ValueError("invalid value %r" % (token,))
    value = int(token)
    lo, hi = _RANGES[field]
    if not lo <= value <= hi:
        raise ValueError("value %r out of range for field %d" % (token, field))
    return value


def _parse_item(item, field):
    """Expand one comma-separated item into a set of field values."""
    if not item:
        raise ValueError("empty item")

    base, sep, step_text = item.partition("/")
    step = None
    if sep:
        if _UINT.fullmatch(step_text) is None:
            raise ValueError("invalid step %r" % (step_text,))
        step = int(step_text)
        if step < 1:
            raise ValueError("step must be at least 1")

    lo, hi = _RANGES[field]
    if base == "*":
        return set(range(lo, hi + 1, step) if step is not None
                   else range(lo, hi + 1))

    if "-" in base:
        if base.count("-") != 1:
            raise ValueError("invalid range %r" % (base,))
        left, right = base.split("-")
        low = _parse_value(left, field)
        high = _parse_value(right, field)
        if low > high:
            raise ValueError("range %r is reversed" % (base,))
        return set(range(low, high + 1, step) if step is not None
                   else range(low, high + 1))

    value = _parse_value(base, field)
    if step is None:
        return {value}
    return set(range(value, hi + 1, step))


def _parse_field(text, field):
    values = set()
    for item in text.split(","):
        values.update(_parse_item(item, field))
    if field == _DOW:
        # 0 and 7 are both Sunday.
        values = {0 if value == 7 else value for value in values}
    return frozenset(values)


def _parse(expr):
    text = expr.strip()
    expansion = _SHORTCUTS.get(text.lower())
    if expansion is not None:
        text = expansion

    fields = re.split(r"[ \t]+", text)
    if len(fields) != 5:
        raise ValueError("expected 5 fields, got %d" % (len(fields),))

    parsed = [_parse_field(field_text, index)
              for index, field_text in enumerate(fields)]
    dom_restricted = fields[_DOM] != "*"
    dow_restricted = fields[_DOW] != "*"
    return parsed, dom_restricted, dow_restricted


def _day_matches(day_of_month, day_of_week, doms, dows,
                 dom_restricted, dow_restricted):
    dom_ok = day_of_month in doms
    dow_ok = day_of_week in dows
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    if dom_restricted:
        return dom_ok
    if dow_restricted:
        return dow_ok
    return True


def _five_years_after(after):
    year = after.year + 5
    if year > datetime.max.year:
        return datetime.max
    try:
        return after.replace(year=year)
    except ValueError:
        # Only possible when ``after`` is February 29 and the target year
        # is not a leap year.
        return after.replace(year=year, month=2, day=28)


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly later than ``after``."""
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")

    parsed, dom_restricted, dow_restricted = _parse(expr)
    minutes, hours, doms, months, dows = parsed

    try:
        start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no matching minute exists after %r" % (after,))
    limit = _five_years_after(after)
    minute_list = sorted(minutes)
    hour_list = sorted(hours)

    day = start.date()
    last_day = limit.date()
    while day <= last_day:
        # Python's Monday is 0; cron's Sunday is 0 and Monday is 1.
        day_of_week = (day.weekday() + 1) % 7
        if (day.month in months
                and _day_matches(day.day, day_of_week, doms, dows,
                                 dom_restricted, dow_restricted)):
            for hour in hour_list:
                for minute in minute_list:
                    candidate = datetime(day.year, day.month, day.day,
                                         hour, minute)
                    if candidate < start:
                        continue
                    if candidate > limit:
                        raise ValueError(
                            "no matching minute within 5 years of %r" % (after,))
                    return candidate
        try:
            day += timedelta(days=1)
        except OverflowError:
            break

    raise ValueError("no matching minute within 5 years of %r" % (after,))
