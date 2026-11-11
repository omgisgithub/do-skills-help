"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_NUMBER = r'(?:0|[1-9][0-9]*)'
_IDENTIFIERS = r'[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*'
_FULL = re.compile(
    r'(' + _NUMBER + r')\.(' + _NUMBER + r')\.(' + _NUMBER + r')'
    r'(?:-(' + _IDENTIFIERS + r'))?(?:\+(' + _IDENTIFIERS + r'))?'
)
_OPERATOR = re.compile(r'(<=|>=|[<>=~^])?(.*)')
_OPERATORS = {'<', '<=', '>', '>=', '=', '~', '^'}


def _key(core, prerelease=None):
    """Tuple whose native ordering is SemVer precedence (build is omitted)."""
    identifiers = ()
    if prerelease is not None:
        identifiers = tuple(
            (0, int(part)) if part.isdigit() else (1, part)
            for part in prerelease.split('.')
        )
    return (core, prerelease is None, identifiers)


def _full_version(value):
    match = _FULL.fullmatch(value)
    if match is None:
        raise ValueError('Invalid version: {!r}'.format(value))
    major, minor, patch, prerelease, _ = match.groups()
    if prerelease is not None:
        for part in prerelease.split('.'):
            if part.isdigit() and len(part) > 1 and part[0] == '0':
                raise ValueError('Leading zero in prerelease: {!r}'.format(value))
    return _key((int(major), int(minor), int(patch)), prerelease)


def _parse_version(value):
    if not isinstance(value, str):
        raise ValueError('Version must be a string')
    value = value.strip()
    if value.startswith(('v', '=')):
        value = value[1:]
    return _full_version(value)


def _operand(value):
    """Return (zero-filled version, number of specified numeric components)."""
    if value.startswith('v'):
        value = value[1:]
    if _FULL.fullmatch(value):
        return _full_version(value), 3
    parts = value.split('.')
    if not 1 <= len(parts) <= 3:
        raise ValueError('Invalid range version: {!r}'.format(value))
    numbers = []
    wildcard = False
    for part in parts:
        if part in ('*', 'x', 'X'):
            wildcard = True
        elif not wildcard and re.fullmatch(_NUMBER, part):
            numbers.append(int(part))
        else:
            raise ValueError('Invalid range version: {!r}'.format(value))
    count = len(numbers)
    return _key(tuple(numbers + [0] * (3 - count))), count


def _upper(core, index):
    """Exclusive upper bound, excluding prereleases at the next core."""
    bumped = list(core)
    bumped[index] += 1
    bumped[index + 1:] = [0] * (2 - index)
    return _key(tuple(bumped), '0')


def _expand(operator, version, count):
    core = version[0]
    if operator in ('~', '^'):
        if count == 0:
            return [('>=', _key((0, 0, 0)))]
        if operator == '~':
            index = 0 if count == 1 else 1
        else:
            # Missing components determine the bound when all specified
            # components are zero: ^0.0 reaches 0.1.0, ^0 reaches 1.0.0.
            index = next((i for i in range(count) if core[i]), count - 1)
        return [('>=', version), ('<', _upper(core, index))]
    if count == 3:
        return [(operator or '=', version)]
    if count == 0:
        if operator in ('<', '>'):
            return [('<', _key((0, 0, 0), '0'))]
        return [('>=', _key((0, 0, 0)))]
    upper = _upper(core, count - 1)
    if operator == '>':
        return [('>=', _key(upper[0]))]
    if operator == '>=':
        return [('>=', version)]
    if operator == '<':
        return [('<', _key(core, '0'))]
    if operator == '<=':
        return [('<', upper)]
    return [('>=', version), ('<', upper)]


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError('Range must be a string')
    sets = []
    for branch in range_.split('||'):
        tokens = branch.split()
        bounds = []
        prerelease_cores = set()

        def operand(token):
            version, count = _operand(token)
            if not version[1]:
                prerelease_cores.add(version[0])
            return version, count

        index = 0
        while index < len(tokens):
            token = tokens[index]
            if index + 1 < len(tokens) and tokens[index + 1] == '-':
                if index + 2 >= len(tokens):
                    raise ValueError('Missing hyphen range endpoint')
                left, _ = operand(token)
                right, count = operand(tokens[index + 2])
                bounds.append(('>=', left))
                if count == 3:
                    bounds.append(('<=', right))
                elif count:
                    bounds.append(('<', _upper(right[0], count - 1)))
                index += 3
                continue
            operator, value = _OPERATOR.fullmatch(token).groups()
            if token in _OPERATORS:
                index += 1
                if index >= len(tokens):
                    raise ValueError('Missing comparator operand')
                value = tokens[index]
            version, count = operand(value)
            bounds.extend(_expand(operator, version, count))
            index += 1
        sets.append((bounds, prerelease_cores))
    return sets


def _matches(version, sets):
    for bounds, prerelease_cores in sets:
        if not version[1] and version[0] not in prerelease_cores:
            continue
        for operator, bound in bounds:
            if operator == '=':
                matches = version == bound
            elif operator == '<':
                matches = version < bound
            elif operator == '<=':
                matches = version <= bound
            elif operator == '>':
                matches = version > bound
            else:
                matches = version >= bound
            if not matches:
                break
        else:
            return True
    return False


def satisfies(version: str, range_: str) -> bool:
    """Whether version matches range_; invalid versions/ranges raise ValueError."""
    parsed = _parse_version(version)
    sets = _parse_range(range_)
    return _matches(parsed, sets)


def max_satisfying(versions: list, range_: str):
    """Return the first highest matching original string, skipping invalid entries."""
    sets = _parse_range(range_)
    best = None
    best_key = None
    for version in versions:
        try:
            parsed = _parse_version(version)
        except ValueError:
            continue
        if (best_key is None or parsed > best_key) and _matches(parsed, sets):
            best = version
            best_key = parsed
    return best
