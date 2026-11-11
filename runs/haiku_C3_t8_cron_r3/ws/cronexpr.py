"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

MONTH_NAMES = {name: i for i, name in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
DOW_NAMES = {name: i for i, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])}

# (minimum, maximum, names) for minute, hour, day of month, month, day of week
FIELDS = (
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, MONTH_NAMES),
    (0, 7, DOW_NAMES),
)

SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def _parse_value(token, low, high, names):
    if token.upper() in names:
        return names[token.upper()]
    if not re.fullmatch(r"[0-9]+", token):
        raise ValueError(f"invalid cron value: {token!r}")
    value = int(token)
    if not low <= value <= high:
        raise ValueError(f"cron value out of range: {token!r}")
    return value


def _parse_field(text, low, high, names):
    values = set()
    for item in text.split(","):
        base, slash, step_text = item.partition("/")
        step = 1
        if slash:
            if not re.fullmatch(r"[0-9]+", step_text) or int(step_text) < 1:
                raise ValueError(f"invalid cron step: {item!r}")
            step = int(step_text)
        if base == "*":
            start, stop = low, high
        elif "-" in base:
            first, _, last = base.partition("-")
            start = _parse_value(first, low, high, names)
            stop = _parse_value(last, low, high, names)
            if start > stop:
                raise ValueError(f"cron range must be ascending: {item!r}")
        else:
            start = _parse_value(base, low, high, names)
            stop = high if slash else start
        values.update(range(start, stop + 1, step))
    return values


def _parse(expr):
    parts = re.split(r"[ \t]+", expr.strip())
    if len(parts) != 5:
        raise ValueError(f"cron expression needs 5 fields: {expr!r}")
    # Each field is (restricted, values); restricted means the field is not exactly "*".
    fields = []
    for text, (low, high, names) in zip(parts, FIELDS):
        fields.append((text != "*", _parse_field(text, low, high, names)))
    # 0 and 7 are both Sunday, so fold day-of-week values into 0-6.
    dow_restricted, dow_values = fields[4]
    fields[4] = (dow_restricted, {value % 7 for value in dow_values})
    return fields


def _day_matches(t, dom_restricted, dom_values, dow_restricted, dow_values):
    in_dom = t.day in dom_values
    in_dow = t.isoweekday() % 7 in dow_values
    if dom_restricted and dow_restricted:
        return in_dom or in_dow
    return in_dom and in_dow


def _horizon(after):
    if after.year + 5 > datetime.max.year:
        return datetime.max
    try:
        return after.replace(year=after.year + 5)
    except ValueError:  # Feb 29 with a non-leap target year
        return after.replace(year=after.year + 5, month=3, day=1)


def next_run(expr: str, after: datetime) -> datetime:
    if not isinstance(expr, str):
        raise TypeError("cron expression must be a str")
    key = expr.strip().lower()
    if key.startswith("@"):
        if key not in SHORTCUTS:
            raise ValueError(f"unknown cron shortcut: {expr!r}")
        expr = SHORTCUTS[key]

    (minute_r, minutes), (hour_r, hours), (dom_r, doms), (month_r, months), (dow_r, dows) = _parse(expr)
    horizon = _horizon(after)
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        while t <= horizon:
            if t.month not in months:
                t = datetime(t.year + (t.month == 12), t.month % 12 + 1, 1)
            elif not _day_matches(t, dom_r, doms, dow_r, dows):
                t = datetime(t.year, t.month, t.day) + timedelta(days=1)
            elif t.hour not in hours:
                t = t.replace(minute=0) + timedelta(hours=1)
            elif t.minute not in minutes:
                t += timedelta(minutes=1)
            else:
                return t
    except (OverflowError, ValueError):  # stepped past datetime.max
        pass
    raise ValueError(f"no matching minute within 5 years of {after}")
