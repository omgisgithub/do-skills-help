"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta


# (lo, hi, names) per field: minute, hour, day of month, month, day of week
_FIELDS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
             "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}),
    (0, 7, {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}),
]

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _parse_value(token, lo, hi, names):
    if re.fullmatch(r"[0-9]+", token):
        value = int(token)
    elif names and token.upper() in names:
        value = names[token.upper()]
    else:
        raise ValueError("invalid value: %r" % token)
    if not lo <= value <= hi:
        raise ValueError("value out of range: %r" % token)
    return value


def _parse_item(item, lo, hi, names):
    base, sep, step_text = item.partition("/")
    if sep:
        if not re.fullmatch(r"[0-9]+", step_text) or int(step_text) < 1:
            raise ValueError("invalid step: %r" % item)
        step = int(step_text)
    else:
        step = 1

    if base == "*":
        start, end = lo, hi
    elif "-" in base:
        a, dash, b = base.partition("-")
        if not dash or "-" in b:
            raise ValueError("invalid range: %r" % item)
        start = _parse_value(a, lo, hi, names)
        end = _parse_value(b, lo, hi, names)
        if start > end:
            raise ValueError("reversed range: %r" % item)
    else:
        start = _parse_value(base, lo, hi, names)
        # N/S runs from N up to the field maximum
        end = hi if sep else start
    return range(start, end + 1, step)


def _parse_field(text, lo, hi, names):
    values = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty item in field: %r" % text)
        values.update(_parse_item(item, lo, hi, names))
    return values


def _add_years(dt, years):
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:  # Feb 29 in a non-leap target year
        return dt.replace(year=dt.year + years, day=28)


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be str, not %s" % type(expr).__name__)

    text = expr.strip()
    text = _SHORTCUTS.get(text.lower(), text)
    parts = re.split(r"[ \t]+", text)
    if len(parts) != 5:
        raise ValueError("expected 5 fields: %r" % expr)

    sets = []
    for part, (lo, hi, names) in zip(parts, _FIELDS):
        sets.append(_parse_field(part, lo, hi, names))
    # 0 and 7 are both Sunday
    sets[4] = {0 if v == 7 else v for v in sets[4]}
    minutes, hours, doms, months, dows = sets

    dom_restricted = parts[2] != "*"
    dow_restricted = parts[4] != "*"

    def day_matches(day):
        if day.month not in months:
            return False
        dom_ok = day.day in doms
        dow_ok = (day.isoweekday() % 7) in dows
        if dom_restricted and dow_restricted:
            return dom_ok or dow_ok
        return dom_ok and dow_ok

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _add_years(after, 5)

    day = start.replace(hour=0, minute=0)
    while day.date() <= limit.date():
        if day_matches(day):
            for hour in sorted(hours):
                for minute in sorted(minutes):
                    candidate = day.replace(hour=hour, minute=minute)
                    if candidate < start:
                        continue
                    if candidate > limit:
                        raise ValueError("no matching time within 5 years")
                    return candidate
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")
