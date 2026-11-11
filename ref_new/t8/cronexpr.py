"""Reference solution for t8_cron (hidden from agents)."""
import re
from datetime import datetime, timedelta

MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
DOWS = {d: i for i, d in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"])}
FIELDS = [(0, 59, None), (0, 23, None), (1, 31, None), (1, 12, MONTHS), (0, 7, DOWS)]
SHORT = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
         "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
         "@hourly": "0 * * * *"}


def _val(tok, lo, hi, names):
    if re.fullmatch(r"\d+", tok):
        v = int(tok)
    elif names and tok.upper() in names:
        v = names[tok.upper()]
    else:
        raise ValueError("bad value %r" % tok)
    if not lo <= v <= hi:
        raise ValueError("out of range %r" % tok)
    return v


def _field(s, lo, hi, names):
    out = set()
    for item in s.split(","):
        m = re.fullmatch(r"([^/]+)(?:/(\d+))?", item)
        if not m:
            raise ValueError("bad item %r" % item)
        base, step = m.group(1), m.group(2)
        step = int(step) if step is not None else None
        if step == 0:
            raise ValueError("step 0")
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            x, y = base.split("-", 1)
            a, b = _val(x, lo, hi, names), _val(y, lo, hi, names)
            if a > b:
                raise ValueError("reversed range")
        else:
            a = _val(base, lo, hi, names)
            b = hi if step is not None else a
        out.update(range(a, b + 1, step or 1))
    return out


def parse(expr):
    if not isinstance(expr, str):
        raise TypeError("expr must be str")
    e = expr.strip()
    if e.lower() in SHORT:
        e = SHORT[e.lower()]
    parts = e.split()
    if len(parts) != 5:
        raise ValueError("need 5 fields")
    sets = [_field(p, lo, hi, nm) for p, (lo, hi, nm) in zip(parts, FIELDS)]
    dow = {d % 7 for d in sets[4]}
    return sets[0], sets[1], sets[2], sets[3], dow, parts[2] != "*", parts[4] != "*"


def next_run(expr, after):
    mins, hours, doms, months, dows, dom_r, dow_r = parse(expr)
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = after + timedelta(days=5 * 366)

    def day_ok(d):
        a = d.day in doms
        b = (d.isoweekday() % 7) in dows
        if dom_r and dow_r:
            return a or b
        if dom_r:
            return a
        if dow_r:
            return b
        return True

    while t <= limit:
        if t.month not in months or not day_ok(t):
            t = (t + timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if t.hour not in hours:
            t = (t + timedelta(hours=1)).replace(minute=0)
            continue
        if t.minute not in mins:
            t += timedelta(minutes=1)
            continue
        if t - after > timedelta(days=5 * 365 + 1):
            break
        return t
    raise ValueError("no match within 5 years")
