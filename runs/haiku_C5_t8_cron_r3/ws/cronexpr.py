"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, time, timedelta

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
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)
}
_DOW_NAMES = {
    name: number
    for number, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])
}

# (min, max, names) for minute, hour, day of month, month, day of week
_FIELDS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, _MONTH_NAMES),
    (0, 7, _DOW_NAMES),
]

_NUMBER = re.compile(r"[0-9]+")


def _value(token, names, lo, hi):
    if _NUMBER.fullmatch(token):
        value = int(token)
    elif token.upper() in names:
        value = names[token.upper()]
    else:
        raise ValueError(f"invalid value: {token!r}")
    if not lo <= value <= hi:
        raise ValueError(f"value out of range: {token!r}")
    return value


def _parse_field(text, lo, hi, names):
    values = set()
    for item in text.split(","):
        base, slash, step_text = item.partition("/")
        step = 1
        if slash:
            if not _NUMBER.fullmatch(step_text) or int(step_text) < 1:
                raise ValueError(f"invalid step: {item!r}")
            step = int(step_text)

        if base == "*":
            first, last = lo, hi
        elif "-" in base:
            low_text, _, high_text = base.partition("-")
            first = _value(low_text, names, lo, hi)
            last = _value(high_text, names, lo, hi)
            if first > last:
                raise ValueError(f"range must be ascending: {item!r}")
        else:
            first = _value(base, names, lo, hi)
            last = hi if slash else first

        values.update(range(first, last + 1, step))
    return values


def _parse(expr):
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    fields = re.split(r"[ \t]+", expr)
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}: {expr!r}")

    minutes, hours, dom, months, dow = (
        _parse_field(text, lo, hi, names)
        for text, (lo, hi, names) in zip(fields, _FIELDS)
    )
    dow = {day % 7 for day in dow}  # 7 is Sunday, same as 0
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"
    return minutes, hours, dom, months, dow, dom_restricted, dow_restricted


def _day_matches(day, dom, dow, dom_restricted, dow_restricted):
    dom_ok = day.day in dom
    dow_ok = day.isoweekday() % 7 in dow  # isoweekday: Monday=1 ... Sunday=7
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    if dom_restricted:
        return dom_ok
    if dow_restricted:
        return dow_ok
    return True


def _add_years(dt, years):
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:  # Feb 29 in a non-leap target year
        return dt.replace(year=dt.year + years, day=28)


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")

    minutes, hours, dom, months, dow, dom_restricted, dow_restricted = _parse(expr)
    minutes, hours = sorted(minutes), sorted(hours)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _add_years(after, 5)

    day = start.date()
    while day <= limit.date():
        if day.month in months and _day_matches(day, dom, dow, dom_restricted, dow_restricted):
            for hour in hours:
                for minute in minutes:
                    candidate = datetime.combine(day, time(hour, minute))
                    if start <= candidate <= limit:
                        return candidate
        day += timedelta(days=1)

    raise ValueError(f"no matching time within 5 years for {expr!r}")
