"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from datetime import datetime, timedelta

_MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_DOW_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
}

_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_INT_RE = re.compile(r"^[0-9]+$")
_FIELD_SPLIT_RE = re.compile(r"[ \t]+")


class _Field(object):
    """One parsed cron field: allowed values plus its raw-text restriction flag."""

    def __init__(self, minimum, maximum, names, text):
        self.minimum = minimum
        self.maximum = maximum
        self.names = names
        self.text = text
        self.values = frozenset(self._parse(text))

    @property
    def restricted(self):
        return self.text != "*"

    def _value(self, token):
        upper = token.upper()
        if upper in self.names:
            return self.names[upper]
        if _INT_RE.match(token):
            value = int(token)
            if self.minimum <= value <= self.maximum:
                return value
        raise ValueError("invalid value %r" % (token,))

    def _parse(self, text):
        result = set()
        for item in text.split(","):
            if not item:
                raise ValueError("empty field item")

            parts = item.split("/")
            if len(parts) > 2:
                raise ValueError("invalid step %r" % (item,))
            base = parts[0]
            step = None
            if len(parts) == 2:
                if not _INT_RE.match(parts[1]):
                    raise ValueError("invalid step %r" % (item,))
                step = int(parts[1])
                if step < 1:
                    raise ValueError("invalid step %r" % (item,))

            if base == "*":
                start, end = self.minimum, self.maximum
            elif "-" in base:
                bounds = base.split("-")
                if len(bounds) != 2 or not bounds[0] or not bounds[1]:
                    raise ValueError("invalid range %r" % (item,))
                start = self._value(bounds[0])
                end = self._value(bounds[1])
                if start > end:
                    raise ValueError("invalid range %r" % (item,))
            else:
                value = self._value(base)
                start = value
                end = self.maximum if step is not None else value

            if step is None:
                step = 1
            result.update(range(start, end + 1, step))
        return result


def _parse(expr):
    if not isinstance(expr, str):
        raise TypeError("expr must be a str")

    text = expr.strip()
    if not text:
        raise ValueError("empty expression")
    if text.startswith("@"):
        key = text.lower()
        if key not in _SHORTCUTS:
            raise ValueError("unknown shortcut %r" % (expr,))
        text = _SHORTCUTS[key]

    fields = _FIELD_SPLIT_RE.split(text)
    if len(fields) != 5:
        raise ValueError("expected 5 fields, got %d" % (len(fields),))

    minute = _Field(0, 59, {}, fields[0])
    hour = _Field(0, 23, {}, fields[1])
    dom = _Field(1, 31, {}, fields[2])
    month = _Field(1, 12, _MONTH_NAMES, fields[3])
    dow = _Field(0, 7, _DOW_NAMES, fields[4])

    # 7 and 0 both mean Sunday.
    dow_values = frozenset(0 if value == 7 else value for value in dow.values)

    return {
        "minutes": sorted(minute.values),
        "hours": sorted(hour.values),
        "dom": frozenset(dom.values),
        "dom_restricted": dom.restricted,
        "months": frozenset(month.values),
        "dow": dow_values,
        "dow_restricted": dow.restricted,
    }


def _day_matches(date, spec):
    dom_restricted = spec["dom_restricted"]
    dow_restricted = spec["dow_restricted"]
    dom_match = date.day in spec["dom"]
    # Python: Monday == 0. Cron: Sunday == 0.
    dow_match = ((date.weekday() + 1) % 7) in spec["dow"]

    if dom_restricted and dow_restricted:
        return dom_match or dow_match
    if dom_restricted:
        return dom_match
    if dow_restricted:
        return dow_match
    return True


def next_run(expr, after):
    """Return the earliest matching minute strictly later than ``after``.

    Raises ``ValueError`` for an invalid expression or when no matching minute
    exists within five years, and ``TypeError`` when ``expr`` is not a string.
    """
    spec = _parse(expr)

    # First candidate minute strictly after ``after``.
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

    # Calendar-accurate limit of five years after ``after``.
    try:
        limit = after.replace(year=after.year + 5)
    except ValueError:  # Feb 29 -> non-leap target year
        limit = after.replace(year=after.year + 5, day=28)

    if candidate > limit:
        raise ValueError("no matching minute within 5 years")

    day = candidate.date()
    last_day = limit.date()
    one_day = timedelta(days=1)

    while day <= last_day:
        if day.month in spec["months"] and _day_matches(day, spec):
            for hour in spec["hours"]:
                if day == candidate.date() and hour < candidate.hour:
                    continue
                for minute in spec["minutes"]:
                    if (
                        day == candidate.date()
                        and hour == candidate.hour
                        and minute < candidate.minute
                    ):
                        continue
                    result = datetime(day.year, day.month, day.day, hour, minute)
                    if result > limit:
                        raise ValueError("no matching minute within 5 years")
                    return result
        day += one_day

    raise ValueError("no matching minute within 5 years")
