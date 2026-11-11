"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_MONTHS = {n: i + 1 for i, n in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
_DAYS = {n: i for i, n in enumerate("SUN MON TUE WED THU FRI SAT".split())}
# (min, max, names)
_FIELDS = [(0, 59, {}), (0, 23, {}), (1, 31, {}), (1, 12, _MONTHS), (0, 7, _DAYS)]


def _value(tok, lo, hi, names):
    if re.fullmatch(r"[0-9]+", tok):
        v = int(tok)
    elif tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("bad value %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("value out of range: %r" % tok)
    return v


def _parse_field(text, lo, hi, names):
    out = set()
    for item in text.split(","):
        base, sep, step = item.partition("/")
        if sep:
            if not re.fullmatch(r"[0-9]+", step) or int(step) < 1:
                raise ValueError("bad step %r" % item)
            step = int(step)
        else:
            step = None
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            x, _, y = base.partition("-")
            a, b = _value(x, lo, hi, names), _value(y, lo, hi, names)
            if a > b:
                raise ValueError("bad range %r" % item)
        else:
            a = _value(base, lo, hi, names)
            b = hi if step else a
        out.update(range(a, b + 1, step or 1))
    return out


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be str")
    expr = expr.strip(" \t")
    expr = _SHORTCUTS.get(expr.lower(), expr)
    parts = re.split(r"[ \t]+", expr)
    if len(parts) != 5:
        raise ValueError("need 5 fields")
    minutes, hours, doms, months, dows = (
        _parse_field(p, *f) for p, f in zip(parts, _FIELDS))
    dows = {d % 7 for d in dows}
    dom_r, dow_r = parts[2] != "*", parts[4] != "*"

    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    try:
        end = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29
        end = after.replace(year=after.year + 5, day=28) + timedelta(days=1)
    mins = sorted(h * 60 + m for h in hours for m in minutes)
    day = start.replace(hour=0, minute=0)
    while day <= end:
        if day.month in months:
            dom_ok, dow_ok = day.day in doms, (day.weekday() + 1) % 7 in dows
            ok = (dom_ok or dow_ok) if dom_r and dow_r else dom_ok if dom_r else dow_ok if dow_r else True
            if ok:
                for t in mins:
                    cand = day + timedelta(minutes=t)
                    if cand >= start:
                        if cand > end:
                            break
                        return cand
        day += timedelta(days=1)
    raise ValueError("no matching time within 5 years")


if __name__ == "__main__":
    d = datetime
    assert next_run("*/15 * * * *", d(2026, 3, 4, 10, 7)) == d(2026, 3, 4, 10, 15)
    assert next_run("0 9 * * MON-FRI", d(2026, 3, 6, 9, 0)) == d(2026, 3, 9, 9, 0)
    assert next_run("0 0 29 2 *", d(2026, 3, 1)) == d(2028, 2, 29)
    assert next_run("30 4 1,15 * 5", d(2026, 1, 1, 5, 0)) == d(2026, 1, 2, 4, 30)
    assert next_run("@hourly", d(2026, 1, 1, 0, 0, 30)) == d(2026, 1, 1, 1, 0)
    assert next_run("0 0 * * 5-7", d(2026, 3, 4)) == d(2026, 3, 6)
    for bad in ["0 0 30 2 *", "* * * *", "FRI-MON * * * *", "*/0 * * * *", "* * * * JAN", "1,,2 * * * *"]:
        try:
            next_run(bad, d(2026, 1, 1))
        except ValueError:
            continue
        raise AssertionError(bad)
    try:
        next_run(1, d(2026, 1, 1))
    except TypeError:
        pass
