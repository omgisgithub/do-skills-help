"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import calendar
import re
from datetime import timedelta

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_MONTH_NAMES = {
    name: number
    for number, name in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1
    )
}
_DOW_NAMES = {name: number for number, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])}

# (min, max, names) for minute, hour, day of month, month, day of week.
_FIELDS = (
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, _MONTH_NAMES),
    (0, 7, _DOW_NAMES),
)

_NUMBER = re.compile(r"[0-9]+")
_SEPARATOR = re.compile(r"[ \t]+")
_MAX_YEARS = 5


def _parse_value(token, lo, hi, names):
    if _NUMBER.fullmatch(token):
        value = int(token)
    elif token.upper() in names:
        value = names[token.upper()]
    else:
        raise ValueError(f"invalid value {token!r}")
    if not lo <= value <= hi:
        raise ValueError(f"value {value} out of range {lo}-{hi}")
    return value


def _parse_item(item, lo, hi, names):
    base, slash, step_text = item.partition("/")
    if slash:
        if not _NUMBER.fullmatch(step_text) or int(step_text) < 1:
            raise ValueError(f"invalid step in {item!r}")
        step = int(step_text)
    else:
        step = 1

    if base == "*":
        start, end = lo, hi
    elif "-" in base:
        first, _, last = base.partition("-")
        start = _parse_value(first, lo, hi, names)
        end = _parse_value(last, lo, hi, names)
        if start > end:
            raise ValueError(f"reversed range {base!r}")
    else:
        start = _parse_value(base, lo, hi, names)
        end = hi if slash else start
    return range(start, end + 1, step)


def _parse_field(text, lo, hi, names):
    values = set()
    for item in text.split(","):
        values.update(_parse_item(item, lo, hi, names))
    return values


def _parse(expr):
    if not isinstance(expr, str):
        raise TypeError(f"expr must be str, not {type(expr).__name__}")
    text = _SHORTCUTS.get(expr.strip(" \t").lower(), expr.strip(" \t"))
    fields = _SEPARATOR.split(text)
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}")

    sets = [_parse_field(field, lo, hi, names) for field, (lo, hi, names) in zip(fields, _FIELDS)]
    # Sunday is both 0 and 7 in the day-of-week field.
    sets[4] = {value % 7 for value in sets[4]}
    restricted = (fields[2] != "*", fields[4] != "*")
    return sets, restricted


def _day_matches(day, dom_set, dow_set, dom_restricted, dow_restricted):
    dom_ok = day.day in dom_set
    dow_ok = (day.weekday() + 1) % 7 in dow_set
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def _limit(after):
    year = after.year + _MAX_YEARS
    day = min(after.day, calendar.monthrange(year, after.month)[1])
    return after.replace(year=year, day=day)


def next_run(expr, after):
    sets, (dom_restricted, dow_restricted) = _parse(expr)
    minute_set, hour_set, dom_set, month_set, dow_set = sets

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _limit(after)
    times = [(hour, minute) for hour in sorted(hour_set) for minute in sorted(minute_set)]

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in month_set and _day_matches(day, dom_set, dow_set, dom_restricted, dow_restricted):
            for hour, minute in times:
                candidate = day.replace(hour=hour, minute=minute)
                if start <= candidate <= limit:
                    return candidate
        day += timedelta(days=1)

    raise ValueError(f"no matching time for {expr!r} within {_MAX_YEARS} years")
