"""npm-style version range matching. See TASK.md for the exact spec."""

import re
from dataclasses import dataclass
from typing import Optional


_PARTIAL = re.compile(
    r'([0-9]+|[xX*])(?:\.([0-9]+|[xX*]))?(?:\.([0-9]+|[xX*]))?'
    r'(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
    r'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
)
_COMPARATOR = re.compile(r'(<=|>=|[<>=~^])?(.*)')


@dataclass(frozen=True)
class _Version:
    core: tuple
    prerelease: Optional[tuple] = None

    @property
    def key(self):
        # Each identifier is tagged so numeric identifiers sort before text.
        return self.core, self.prerelease is None, self.prerelease or ()


def _parse_partial(text, allow_v=True):
    if allow_v and text.startswith('v'):
        text = text[1:]
    match = _PARTIAL.fullmatch(text)
    if match is None:
        raise ValueError('Invalid version: {!r}'.format(text))

    numbers = []
    wildcard = False
    for part in match.group(1, 2, 3):
        if part is None or part in ('x', 'X', '*'):
            wildcard = True
        else:
            if wildcard or (len(part) > 1 and part[0] == '0'):
                raise ValueError('Invalid version: {!r}'.format(text))
            numbers.append(int(part))

    precision = len(numbers)
    pre, build = match.group(4, 5)
    if precision < 3 and (pre is not None or build is not None):
        raise ValueError('Partial versions cannot have prerelease or build tags')
    identifiers = None
    if pre is not None:
        identifiers = []
        for identifier in pre.split('.'):
            if identifier.isdigit():
                if len(identifier) > 1 and identifier[0] == '0':
                    raise ValueError('Numeric prerelease identifiers cannot have leading zeros')
                identifiers.append((0, int(identifier)))
            else:
                identifiers.append((1, identifier))
        identifiers = tuple(identifiers)
    return _Version(tuple(numbers + [0] * (3 - precision)), identifiers), precision


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError('Version must be a string')
    text = text.strip()
    if text.startswith(('v', '=')):
        text = text[1:]
    version, precision = _parse_partial(text, allow_v=False)
    if precision != 3:
        raise ValueError('A version must have major, minor, and patch numbers')
    return version


def _upper_bound(version, index):
    """Increment a component, zero the rest, and exclude its prereleases."""
    core = list(version.core)
    core[index] += 1
    core[index + 1:] = [0] * (2 - index)
    return _Version(tuple(core), ((0, 0),))


def _expand(operator, version, precision):
    if operator in ('~', '^'):
        if precision == 0:
            return [('>=', version)]
        if operator == '~':
            index = 0 if precision == 1 else 1
        else:
            # Missing components are free to vary, even when all fixed ones
            # are zero (e.g. ^0.0 permits every patch in minor zero).
            index = next((i for i in range(precision) if version.core[i]),
                         precision - 1)
        return [('>=', version), ('<', _upper_bound(version, index))]

    if precision == 3:
        return [(operator, version)]
    if precision == 0:
        if operator in ('<', '>'):
            return [('<', _Version((0, 0, 0), ((0, 0),)))]
        return [('>=', version)]

    upper = _upper_bound(version, precision - 1)
    if operator == '=':
        return [('>=', version), ('<', upper)]
    if operator == '>':
        return [('>=', _Version(upper.core))]
    if operator == '>=':
        return [('>=', version)]
    if operator == '<':
        return [('<', _Version(version.core, ((0, 0),)))]
    return [('<', upper)]  # <= a partial includes all of its missing parts.


def _parse_set(text):
    tokens = text.split()
    constraints = []
    prerelease_cores = set()

    def operand(token):
        version, precision = _parse_partial(token)
        if version.prerelease is not None:
            prerelease_cores.add(version.core)
        return version, precision

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if index + 1 < len(tokens) and tokens[index + 1] == '-':
            if index + 2 >= len(tokens):
                raise ValueError('Missing hyphen range endpoint')
            left, _ = operand(token)
            right, precision = operand(tokens[index + 2])
            constraints.append(('>=', left))
            if precision == 3:
                constraints.append(('<=', right))
            elif precision:
                constraints.append(('<', _upper_bound(right, precision - 1)))
            index += 3
            continue

        match = _COMPARATOR.fullmatch(token)
        operator, value = match.groups()
        if not value:
            index += 1
            if index >= len(tokens):
                raise ValueError('Missing comparator version')
            value = tokens[index]
        version, precision = operand(value)
        constraints.extend(_expand(operator or '=', version, precision))
        index += 1
    return constraints, prerelease_cores


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError('Range must be a string')
    # Parse every branch before matching, so invalid unused branches still fail.
    return [_parse_set(part) for part in range_.split('||')]


def _matches(version, sets):
    for constraints, prerelease_cores in sets:
        if (version.prerelease is not None
                and version.core not in prerelease_cores):
            continue
        for operator, bound in constraints:
            comparison = (version.key > bound.key) - (version.key < bound.key)
            if not {'=': comparison == 0, '<': comparison < 0,
                    '<=': comparison <= 0, '>': comparison > 0,
                    '>=': comparison >= 0}[operator]:
                break
        else:
            return True
    return False


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version matches a range; reject invalid input."""
    parsed_version = _parse_version(version)
    return _matches(parsed_version, _parse_range(range_))


def max_satisfying(versions: list, range_: str):
    """Return the first highest-precedence match, skipping invalid versions."""
    sets = _parse_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            version = _parse_version(text)
        except ValueError:
            continue
        if _matches(version, sets) and (best_key is None or version.key > best_key):
            best = text
            best_key = version.key
    return best
