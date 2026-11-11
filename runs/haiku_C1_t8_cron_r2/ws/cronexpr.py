"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

MONTH_NAMES = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
               "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
DOW_NAMES = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}

SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

# (low, high, names) for minute, hour, day of month, month, day of week
FIELD_SPECS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, MONTH_NAMES),
    (0, 7, DOW_NAMES),
]


def _parse_value(token, low, high, names):
    if re.fullmatch(r"[0-9]+", token):
        value = int(token)
    elif token.upper() in names:
        value = names[token.upper()]
    else:
        raise ValueError(f"invalid cron value: {token!r}")
    if not low <= value <= high:
        raise ValueError(f"cron value out of range: {token!r}")
    return value


def _parse_field(text, low, high, names):
    values = set()
    for item in text.split(","):
        spec, has_step, step_text = item.partition("/")
        if has_step:
            if not re.fullmatch(r"[0-9]+", step_text) or int(step_text) < 1:
                raise ValueError(f"invalid cron step: {item!r}")
            step = int(step_text)
        else:
            step = 1

        if spec == "*":
            first, last = low, high
        elif "-" in spec:
            left, _, right = spec.partition("-")
            first = _parse_value(left, low, high, names)
            last = _parse_value(right, low, high, names)
            if first > last:
                raise ValueError(f"cron range must be ascending: {item!r}")
        else:
            first = _parse_value(spec, low, high, names)
            last = high if has_step else first

        values.update(range(first, last + 1, step))
    return values


def _parse(expr):
    text = expr.strip()
    if text.startswith("@"):
        if text.lower() not in SHORTCUTS:
            raise ValueError(f"unknown cron shortcut: {text!r}")
        text = SHORTCUTS[text.lower()]

    fields = re.split(r"[ \t]+", text)
    if len(fields) != 5:
        raise ValueError(f"cron expression needs 5 fields: {expr!r}")

    parsed = [_parse_field(field, low, high, names)
              for field, (low, high, names) in zip(fields, FIELD_SPECS)]
    minutes, hours, days, months, dows = parsed
    dows = {value % 7 for value in dows}  # 7 is Sunday, same as 0
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"
    return minutes, hours, days, months, dows, dom_restricted, dow_restricted


def _day_matches(day, spec):
    _, _, days, _, dows, dom_restricted, dow_restricted = spec
    dom_match = day.day in days
    dow_match = (day.weekday() + 1) % 7 in dows  # Python Monday=0, cron Sunday=0
    if dom_restricted and dow_restricted:
        return dom_match or dow_match
    return dom_match and dow_match


def _limit_after(after):
    try:
        return after.replace(year=after.year + 5)
    except ValueError:  # Feb 29 -> Feb 28 in the target year
        return after.replace(year=after.year + 5, day=28)


def next_run(expr: str, after: datetime) -> datetime:
    if not isinstance(expr, str):
        raise TypeError("cron expression must be a str")

    spec = _parse(expr)
    minutes, hours, _, months, _, _, _ = spec

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _limit_after(after)

    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day.month in months and _day_matches(day, spec):
            for hour in sorted(hours):
                for minute in sorted(minutes):
                    candidate = day.replace(hour=hour, minute=minute)
                    if candidate >= start:
                        if candidate > limit:
                            break
                        return candidate
        day += timedelta(days=1)

    raise ValueError(f"no matching time within 5 years for {expr!r}")
