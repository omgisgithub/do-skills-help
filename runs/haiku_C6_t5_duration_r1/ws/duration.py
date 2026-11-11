import re
from fractions import Fraction

# Unit sizes in seconds, in the only order they may appear (largest first).
_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}

# [0-9] rather than \d: \d also matches non-ASCII digits.
_NUM = r"[0-9]+(?:\.[0-9]+)?"
_UNIT_PART = re.compile(r"(%s)([wdhms])" % _NUM)
_UNIT_FORM = re.compile(r"%s[wdhms](?: ?%s[wdhms])*" % (_NUM, _NUM))
_CLOCK_FORM = re.compile(r"[0-9]+:[0-5][0-9](?::[0-5][0-9])?")


def parse_duration(s: str) -> int:
    """Parse a human duration into whole seconds. See TASK.md."""
    if not isinstance(s, str):
        raise TypeError("duration must be a str, not %s" % type(s).__name__)

    text = s.strip()
    if text == "0":
        return 0

    sign = 1
    body = text
    if body.startswith("-"):
        sign = -1
        body = body[1:]

    if _CLOCK_FORM.fullmatch(body):
        fields = [int(f) for f in body.split(":")]
        if len(fields) == 2:
            fields.insert(0, 0)
        hours, minutes, seconds = fields
        return sign * (hours * 3600 + minutes * 60 + seconds)

    if _UNIT_FORM.fullmatch(body):
        total = Fraction(0)
        previous_size = None
        for number, unit in _UNIT_PART.findall(body):
            size = _UNITS[unit]
            if previous_size is not None and size >= previous_size:
                raise ValueError("units out of order or repeated: %r" % s)
            previous_size = size
            total += Fraction(number) * size
        if total.denominator != 1:
            raise ValueError("duration is not a whole number of seconds: %r" % s)
        return sign * int(total)

    raise ValueError("invalid duration: %r" % s)
