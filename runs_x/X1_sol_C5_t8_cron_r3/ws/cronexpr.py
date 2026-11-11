"""Classic 5-field cron expressions. See TASK.md for the exact spec."""
import re
from calendar import monthrange
from datetime import datetime, timedelta


_MONTHS = dict(zip('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split(), range(1, 13)))
_WEEKDAYS = dict(zip('SUN MON TUE WED THU FRI SAT'.split(), range(7)))
_SHORTCUTS = {
    '@yearly': '0 0 1 1 *',
    '@annually': '0 0 1 1 *',
    '@monthly': '0 0 1 * *',
    '@weekly': '0 0 * * 0',
    '@daily': '0 0 * * *',
    '@midnight': '0 0 * * *',
    '@hourly': '0 * * * *',
}


def _parse_field(field, minimum, maximum, names):
    """Expand a field before normalizing the Sunday alias."""
    def value(token):
        if token.upper() in names:
            number = names[token.upper()]
        elif re.fullmatch(r'[0-9]+', token):
            number = int(token)
        else:
            raise ValueError('Invalid cron value: ' + token)
        if not minimum <= number <= maximum:
            raise ValueError('Cron value out of range: ' + token)
        return number

    values = set()
    for item in field.split(','):
        parts = item.split('/')
        if len(parts) > 2:
            raise ValueError('Invalid cron step: ' + item)
        step = 1
        if len(parts) == 2:
            if not re.fullmatch(r'[0-9]+', parts[1]):
                raise ValueError('Invalid cron step: ' + item)
            step = int(parts[1])
            if step < 1:
                raise ValueError('Cron step must be positive')
        base = parts[0]
        if base == '*':
            start, end = minimum, maximum
        elif '-' in base:
            bounds = base.split('-')
            if len(bounds) != 2:
                raise ValueError('Invalid cron range: ' + base)
            start, end = map(value, bounds)
            if start > end:
                raise ValueError('Cron ranges cannot wrap around')
        else:
            start = value(base)
            end = maximum if len(parts) == 2 else start
        values.update(range(start, end + 1, step))
    return values


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after ``after``, within five years.

    The horizon is the fifth calendar anniversary (February 29 is clamped
    to February 28). Search whole days so impossible dates remain cheap.
    """
    if not isinstance(expr, str):
        raise TypeError('expr must be a string')
    expression = expr.strip()
    expression = _SHORTCUTS.get(expression.lower(), expression)
    fields = re.split(r'[ \t]+', expression)
    if len(fields) != 5:
        raise ValueError('A cron expression must have five fields')

    minutes, hours, days, months, weekdays = [
        _parse_field(field, low, high, names)
        for field, low, high, names in zip(
            fields, (0, 0, 1, 1, 0), (59, 23, 31, 12, 7),
            ({}, {}, {}, _MONTHS, _WEEKDAYS),
        )
    ]
    weekdays = {day % 7 for day in weekdays}
    dom_restricted = fields[2] != '*'
    dow_restricted = fields[4] != '*'

    if after.year + 5 > datetime.max.year:
        deadline = datetime.max
    else:
        year = after.year + 5
        day = min(after.day, monthrange(year, after.month)[1])
        deadline = after.replace(year=year, day=day)

    current = after.replace(hour=0, minute=0, second=0, microsecond=0)
    hours = sorted(hours)
    minutes = sorted(minutes)
    while current.date() <= deadline.date():
        dom_match = current.day in days
        dow_match = (current.weekday() + 1) % 7 in weekdays
        if dom_restricted and dow_restricted:
            day_match = dom_match or dow_match
        elif dom_restricted:
            day_match = dom_match
        elif dow_restricted:
            day_match = dow_match
        else:
            day_match = True

        if current.month in months and day_match:
            for hour in hours:
                for minute in minutes:
                    candidate = current.replace(hour=hour, minute=minute)
                    if candidate > deadline:
                        raise ValueError('No matching minute within five years')
                    if candidate > after:
                        return candidate
        if current.date() == deadline.date():
            break
        current += timedelta(days=1)

    raise ValueError('No matching minute within five years')
