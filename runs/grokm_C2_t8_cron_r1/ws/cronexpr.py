"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
from datetime import datetime, timedelta

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_DOWS = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}
_ALIASES = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
# lo, hi, names, dow (7 is Sunday). Hi 7 lets "5-7" and "N/S" reach Sunday.
_FIELDS = (
    (0, 59, None, False),
    (0, 23, None, False),
    (1, 31, None, False),
    (1, 12, _MONTHS, False),
    (0, 7, _DOWS, True),
)


def _bad():
    raise ValueError("invalid cron expression")


def _number(tok, lo, hi, names):
    if names and tok.upper() in names:
        return names[tok.upper()]
    if not tok or any(c not in "0123456789" for c in tok):
        _bad()
    n = int(tok)
    if n < lo or n > hi:
        _bad()
    return n


def _item(item, lo, hi, names, is_dow):
    if item.count("/") > 1:
        _bad()
    if "/" in item:
        base, step_s = item.split("/")
        if not step_s or any(c not in "0123456789" for c in step_s):
            _bad()
        step = int(step_s)
        if step < 1:
            _bad()
    else:
        base, step = item, 1
    if base == "*":
        start, end = lo, hi
    elif "-" in base:
        bits = base.split("-")
        if len(bits) != 2 or not bits[0] or not bits[1]:
            _bad()
        start = _number(bits[0], lo, hi, names)
        end = _number(bits[1], lo, hi, names)
        if start > end:
            _bad()
    else:
        n = _number(base, lo, hi, names)
        if "/" not in item:
            return {0 if is_dow and n == 7 else n}
        start, end = n, hi
    out = set()
    v = start
    while v <= end:
        out.add(0 if is_dow and v == 7 else v)
        v += step
    return out


def _field(text, lo, hi, names, is_dow):
    if not text:
        _bad()
    vals = set()
    for item in text.split(","):
        if not item:
            _bad()
        vals |= _item(item, lo, hi, names, is_dow)
    return vals


def _parse(expr):
    raw = expr.strip()
    if any(ch.isspace() and ch not in " \t" for ch in raw):
        _bad()
    folded = raw.lower()
    if folded in _ALIASES:
        raw = _ALIASES[folded]
    elif folded.startswith("@"):
        _bad()
    parts = raw.split()
    if len(parts) != 5:
        _bad()
    parsed = [
        _field(part, lo, hi, names, is_dow)
        for part, (lo, hi, names, is_dow) in zip(parts, _FIELDS)
    ]
    # Restricted unless the field is exactly "*". See TASK.md day matching.
    return parsed, parts[2] != "*", parts[4] != "*"


def _day_ok(dt, doms, dows, dom_r, dow_r):
    dom_ok = dt.day in doms
    dow_ok = (dt.weekday() + 1) % 7 in dows
    if dom_r and dow_r:
        return dom_ok or dow_ok
    if dom_r:
        return dom_ok
    if dow_r:
        return dow_ok
    return True


def _deadline(after):
    try:
        return after.replace(year=after.year + 5)
    except ValueError:
        try:
            # shortcut: Feb 29 + 5y clamps to Feb 28, upgrade if a caller needs Mar 1
            return after.replace(year=after.year + 5, day=28)
        except ValueError:
            return datetime.max


def next_run(expr, after):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    (minutes, hours, doms, months, dows), dom_r, dow_r = _parse(expr)
    try:
        t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no matching minute within 5 years")
    deadline = _deadline(after)
    try:
        while t <= deadline:
            if t.month not in months:
                y, m = t.year, t.month
                nxt = None
                for _ in range(12):
                    if m == 12:
                        y, m = y + 1, 1
                    else:
                        m += 1
                    if m in months:
                        nxt = datetime(y, m, 1)
                        break
                if nxt is None or nxt > deadline:
                    break
                t = nxt
                continue
            if not _day_ok(t, doms, dows, dom_r, dow_r):
                t = (t + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                continue
            if t.hour not in hours:
                later = [h for h in hours if h > t.hour]
                if later:
                    t = t.replace(hour=min(later), minute=min(minutes), second=0, microsecond=0)
                else:
                    t = (t + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                continue
            if t.minute not in minutes:
                later = [m for m in minutes if m > t.minute]
                if later:
                    t = t.replace(minute=min(later), second=0, microsecond=0)
                else:
                    t = t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                continue
            return t
    except OverflowError:
        pass
    raise ValueError("no matching minute within 5 years")


if __name__ == "__main__":
    assert next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)) == datetime(2026, 3, 4, 10, 15)
    assert next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)) == datetime(2026, 3, 9, 9, 0)
    assert next_run("0 0 29 2 *", datetime(2026, 3, 1)) == datetime(2028, 2, 29)
    assert next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)) == datetime(2026, 1, 2, 4, 30)
    try:
        next_run(1, datetime(2026, 1, 1))
    except TypeError:
        pass
    else:
        raise AssertionError("type")
    try:
        next_run("0 0 30 2 *", datetime(2026, 1, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("impossible")
