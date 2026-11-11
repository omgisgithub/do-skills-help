"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, time, timedelta

_MONTHS = {name: i for i, name in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
_DAYS = {name: i for i, name in enumerate(
    ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])}

# (low, high, names) for minute, hour, day of month, month, day of week
_FIELDS = [
    (0, 59, {}),
    (0, 23, {}),
    (1, 31, {}),
    (1, 12, _MONTHS),
    (0, 7, _DAYS),
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

_VALUE = r"(?:[0-9]+|[A-Za-z]{3})"
_STAR_ITEM = re.compile(r"\*(?:/([0-9]+))?")
_RANGE_ITEM = re.compile(r"(%s)(?:-(%s))?(?:/([0-9]+))?" % (_VALUE, _VALUE))


def _value(text, names, low, high):
    if re.fullmatch(r"[0-9]+", text):
        n = int(text)
    else:
        n = names.get(text.upper())
        if n is None:
            raise ValueError("invalid name: %r" % text)
    if not low <= n <= high:
        raise ValueError("value out of range: %r" % text)
    return n


def _parse_field(text, low, high, names):
    values = set()
    for item in text.split(","):
        star = _STAR_ITEM.fullmatch(item)
        if star:
            start, stop, step = low, high, star.group(1)
        else:
            m = _RANGE_ITEM.fullmatch(item)
            if not m:
                raise ValueError("invalid item: %r" % item)
            start = _value(m.group(1), names, low, high)
            if m.group(2) is not None:
                stop = _value(m.group(2), names, low, high)
                if start > stop:
                    raise ValueError("range end before start: %r" % item)
            elif m.group(3) is not None:
                stop = high  # N/S runs up to the field maximum
            else:
                stop = start
            step = m.group(3)
        step = 1 if step is None else int(step)
        if step < 1:
            raise ValueError("step must be >= 1: %r" % item)
        values.update(range(start, stop + 1, step))
    return values


def _parse(expr):
    if not isinstance(expr, str):
        raise TypeError("expr must be str")
    text = expr.strip()
    text = _SHORTCUTS.get(text.lower(), text)
    fields = re.split(r"[ \t]+", text)
    if len(fields) != 5:
        raise ValueError("expected 5 fields: %r" % expr)
    sets = []
    for i, (text_field, (low, high, names)) in enumerate(zip(fields, _FIELDS)):
        values = _parse_field(text_field, low, high, names)
        if i == 4:
            values = {v % 7 for v in values}  # 7 is Sunday, same as 0
        sets.append(sorted(values))
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"
    return sets, dom_restricted, dow_restricted


def _day_matches(day, doms, dows, dom_restricted, dow_restricted):
    dom_ok = day.day in doms
    dow_ok = day.isoweekday() % 7 in dows  # Sunday -> 0
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    # An unrestricted field is "*", which covers every value, so AND is safe.
    return dom_ok and dow_ok


def _five_years_later(dt):
    try:
        return dt.replace(year=dt.year + 5)
    except ValueError:  # Feb 29
        return dt.replace(year=dt.year + 5, day=28)


def next_run(expr, after):
    (minutes, hours, doms, months, dows), dom_r, dow_r = _parse(expr)
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    deadline = _five_years_later(after)
    month_set = set(months)

    day = start.date()
    while day <= deadline.date():
        if day.month in month_set and _day_matches(day, doms, dows, dom_r, dow_r):
            for hour in hours:
                for minute in minutes:
                    cand = datetime.combine(day, time(hour, minute))
                    if cand >= start:
                        if cand > deadline:
                            break
                        return cand
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years of %s" % after)
