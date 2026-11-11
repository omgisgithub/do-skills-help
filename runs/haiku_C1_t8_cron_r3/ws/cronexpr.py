"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTH_NAMES = {
    name: number
    for number, name in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1
    )
}
_DOW_NAMES = {
    name: number
    for number, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])
}

# name, minimum, maximum, allowed names
_FIELDS = (
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day of month", 1, 31, {}),
    ("month", 1, 12, _MONTH_NAMES),
    ("day of week", 0, 7, _DOW_NAMES),
)

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_ITEM = re.compile(r"(\*|[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?)(?:/([0-9]+))?")
_NUMBER = re.compile(r"[0-9]+")


def _value(token, lo, hi, names):
    if _NUMBER.fullmatch(token):
        value = int(token)
    elif token.upper() in names:
        value = names[token.upper()]
    else:
        raise ValueError(f"invalid value {token!r}")
    if not lo <= value <= hi:
        raise ValueError(f"value {token!r} out of range {lo}-{hi}")
    return value


def _parse_field(text, lo, hi, names):
    values = set()
    for item in text.split(","):
        match = _ITEM.fullmatch(item)
        if not match:
            raise ValueError(f"invalid item {item!r}")
        base, step_text = match.group(1), match.group(2)
        step = 1
        if step_text is not None:
            step = int(step_text)
            if step < 1:
                raise ValueError(f"step must be at least 1 in {item!r}")
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            first, last = base.split("-")
            start = _value(first, lo, hi, names)
            end = _value(last, lo, hi, names)
            if start > end:
                raise ValueError(f"reversed range {base!r}")
        else:
            start = _value(base, lo, hi, names)
            end = hi if step_text is not None else start
        values.update(range(start, end + 1, step))
    return values


def _parse(expr):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    text = expr.strip()
    if text.startswith("@"):
        if text.lower() not in _SHORTCUTS:
            raise ValueError(f"unknown shortcut {expr!r}")
        text = _SHORTCUTS[text.lower()]
    parts = re.split(r"[ \t]+", text)
    if len(parts) != 5:
        raise ValueError(f"expected 5 fields in {expr!r}")

    fields = []
    for part, (_, lo, hi, names) in zip(parts, _FIELDS):
        fields.append(_parse_field(part, lo, hi, names))
    minutes, hours, doms, months, dows = fields

    # Sunday may be written as 0 or 7; both match the same days.
    dows = {0 if value == 7 else value for value in dows}
    dom_restricted = parts[2] != "*"
    dow_restricted = parts[4] != "*"
    return minutes, hours, doms, months, dows, dom_restricted, dow_restricted


def _day_matches(day, doms, dows, dom_restricted, dow_restricted):
    dom_ok = day.day in doms
    dow_ok = (day.weekday() + 1) % 7 in dows
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def _five_years_after(after):
    try:
        return after.replace(year=after.year + 5)
    except ValueError:  # Feb 29 in a non-leap target year
        return after.replace(year=after.year + 5, month=3, day=1)


def next_run(expr, after):
    """Return the first minute strictly after ``after`` matching ``expr``."""
    minutes, hours, doms, months, dows, dom_restricted, dow_restricted = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _five_years_after(after)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months and _day_matches(day, doms, dows, dom_restricted, dow_restricted):
            for hour in sorted(hours):
                for minute in sorted(minutes):
                    candidate = day.replace(hour=hour, minute=minute)
                    if candidate < start:
                        continue
                    if candidate > limit:
                        raise ValueError(f"no matching time within 5 years for {expr!r}")
                    return candidate
        day += timedelta(days=1)
    raise ValueError(f"no matching time within 5 years for {expr!r}")
