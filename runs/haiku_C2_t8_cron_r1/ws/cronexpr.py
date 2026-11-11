"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
          "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
DAYS = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}


def _value(text, lo, hi, names):
    if re.fullmatch(r"[0-9]+", text):
        value = int(text)
    elif text.upper() in names:
        value = names[text.upper()]
    else:
        raise ValueError(f"bad value {text!r}")
    if not lo <= value <= hi:
        raise ValueError(f"value {value} outside {lo}-{hi}")
    return value


def _field(text, lo, hi, names={}):
    values = set()
    for item in text.split(","):
        base, slash, step_text = item.partition("/")
        if slash and not (re.fullmatch(r"[0-9]+", step_text) and int(step_text) >= 1):
            raise ValueError(f"bad step in {item!r}")
        step = int(step_text) if slash else 1
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            first, _, last = base.partition("-")
            start, end = _value(first, lo, hi, names), _value(last, lo, hi, names)
            if start > end:
                raise ValueError(f"range {base!r} runs backwards")
        else:
            start = _value(base, lo, hi, names)
            end = hi if slash else start
        values.update(range(start, end + 1, step))
    return values


def _day_ok(t, doms, dows, dom_restricted, dow_restricted):
    dom_ok = t.day in doms
    dow_ok = (t.weekday() + 1) % 7 in dows  # Python Monday=0, cron Sunday=0
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    expr = SHORTCUTS.get(expr.strip().lower(), expr)
    fields = re.split(r"[ \t]+", expr.strip())
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}")
    minute, hour, dom, month, dow = fields

    minutes = _field(minute, 0, 59)
    hours = _field(hour, 0, 23)
    doms = _field(dom, 1, 31)
    months = _field(month, 1, 12, MONTHS)
    dows = {d % 7 for d in _field(dow, 0, 7, DAYS)}  # 7 is Sunday too

    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29 has no counterpart five years on
        limit = after.replace(year=after.year + 5, month=3, day=1)

    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while t <= limit:
        if t.month not in months:
            t = (t.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
        elif not _day_ok(t, doms, dows, dom != "*", dow != "*"):
            t = t.replace(hour=0, minute=0) + timedelta(days=1)
        elif t.hour not in hours:
            t = t.replace(minute=0) + timedelta(hours=1)
        elif t.minute not in minutes:
            t += timedelta(minutes=1)
        else:
            return t
    raise ValueError(f"no matching minute within 5 years of {after}")
