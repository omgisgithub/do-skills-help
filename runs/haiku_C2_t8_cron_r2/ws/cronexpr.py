"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, time, timedelta

SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
MONTHS = {n: i for i, n in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
DAYS = {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())}
# (min, max, names) for minute, hour, day of month, month, day of week
FIELDS = [(0, 59, {}), (0, 23, {}), (1, 31, {}), (1, 12, MONTHS), (0, 7, DAYS)]


def _value(tok, lo, hi, names):
    if re.fullmatch(r"[0-9]+", tok):
        n = int(tok)
    elif tok.upper() in names:
        n = names[tok.upper()]
    else:
        raise ValueError(f"bad value {tok!r}")
    if not lo <= n <= hi:
        raise ValueError(f"{n} out of range {lo}-{hi}")
    return n


def _item(item, lo, hi, names):
    body, slash, step_s = item.partition("/")
    if slash and not (re.fullmatch(r"[0-9]+", step_s) and int(step_s) >= 1):
        raise ValueError(f"bad step {step_s!r}")
    step = int(step_s) if slash else 1
    if body == "*":
        start, end = lo, hi
    elif "-" in body:
        a, _, b = body.partition("-")
        start, end = _value(a, lo, hi, names), _value(b, lo, hi, names)
        if start > end:
            raise ValueError(f"range {body!r} runs backwards")
    else:
        start = _value(body, lo, hi, names)
        end = hi if slash else start
    return range(start, end + 1, step)


def _parse(expr):
    fields = re.split(r"[ \t]+", expr.strip())
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}")
    parsed = []
    for text, (lo, hi, names) in zip(fields, FIELDS):
        vals = set()
        for item in text.split(","):
            vals.update(_item(item, lo, hi, names))
        parsed.append((vals, text != "*"))
    return parsed


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError(f"expr must be str, not {type(expr).__name__}")
    key = expr.strip().lower()
    if key in SHORTCUTS:
        expr = SHORTCUTS[key]
    (minutes, _), (hours, _), (doms, dom_r), (months, _), (dows, dow_r) = _parse(expr)
    dows = {d % 7 for d in dows}  # 7 is Sunday, same as 0
    limit = after + timedelta(days=5 * 365 + 1)  # 5 years, counted in days
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    day = start.date()
    while day <= limit.date():
        dom_ok = day.day in doms
        dow_ok = (day.weekday() + 1) % 7 in dows  # Python Monday=0, cron Sunday=0
        ok = (dom_ok or dow_ok) if dom_r and dow_r else (dom_ok and dow_ok)
        if ok and day.month in months:
            for h in sorted(hours):
                for m in sorted(minutes):
                    c = datetime.combine(day, time(h, m))
                    if c >= start:
                        if c > limit:
                            raise ValueError(f"no matching minute within 5 years of {after}")
                        return c
        day += timedelta(days=1)
    raise ValueError(f"no matching minute within 5 years of {after}")
