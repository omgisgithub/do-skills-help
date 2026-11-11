"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
# (min, max, names -> value offset)
_FIELDS = [(0, 59, None), (0, 23, None), (1, 31, None), (1, 12, _MONTHS), (0, 7, _DAYS)]
_ITEM = re.compile(r"([A-Za-z0-9*]+)(?:-([A-Za-z0-9]+))?(?:/([0-9]+))?", re.ASCII)


def _value(tok, lo, hi, names):
    if re.fullmatch(r"[0-9]+", tok, re.ASCII):
        v = int(tok)
    elif names and tok.upper() in names:
        v = names.index(tok.upper()) + (1 if names is _MONTHS else 0)
    else:
        raise ValueError("bad value %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range %r" % tok)
    return v


def _parse_field(text, lo, hi, names):
    out = set()
    for item in text.split(","):
        m = _ITEM.fullmatch(item)
        if not m:
            raise ValueError("bad item %r" % item)
        a, b, s = m.groups()
        step = int(s) if s is not None else None
        if step == 0:
            raise ValueError("step 0")
        if a == "*":
            if b is not None:
                raise ValueError("bad range")
            start, end = lo, hi
        else:
            start = _value(a, lo, hi, names)
            if b is not None:
                end = _value(b, lo, hi, names)
                if start > end:
                    raise ValueError("bad range")
            else:
                end = hi if step else start
        out.update(range(start, end + 1, step or 1))
    return out


def _parse(expr):
    expr = expr.strip(" \t")
    expr = _SHORTCUTS.get(expr.lower(), expr)
    parts = re.split(r"[ \t]+", expr)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    sets = [_parse_field(p, *f) for p, f in zip(parts, _FIELDS)]
    sets[4] = {v % 7 for v in sets[4]}
    return sets, parts[2] != "*", parts[4] != "*"


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be str")
    (mins, hours, doms, months, dows), dom_r, dow_r = _parse(expr)
    mins, hours = sorted(mins), sorted(hours)
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28) + timedelta(days=1)
    day = start.date()
    while day <= limit.date():
        dom_ok, dow_ok = day.day in doms, (day.weekday() + 1) % 7 in dows
        ok = (dom_ok or dow_ok) if dom_r and dow_r else dom_ok if dom_r else dow_ok if dow_r else True
        if day.month in months and ok:
            for h in hours:
                for m in mins:
                    t = datetime(day.year, day.month, day.day, h, m)
                    if t >= start:
                        if t > limit:
                            raise ValueError("no match within 5 years")
                        return t
        day += timedelta(days=1)
    raise ValueError("no match within 5 years")


if __name__ == "__main__":
    D = datetime
    assert next_run("*/15 * * * *", D(2026, 3, 4, 10, 7)) == D(2026, 3, 4, 10, 15)
    assert next_run("0 9 * * MON-FRI", D(2026, 3, 6, 9, 0)) == D(2026, 3, 9, 9, 0)
    assert next_run("0 0 29 2 *", D(2026, 3, 1)) == D(2028, 2, 29)
    assert next_run("30 4 1,15 * 5", D(2026, 1, 1, 5, 0)) == D(2026, 1, 2, 4, 30)
    assert next_run("@HOURLY", D(2026, 1, 1, 0, 0, 30)) == D(2026, 1, 1, 1, 0)
    assert next_run("0 0 * * 5-7", D(2026, 3, 2)) == D(2026, 3, 6)
    for bad in ["0 0 30 2 *", "* * * *", "*/0 * * * *", "* * * * FRI-MON", "* * * JAN * *", "60 * * * *", "* * * * MON,", "1-*/2 * * * *"]:
        try:
            next_run(bad, D(2026, 1, 1))
        except ValueError:
            continue
        raise AssertionError(bad)
    try:
        next_run(5, D(2026, 1, 1))
    except TypeError:
        pass
    else:
        raise AssertionError
    print("ok")
