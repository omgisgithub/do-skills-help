"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from collections import namedtuple
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
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)
}
_DOW_NAMES = {
    name: number
    for number, name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])
}

# (low, high, names) per field, in expression order.
_FIELDS = (
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, _MONTH_NAMES),
    (0, 7, _DOW_NAMES),
)


def _item_pattern(names):
    # Groups: "*" marker, range start, range end, step.
    value = "(?:[0-9]+|" + "|".join(names) + ")" if names else "[0-9]+"
    return re.compile(
        r"(?:(\*)|(" + value + r")(?:-(" + value + r"))?)(?:/([0-9]+))?",
        re.ASCII | re.IGNORECASE,
    )


_ITEM_PATTERNS = tuple(_item_pattern(names) for _, _, names in _FIELDS)

_Spec = namedtuple(
    "_Spec", "minutes hours doms months dows dom_restricted dow_restricted")


def _value(token, low, high, names):
    if token.upper() in names:
        number = names[token.upper()]
    else:
        number = int(token)
    if not low <= number <= high:
        raise ValueError("value out of range: %r" % token)
    return number


def _parse_field(text, low, high, names, pattern):
    values = set()
    for item in text.split(","):
        match = pattern.fullmatch(item)
        if match is None:
            raise ValueError("invalid item: %r" % item)
        star, first, last, step_text = match.groups()
        step = 1
        if step_text is not None:
            step = int(step_text)
            if step < 1:
                raise ValueError("step must be >= 1: %r" % item)
        if star:
            lo, hi = low, high
        else:
            lo = _value(first, low, high, names)
            if last is not None:
                hi = _value(last, low, high, names)
                if lo > hi:
                    raise ValueError("range start after end: %r" % item)
            elif step_text is not None:
                hi = high
            else:
                hi = lo
        values.update(range(lo, hi + 1, step))
    return values


def _parse(expr):
    text = expr.strip()
    if text.startswith("@"):
        key = text.lower() if text.isascii() else ""
        if key not in _SHORTCUTS:
            raise ValueError("unknown shortcut: %r" % expr)
        text = _SHORTCUTS[key]
    fields = re.split(r"[ \t]+", text)
    if len(fields) != 5:
        raise ValueError("expected 5 fields, got %d" % len(fields))

    values = []
    for field, (low, high, names), pattern in zip(fields, _FIELDS, _ITEM_PATTERNS):
        values.append(_parse_field(field, low, high, names, pattern))

    minutes, hours, doms, months, dows = values
    # 0 and 7 are both Sunday; isoweekday() % 7 maps Sunday to 0.
    dows = {day % 7 for day in dows}
    return _Spec(
        minutes=sorted(minutes),
        hours=sorted(hours),
        doms=doms,
        months=months,
        dows=dows,
        dom_restricted=fields[2] != "*",
        dow_restricted=fields[4] != "*",
    )


def _day_matches(spec, day):
    if day.month not in spec.months:
        return False
    dom_hit = day.day in spec.doms
    dow_hit = day.isoweekday() % 7 in spec.dows
    if spec.dom_restricted and spec.dow_restricted:
        return dom_hit or dow_hit
    return dom_hit and dow_hit


def _years_later(moment, years):
    try:
        return moment.replace(year=moment.year + years)
    except ValueError:  # Feb 29 in a non-leap target year
        return moment.replace(year=moment.year + years, day=28)


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be str, not %s" % type(expr).__name__)
    spec = _parse(expr)

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = _years_later(after, 5)
    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if _day_matches(spec, day):
            for hour in spec.hours:
                for minute in spec.minutes:
                    candidate = day.replace(hour=hour, minute=minute)
                    if start <= candidate <= limit:
                        return candidate
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years of %s" % after)
