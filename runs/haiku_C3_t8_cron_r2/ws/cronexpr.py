"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_DIGITS = re.compile(r"[0-9]+")
_SEPARATOR = re.compile(r"[ \t]+")

_MONTH_NAMES = {
    name: number
    for number, name in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
        start=1,
    )
}
_DOW_NAMES = {
    name: number
    for number, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])
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

# (min, max, names) for minute, hour, day of month, month, day of week.
# Day of week allows 7 so that 7 can mean Sunday; it is folded to 0 later.
_FIELDS = [
    (0, 59, None),
    (0, 23, None),
    (1, 31, None),
    (1, 12, _MONTH_NAMES),
    (0, 7, _DOW_NAMES),
]


def _parse_value(token, lo, hi, names):
    if names and token.upper() in names:
        return names[token.upper()]
    if not _DIGITS.fullmatch(token):
        raise ValueError(f"invalid cron value: {token!r}")
    value = int(token)
    if not lo <= value <= hi:
        raise ValueError(f"cron value {value} outside {lo}-{hi}")
    return value


def _parse_field(text, lo, hi, names):
    values = set()
    for item in text.split(","):
        base, slash, step_text = item.partition("/")
        step = 1
        if slash:
            if not _DIGITS.fullmatch(step_text) or int(step_text) < 1:
                raise ValueError(f"invalid cron step: {item!r}")
            step = int(step_text)

        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            first, _, last = base.partition("-")
            start = _parse_value(first, lo, hi, names)
            end = _parse_value(last, lo, hi, names)
            if start > end:
                raise ValueError(f"cron range runs backwards: {item!r}")
        else:
            start = _parse_value(base, lo, hi, names)
            end = hi if slash else start

        values.update(range(start, end + 1, step))
    return values


def _parse(expr):
    fields = _SEPARATOR.split(expr.strip())
    if len(fields) != 5:
        raise ValueError(f"cron expression needs 5 fields: {expr!r}")

    sets = [_parse_field(text, lo, hi, names)
            for text, (lo, hi, names) in zip(fields, _FIELDS)]
    # Fold Sunday-as-7 onto 0 so matching only has to check 0-6.
    sets[4] = {value % 7 for value in sets[4]}
    restricted = [text != "*" for text in fields]
    return sets, restricted


def _day_matches(day, doms, dows, dom_restricted, dow_restricted):
    dom_ok = day.day in doms
    dow_ok = day.isoweekday() % 7 in dows
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    # An unrestricted field's set covers every value, so AND-ing is safe here.
    return dom_ok and dow_ok


def _add_years(dt, years):
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:  # 29 Feb in a non-leap target year
        return dt.replace(year=dt.year + years, day=28)


def _first_of_next_month(dt):
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0)
    return dt.replace(month=dt.month + 1, day=1, hour=0, minute=0)


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError(f"expr must be str, not {type(expr).__name__}")
    expr = _SHORTCUTS.get(expr.strip().lower(), expr)

    (minutes, hours, doms, months, dows), restricted = _parse(expr)
    dom_restricted = restricted[2]
    dow_restricted = restricted[4]
    deadline = _add_years(after, 5)

    # Walk forward, skipping whole months, days, and hours when they cannot match.
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while t <= deadline:
        if t.month not in months:
            t = _first_of_next_month(t)
        elif not _day_matches(t, doms, dows, dom_restricted, dow_restricted):
            t = t.replace(hour=0, minute=0) + timedelta(days=1)
        elif t.hour not in hours:
            t = t.replace(minute=0) + timedelta(hours=1)
        elif t.minute not in minutes:
            t += timedelta(minutes=1)
        else:
            return t
    raise ValueError(f"no matching time within 5 years after {after}: {expr!r}")
