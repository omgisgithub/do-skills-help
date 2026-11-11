"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
from bisect import bisect_right
from datetime import datetime
import re


_MONTHS = {name: value for value, name in enumerate(
    ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
     'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'), 1)}
_WEEKDAYS = {name: value for value, name in enumerate(
    ('SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'))}
_SHORTCUTS = {
    '@yearly': '0 0 1 1 *', '@annually': '0 0 1 1 *',
    '@monthly': '0 0 1 * *', '@weekly': '0 0 * * 0',
    '@daily': '0 0 * * *', '@midnight': '0 0 * * *',
    '@hourly': '0 * * * *',
}
_ITEM = re.compile(r'(\*|[0-9A-Za-z]+(?:-[0-9A-Za-z]+)?)(?:/([0-9]+))?')


def _parse_field(field, minimum, maximum, names):
    """Expand a field before normalizing any Sunday aliases."""
    def value(token):
        if token.upper() in names:
            return names[token.upper()]
        if re.fullmatch(r'[0-9]+', token):
            number = int(token)
            if minimum <= number <= maximum:
                return number
        raise ValueError('Invalid cron value: ' + token)

    values = set()
    for item in field.split(','):
        match = _ITEM.fullmatch(item)
        if match is None:
            raise ValueError('Invalid cron item: ' + item)
        base, step_text = match.groups()
        step = int(step_text) if step_text is not None else 1
        if step < 1:
            raise ValueError('Cron steps must be positive')
        if base == '*':
            start, end = minimum, maximum
        elif '-' in base:
            left, right = base.split('-')
            start, end = value(left), value(right)
        else:
            start = value(base)
            end = maximum if step_text is not None else start
        if start > end:
            raise ValueError('Cron ranges must be ascending')
        values.update(range(start, end + 1, step))
    return values


def next_run(expr: str, after: datetime) -> datetime:
    """Return the earliest matching minute strictly after ``after``.

    Search at most five calendar years, checking dates before times so
    impossible dates remain inexpensive. February 29's anniversary in a
    non-leap year is February 28.
    """
    if not isinstance(expr, str):
        raise TypeError('Cron expression must be a string')
    expr = expr.strip()
    expr = _SHORTCUTS.get(expr.lower(), expr)
    fields = re.split(r'[ \t]+', expr)
    if len(fields) != 5:
        raise ValueError('Cron expressions require five fields')

    minutes, hours, days, months, weekdays = [
        _parse_field(field, low, high, names)
        for field, (low, high, names) in zip(fields, (
            (0, 59, {}), (0, 23, {}), (1, 31, {}),
            (1, 12, _MONTHS), (0, 7, _WEEKDAYS),
        ))
    ]
    weekdays = {day % 7 for day in weekdays}
    dom_restricted, dow_restricted = fields[2] != '*', fields[4] != '*'
    times = sorted(hour * 60 + minute for hour in hours for minute in minutes)

    if after.year > 9994:
        deadline = datetime.max
    else:
        try:
            deadline = after.replace(year=after.year + 5)
        except ValueError:  # February 29 has no anniversary this year.
            deadline = after.replace(year=after.year + 5, day=28)

    first_day = after.toordinal()
    for ordinal in range(first_day, deadline.toordinal() + 1):
        day = datetime.fromordinal(ordinal)
        if day.month not in months:
            continue
        dom_match = day.day in days
        dow_match = (day.weekday() + 1) % 7 in weekdays
        if dom_restricted and dow_restricted:
            matches = dom_match or dow_match
        elif dom_restricted:
            matches = dom_match
        elif dow_restricted:
            matches = dow_match
        else:
            matches = True
        if not matches:
            continue
        index = bisect_right(times, after.hour * 60 + after.minute) if ordinal == first_day else 0
        if index < len(times):
            hour, minute = divmod(times[index], 60)
            candidate = day.replace(hour=hour, minute=minute)
            if candidate <= deadline:
                return candidate
    raise ValueError('No matching minute within five years')
