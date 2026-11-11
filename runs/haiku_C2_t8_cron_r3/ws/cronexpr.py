"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, time, timedelta

MONTHS = {m: i for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
WEEKDAYS = {d: i for i, d in enumerate("SUN MON TUE WED THU FRI SAT".split())}
# (min, max, names) per field; day of week goes to 7 so "7" is valid and folds to Sunday
FIELDS = [(0, 59, {}), (0, 23, {}), (1, 31, {}), (1, 12, MONTHS), (0, 7, WEEKDAYS)]
SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@hourly": "0 * * * *",
}
ITEM = re.compile(r"(\*|[0-9A-Za-z]+)(?:-([0-9A-Za-z]+))?(?:/([0-9]+))?")


def _value(tok, lo, hi, names):
    v = int(tok) if tok.isdigit() else names.get(tok.upper())
    if v is None or not lo <= v <= hi:
        raise ValueError(f"bad cron value {tok!r}")
    return v


def _parse_field(text, lo, hi, names):
    values = set()
    for item in text.split(","):
        m = ITEM.fullmatch(item)
        if not m:
            raise ValueError(f"bad cron item {item!r}")
        a_tok, b_tok, s_tok = m.groups()
        step = int(s_tok) if s_tok is not None else 1
        if step < 1:
            raise ValueError(f"bad cron step in {item!r}")
        if a_tok == "*":
            if b_tok is not None:
                raise ValueError(f"bad cron range {item!r}")
            a, b = lo, hi
        else:
            a = _value(a_tok, lo, hi, names)
            if b_tok is not None:
                b = _value(b_tok, lo, hi, names)
                if a > b:
                    raise ValueError(f"reversed cron range {item!r}")
            else:
                b = hi if s_tok is not None else a
        values.update(range(a, b + 1, step))
    return values


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    expr = SHORTCUTS.get(expr.strip().lower(), expr)
    fields = re.split(r"[ \t]+", expr.strip())
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}: {expr!r}")
    minutes, hours, doms, months, dows = (_parse_field(f, *spec) for f, spec in zip(fields, FIELDS))
    dows = {d % 7 for d in dows}
    dom_restricted, dow_restricted = fields[2] != "*", fields[4] != "*"

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29 plus five years
        limit = after.replace(year=after.year + 5, day=28)

    day = start.date()
    while day <= limit.date():
        dom_ok = day.day in doms
        dow_ok = (day.weekday() + 1) % 7 in dows
        # Standard cron: when both day fields are restricted, either one may match
        day_ok = (dom_ok or dow_ok) if dom_restricted and dow_restricted else (dom_ok and dow_ok)
        if day.month in months and day_ok:
            for h in sorted(hours):
                for m in sorted(minutes):
                    cand = datetime.combine(day, time(h, m))
                    if start <= cand <= limit:
                        return cand
        day += timedelta(days=1)
    raise ValueError(f"no matching time within 5 years after {after}")
