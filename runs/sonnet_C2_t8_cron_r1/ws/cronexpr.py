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


def _value(s, lo, hi, names):
    if s.isascii() and s.isdigit():
        v = int(s)
    elif names and s.upper() in names:
        v = names.index(s.upper()) + lo
    else:
        raise ValueError(f"bad value {s!r}")
    if not lo <= v <= hi:
        raise ValueError(f"{s!r} out of range")
    return v


def _field(text, lo, hi, names=None):
    out = set()
    for item in text.split(","):
        base, sep, step = item.partition("/")
        if sep:
            if not (step.isascii() and step.isdigit() and int(step) >= 1):
                raise ValueError(f"bad step in {item!r}")
            step = int(step)
        else:
            step = 1
        if base == "*":
            a, b = lo, (6 if hi == 7 else hi)  # dow: 7 is just Sunday again
        elif "-" in base:
            x, _, y = base.partition("-")
            a, b = _value(x, lo, hi, names), _value(y, lo, hi, names)
            if a > b:
                raise ValueError(f"descending range {item!r}")
        else:
            a = _value(base, lo, hi, names)
            b = hi if sep else a
        out.update(range(a, b + 1, step))
    return out


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be str")
    expr = expr.strip(" \t")
    expr = _SHORTCUTS.get(expr.lower(), expr)
    parts = re.split(r"[ \t]+", expr)
    if len(parts) != 5:
        raise ValueError("expected 5 fields")
    mins = sorted(_field(parts[0], 0, 59))
    hours = sorted(_field(parts[1], 0, 23))
    doms = _field(parts[2], 1, 31)
    months = _field(parts[3], 1, 12, _MONTHS)
    dows = {d % 7 for d in _field(parts[4], 0, 7, _DAYS)}
    dom_r, dow_r = parts[2] != "*", parts[4] != "*"

    def day_ok(d):
        if d.month not in months:
            return False
        a, b = d.day in doms, (d.weekday() + 1) % 7 in dows
        return (a or b) if dom_r and dow_r else a if dom_r else b if dow_r else True

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        limit = after.replace(year=after.year + 5, day=28)
    day = start.replace(hour=0, minute=0)
    while day <= limit:
        if day_ok(day):
            for h in hours:
                for m in mins:
                    c = day.replace(hour=h, minute=m)
                    if start <= c <= limit:
                        return c
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")


if __name__ == "__main__":
    D = datetime
    assert next_run("*/15 * * * *", D(2026, 3, 4, 10, 7)) == D(2026, 3, 4, 10, 15)
    assert next_run("0 9 * * MON-FRI", D(2026, 3, 6, 9, 0)) == D(2026, 3, 9, 9, 0)
    assert next_run("0 0 29 2 *", D(2026, 3, 1)) == D(2028, 2, 29)
    assert next_run("30 4 1,15 * 5", D(2026, 1, 1, 5, 0)) == D(2026, 1, 2, 4, 30)
    assert next_run("@HOURLY", D(2026, 1, 1, 0, 0, 30)) == D(2026, 1, 1, 1, 0)
    assert next_run("0 0 * * 5-7", D(2026, 3, 7, 12)) == D(2026, 3, 8)
    for bad in ["0 0 30 2 *", "FRI-MON * * * *", "* * * * * *", "*/0 * * * *", "1,,2 * * * *", "* * * MON *"]:
        try:
            next_run(bad, D(2026, 1, 1))
            raise AssertionError(bad)
        except ValueError:
            pass
