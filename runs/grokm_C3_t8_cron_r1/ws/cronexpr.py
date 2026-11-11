"""Classic 5-field cron expressions. See TASK.md for the exact spec."""

from datetime import datetime, timedelta

_MONTH_NAMES = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_DOW_NAMES = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}

# Whole-expression shortcuts. Expanded before field parsing so "*" restrictions apply.
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def next_run(expr: str, after: datetime) -> datetime:
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")
    minutes, hours, doms, months, dows, dom_restricted, dow_restricted = _parse(expr)
    limit = _add_years(after, 5)
    try:
        cursor = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    except OverflowError:
        raise ValueError("no matching minute within 5 years") from None

    while cursor <= limit:
        if cursor.month not in months:
            cursor = _next_month_start(cursor)
            if cursor is None or cursor > limit:
                break
            continue
        if not _day_matches(cursor, doms, dows, dom_restricted, dow_restricted):
            cursor = _next_day_start(cursor)
            if cursor is None or cursor > limit:
                break
            continue
        if cursor.hour not in hours:
            hour = _next_above(cursor.hour, hours)
            if hour is None:
                cursor = _next_day_start(cursor)
                if cursor is None or cursor > limit:
                    break
            else:
                cursor = cursor.replace(hour=hour, minute=0)
            continue
        if cursor.minute not in minutes:
            minute = _next_above(cursor.minute, minutes)
            if minute is None:
                hour = _next_above(cursor.hour, hours)
                if hour is None:
                    cursor = _next_day_start(cursor)
                    if cursor is None or cursor > limit:
                        break
                else:
                    cursor = cursor.replace(hour=hour, minute=0)
            else:
                cursor = cursor.replace(minute=minute)
            continue
        return cursor
    raise ValueError("no matching minute within 5 years")


def _parse(expr):
    text = expr.strip()
    if text == "":
        raise ValueError("invalid cron expression")
    if any(ch.isspace() and ch not in " \t" for ch in text):
        raise ValueError("invalid cron expression")
    shortcut = _SHORTCUTS.get(text.lower())
    if shortcut is not None:
        text = shortcut
    elif text[:1] == "@":
        raise ValueError("invalid cron expression")

    fields = text.split()
    if len(fields) != 5:
        raise ValueError("invalid cron expression")
    # str.split() also splits on newlines; those were rejected above.
    # Spaces and tabs both count, and runs of them are one separator.
    minute_f, hour_f, dom_f, month_f, dow_f = fields
    minutes = _parse_field(minute_f, 0, 59, {})
    hours = _parse_field(hour_f, 0, 23, {})
    doms = _parse_field(dom_f, 1, 31, {})
    months = _parse_field(month_f, 1, 12, _MONTH_NAMES)
    dows = _parse_field(dow_f, 0, 7, _DOW_NAMES, normalize_sunday=True)
    # Restricted unless the field text is exactly "*". "*/1" is restricted
    # even though it lists every value. Shortcuts were expanded above.
    return (
        minutes,
        hours,
        doms,
        months,
        dows,
        dom_f != "*",
        dow_f != "*",
    )


def _parse_field(field, lo, hi, names, normalize_sunday=False):
    values = set()
    for item in field.split(","):
        if item == "":
            raise ValueError("invalid cron expression")
        for value in _parse_item(item, lo, hi, names):
            if normalize_sunday and value == 7:
                value = 0
            values.add(value)
    return values


def _parse_item(item, lo, hi, names):
    step = 1
    base = item
    if "/" in item:
        base, step_token = item.split("/", 1)
        if (
            base == ""
            or step_token == ""
            or not step_token.isascii()
            or not step_token.isdigit()
        ):
            raise ValueError("invalid cron expression")
        step = int(step_token)
        if step < 1:
            raise ValueError("invalid cron expression")
    if base == "*":
        start, end = lo, hi
    elif "-" in base:
        left, right = base.split("-", 1)
        if left == "" or right == "" or "-" in right:
            raise ValueError("invalid cron expression")
        start = _parse_value(left, lo, hi, names)
        end = _parse_value(right, lo, hi, names)
        if start > end:
            raise ValueError("invalid cron expression")
    else:
        start = _parse_value(base, lo, hi, names)
        # N/S runs from N through the field maximum. A bare N is just N.
        end = hi if "/" in item else start
    return range(start, end + 1, step)


def _parse_value(token, lo, hi, names):
    if not token.isascii():
        raise ValueError("invalid cron expression")
    if token.isdigit():
        value = int(token)
    else:
        value = names.get(token.lower())
        if value is None:
            raise ValueError("invalid cron expression")
    if value < lo or value > hi:
        raise ValueError("invalid cron expression")
    return value


def _day_matches(dt, doms, dows, dom_restricted, dow_restricted):
    # Both restricted → either field may match. Only one restricted → that
    # field alone. Neither restricted → every day.
    if not dom_restricted and not dow_restricted:
        return True
    dom_ok = dt.day in doms
    dow_ok = (dt.weekday() + 1) % 7 in dows
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    if dom_restricted:
        return dom_ok
    return dow_ok


def _add_years(dt, years):
    """Return the instant `years` calendar years after `dt`.

    Feb 29 lands on Feb 28 when the destination year is not a leap year.
    Dates past year 9999 are capped at datetime.max, which is still inside
    the 5-year window when the anniversary itself is not representable.
    """
    year = dt.year + years
    if year > 9999:
        return datetime.max
    try:
        return dt.replace(year=year)
    except ValueError:
        return dt.replace(year=year, day=28)


def _next_above(current, options):
    nxt = None
    for value in options:
        if value > current and (nxt is None or value < nxt):
            nxt = value
    return nxt


def _next_day_start(dt):
    try:
        return datetime(dt.year, dt.month, dt.day) + timedelta(days=1)
    except OverflowError:
        return None


def _next_month_start(dt):
    if dt.month == 12:
        year = dt.year + 1
        month = 1
    else:
        year = dt.year
        month = dt.month + 1
    if year > 9999:
        return None
    return datetime(year, month, 1)
