"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_NUMBER = r'(?:0|[1-9][0-9]*)'
_IDENTIFIERS = r'[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*'
_VERSION = re.compile(
    r'(' + _NUMBER + r')\.(' + _NUMBER + r')\.(' + _NUMBER + r')'
    r'(?:-(' + _IDENTIFIERS + r'))?(?:\+(' + _IDENTIFIERS + r'))?'
)
_OPERATOR = re.compile(r'(<=|>=|<|>|=|~|\^)?(.*)')
_OPERATORS = {'<', '<=', '>', '>=', '=', '~', '^'}


def _make_version(core, prerelease=None):
    # Tagged identifiers make Python tuple ordering follow SemVer ordering.
    if prerelease is None:
        suffix = (1,)
    else:
        identifiers = []
        for part in prerelease.split('.'):
            if part.isascii() and part.isdigit():
                if len(part) > 1 and part[0] == '0':
                    raise ValueError('Leading zero in prerelease identifier')
                identifiers.append((0, int(part)))
            else:
                identifiers.append((1, part))
        suffix = (0, tuple(identifiers))
    return tuple(core) + (suffix,)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError('Version must be a string')
    text = text.strip()
    if text.startswith(('v', '=')):
        text = text[1:]
    match = _VERSION.fullmatch(text)
    if match is None:
        raise ValueError('Invalid version: ' + text)
    return _make_version(tuple(int(match[i]) for i in (1, 2, 3)), match[4])


def _parse_operand(text):
    """Return a zero-filled version and the number of specified components."""
    if text.startswith('v'):
        text = text[1:]
    match = _VERSION.fullmatch(text)
    if match is not None:
        return _make_version(tuple(int(match[i]) for i in (1, 2, 3)), match[4]), 3
    parts = text.split('.')
    if not 1 <= len(parts) <= 3:
        raise ValueError('Invalid range version: ' + text)
    core = []
    wildcard = False
    for part in parts:
        if part in ('*', 'x', 'X'):
            wildcard = True
        elif wildcard or re.fullmatch(_NUMBER, part) is None:
            raise ValueError('Invalid range version: ' + text)
        else:
            core.append(int(part))
    if len(core) == 3:
        raise ValueError('Invalid range version: ' + text)
    return _make_version(core + [0] * (3 - len(core))), len(core)


def _upper(version, component):
    core = list(version[:3])
    core[component] += 1
    core[component + 1:] = [0] * (2 - component)
    return _make_version(core, '0')


def _expand(operator, version, precision):
    """Desugar one comparator to (operator, version) bounds."""
    if precision == 0:
        if operator in ('<', '>'):
            return [('<', _make_version((0, 0, 0), '0'))]
        return [('>=', _make_version((0, 0, 0)))]
    if operator in ('~', '^'):
        if operator == '~':
            component = min(precision - 1, 1)
        else:
            # With missing components, the last specified zero can change.
            component = next((i for i in range(precision) if version[i]),
                             precision - 1)
        return [('>=', version), ('<', _upper(version, component))]
    if precision == 3:
        return [(operator or '=', version)]
    upper = _upper(version, precision - 1)
    if operator in ('', '='):
        return [('>=', version), ('<', upper)]
    if operator == '>':
        return [('>=', _make_version(upper[:3]))]
    if operator == '>=':
        return [('>=', version)]
    if operator == '<':
        return [('<', _make_version(version[:3], '0'))]
    return [('<', upper)]  # <= a partial version includes its whole interval.


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError('Range must be a string')
    sets = []
    for set_text in range_.split('||'):
        tokens = set_text.split()
        bounds = []
        prerelease_cores = set()

        def operand(text):
            version, precision = _parse_operand(text)
            if version[3][0] == 0:
                prerelease_cores.add(version[:3])
            return version, precision

        i = 0
        while i < len(tokens):
            if i + 1 < len(tokens) and tokens[i + 1] == '-':
                if i + 2 >= len(tokens):
                    raise ValueError('Missing hyphen range endpoint')
                left, _ = operand(tokens[i])
                right, precision = operand(tokens[i + 2])
                bounds.append(('>=', left))
                if precision == 3:
                    bounds.append(('<=', right))
                elif precision:
                    bounds.append(('<', _upper(right, precision - 1)))
                i += 3
                continue
            token = tokens[i]
            operator, value = _OPERATOR.fullmatch(token).groups()
            operator = operator or ''
            if token in _OPERATORS:
                i += 1
                if i == len(tokens):
                    raise ValueError('Missing comparator version')
                value = tokens[i]
            version, precision = operand(value)
            bounds.extend(_expand(operator, version, precision))
            i += 1
        sets.append((bounds, prerelease_cores))
    return sets


def _matches(version, sets):
    for bounds, prerelease_cores in sets:
        if version[3][0] == 0 and version[:3] not in prerelease_cores:
            continue
        for operator, target in bounds:
            if operator == '=':
                matches = version == target
            elif operator == '<':
                matches = version < target
            elif operator == '<=':
                matches = version <= target
            elif operator == '>':
                matches = version > target
            else:
                matches = version >= target
            if not matches:
                break
        else:
            return True
    return False


def satisfies(version: str, range_: str) -> bool:
    """Return whether version matches range_; reject invalid input with ValueError."""
    parsed = _parse_version(version)
    return _matches(parsed, _parse_range(range_))


def max_satisfying(versions: list, range_: str):
    """Return the first highest matching original string, skipping invalid versions."""
    sets = _parse_range(range_)
    best_version = None
    best_text = None
    for text in versions:
        try:
            version = _parse_version(text)
        except ValueError:
            continue
        if (best_version is None or version > best_version) and _matches(version, sets):
            best_version = version
            best_text = text
    return best_text
