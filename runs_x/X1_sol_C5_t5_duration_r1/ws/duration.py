import re
from decimal import Decimal
from fractions import Fraction


_PART = r'([0-9]+(?:\.[0-9]+)?)([wdhms])'
_UNIT_FORM = re.compile(_PART + r'(?: ?' + _PART + r')*')
_UNIT_PART = re.compile(_PART)
_CLOCK_FORM = re.compile(r'[0-9]+(?::[0-5][0-9]){1,2}')
_SECONDS = {'w': 604800, 'd': 86400, 'h': 3600, 'm': 60, 's': 1}


def parse_duration(s: str) -> int:
    """Parse a unit or clock duration into exact whole seconds.

    Raise TypeError for non-strings and ValueError for invalid durations.
    """
    if not isinstance(s, str):
        raise TypeError('duration must be a string')

    value = s.strip()
    sign = -1 if value.startswith('-') else 1
    if sign == -1:
        value = value[1:]

    if value == '0':
        return 0

    if _CLOCK_FORM.fullmatch(value):
        seconds = 0
        for field in value.split(':'):
            # Decimal conversion avoids interpreter limits on int(string).
            seconds = seconds * 60 + int(Decimal(field))
        return sign * seconds

    if not _UNIT_FORM.fullmatch(value):
        raise ValueError('invalid duration syntax')

    total = Fraction(0)
    previous_unit = 604801
    for match in _UNIT_PART.finditer(value):
        number, unit = match.groups()
        unit_seconds = _SECONDS[unit]
        if unit_seconds >= previous_unit:
            raise ValueError('units must be in strictly decreasing order')
        previous_unit = unit_seconds
        # Decimal construction and Fraction conversion are exact, independent
        # of the active decimal context's arithmetic precision.
        total += Fraction(Decimal(number)) * unit_seconds

    if total.denominator != 1:
        raise ValueError('duration must be a whole number of seconds')
    return sign * total.numerator
