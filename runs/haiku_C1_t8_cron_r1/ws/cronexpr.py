"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTH_NAMES = {name: i for i, name in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
_DOW_NAMES = {name: i for i, name in enumerate(
    ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])}

# (min, max, names) for minute, hour, day of month, month, day of week
_FIELDS = (
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, _MONTH_NAMES),
    (0, 7, _DOW_NAMES),
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

_VALUE = r"[A-Za-z]+|[0-9]+"
_ITEM = re.compile(
    rf"(?:(?P<star>\*)|(?P<a>{_VALUE})(?:-(?P<b>{_VALUE}))?)(?:/(?P<step>[0-9]+))?")


def _value(token, lo, hi, names):
    if token.isdigit():
        value = int(token)
    else:
        value = names.get(token.upper())
        if value is None:
            raise ValueError(f"unknown name: {token!r}")
    if not lo <= value <= hi:
        raise ValueError(f"value out of range: {token!r}")
    return value


def _parse_field(text, lo, hi, names):
    values = set()
    for item in text.split(","):
        m = _ITEM.fullmatch(item)
        if m is None:
            raise ValueError(f"invalid item: {item!r}")
        has_step = m.group("step") is not None
        step = int(m.group("step")) if has_step else 1
        if step < 1:
            raise ValueError(f"step must be >= 1: {item!r}")
        if m.group("star"):
            start, end = lo, hi
        else:
            start = _value(m.group("a"), lo, hi, names)
            if m.group("b") is not None:
                end = _value(m.group("b"), lo, hi, names)
                if start > end:
                    raise ValueError(f"range start after end: {item!r}")
            else:
                end = hi if has_step else start
        values.update(range(start, end + 1, step))
    return values


def _compile(expr):
    if not isinstance(expr, str):
        raise TypeError(f"expr must be str, not {type(expr).__name__}")
    expr = _SHORTCUTS.get(expr.strip().lower(), expr)
    texts = re.split(r"[ \t]+", expr.strip())
    if len(texts) != 5:
        raise ValueError(f"expected 5 fields, got {len(texts)}: {expr!r}")
    minutes, hours, doms, months, dows = (
        _parse_field(text, lo, hi, names)
        for text, (lo, hi, names) in zip(texts, _FIELDS))
    dows = {d % 7 for d in dows}  # 7 is Sunday, same as 0
    dom_restricted = texts[2] != "*"
    dow_restricted = texts[4] != "*"
    return minutes, hours, doms, months, dows, dom_restricted, dow_restricted


def _limit(after):
    # Five calendar years after `after`; Feb 29 falls back to Feb 28 in a non-leap year.
    try:
        return after.replace(year=after.year + 5)
    except ValueError:
        if after.year + 5 > datetime.max.year:
            return datetime.max
        return after.replace(year=after.year + 5, day=28)


def next_run(expr, after):
    minutes, hours, doms, months, dows, dom_restricted, dow_restricted = _compile(expr)
    try:
        limit = _limit(after)
        t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        while t <= limit:
            dom_ok = t.day in doms
            dow_ok = (t.weekday() + 1) % 7 in dows
            if dom_restricted and dow_restricted:
                day_ok = dom_ok or dow_ok
            else:
                day_ok = dom_ok and dow_ok

            if t.month not in months:
                t = datetime(t.year + (t.month == 12), t.month % 12 + 1, 1)
            elif not day_ok:
                t = datetime(t.year, t.month, t.day) + timedelta(days=1)
            elif t.hour not in hours:
                t = t.replace(minute=0) + timedelta(hours=1)
            elif t.minute not in minutes:
                t += timedelta(minutes=1)
            else:
                return t
    except (OverflowError, ValueError):
        pass  # ran past datetime.max
    raise ValueError(f"no matching time within 5 years after {after}: {expr!r}")
