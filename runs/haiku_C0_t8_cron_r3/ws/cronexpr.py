"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
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

_MONTH_NAMES = {
    name: number
    for number, name in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)
}
_DOW_NAMES = {
    name: number
    for number, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])
}

# (field name, min, max, names) in expression order
_FIELDS = (
    ("minute", 0, 59, {}),
    ("hour", 0, 23, {}),
    ("day of month", 1, 31, {}),
    ("month", 1, 12, _MONTH_NAMES),
    ("day of week", 0, 7, _DOW_NAMES),
)

_ITEM_RE = re.compile(r"(\*|[0-9A-Za-z]+(?:-[0-9A-Za-z]+)?)(?:/([0-9A-Za-z]+))?")


def _parse_value(token, field):
    name, lo, hi, names = field
    if re.fullmatch(r"[0-9]+", token):
        value = int(token)
    elif token.upper() in names:
        value = names[token.upper()]
    else:
        raise ValueError(f"invalid {name} value: {token!r}")
    if not lo <= value <= hi:
        raise ValueError(f"{name} value out of range: {token!r}")
    return value


def _parse_field(text, field):
    name, lo, hi, _ = field
    values = set()
    for item in text.split(","):
        match = _ITEM_RE.fullmatch(item)
        if not match:
            raise ValueError(f"invalid {name} item: {item!r}")
        base, step_text = match.groups()
        step = 1
        if step_text is not None:
            if not re.fullmatch(r"[0-9]+", step_text) or int(step_text) < 1:
                raise ValueError(f"invalid {name} step: {step_text!r}")
            step = int(step_text)
        if base == "*":
            start, stop = lo, hi
        elif "-" in base:
            first, last = base.split("-")
            start, stop = _parse_value(first, field), _parse_value(last, field)
            if start > stop:
                raise ValueError(f"invalid {name} range: {base!r}")
        else:
            start = _parse_value(base, field)
            stop = hi if step_text is not None else start
        values.update(range(start, stop + 1, step))
    return values


def _parse(expr):
    if not isinstance(expr, str):
        raise TypeError(f"expr must be str, not {type(expr).__name__}")
    expr = expr.strip()
    if expr.startswith("@"):
        if expr.lower() not in _SHORTCUTS:
            raise ValueError(f"unknown shortcut: {expr!r}")
        expr = _SHORTCUTS[expr.lower()]
    parts = re.split(r"[ \t]+", expr)
    if len(parts) != 5:
        raise ValueError(f"expected 5 fields, got {len(parts)}: {expr!r}")

    minutes, hours, doms, months, dows = (
        _parse_field(text, field) for text, field in zip(parts, _FIELDS))
    # 7 is an alias for Sunday (0)
    dows = {day % 7 for day in dows}
    return (sorted(minutes), sorted(hours), doms, months, dows,
            parts[2] != "*", parts[4] != "*")


def _add_years(dt, years):
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:  # Feb 29 in a non-leap target year
        return dt.replace(year=dt.year + years, day=28)


def next_run(expr, after):
    minutes, hours, doms, months, dows, dom_restricted, dow_restricted = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    deadline = _add_years(after, 5)

    day = start.date()
    while day <= deadline.date():
        dom_ok = day.day in doms
        dow_ok = (day.isoweekday() % 7) in dows
        if dom_restricted and dow_restricted:
            day_ok = dom_ok or dow_ok
        else:
            day_ok = dom_ok and dow_ok
        if day.month in months and day_ok:
            first_minute = start.hour * 60 + start.minute if day == start.date() else 0
            for hour in hours:
                for minute in minutes:
                    if hour * 60 + minute >= first_minute:
                        candidate = datetime(day.year, day.month, day.day, hour, minute)
                        if candidate > deadline:
                            break
                        return candidate
        day += timedelta(days=1)

    raise ValueError(f"no matching time within 5 years of {after}")
