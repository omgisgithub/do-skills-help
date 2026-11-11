"""Strict npm-style version range matching as specified in TASK.md."""

import re
from dataclasses import dataclass
from functools import total_ordering


_NUMBER = r'(?:0|[1-9][0-9]*)'
_VERSION = re.compile(
    r'(' + _NUMBER + r')\.(' + _NUMBER + r')\.(' + _NUMBER + r')'
    r'(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
    r'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
)


@total_ordering
@dataclass(frozen=True)
class _Version:
    core: tuple
    prerelease: tuple = ()

    def _key(self):
        identifiers = tuple(
            (0, int(part)) if part.isascii() and part.isdigit() else (1, part)
            for part in self.prerelease
        )
        return self.core, not self.prerelease, identifiers

    def __lt__(self, other):
        return self._key() < other._key()


def _parse_version(value):
    if not isinstance(value, str):
        raise ValueError('Version must be a string')
    value = value.strip()
    if value.startswith(('v', '=')):
        value = value[1:]
    match = _VERSION.fullmatch(value)
    if match is None:
        raise ValueError('Invalid version: ' + repr(value))
    major, minor, patch, prerelease, _ = match.groups()
    parts = tuple(prerelease.split('.')) if prerelease else ()
    if any(part.isdigit() and len(part) > 1 and part[0] == '0' for part in parts):
        raise ValueError('Leading zero in numeric prerelease identifier')
    return _Version((int(major), int(minor), int(patch)), parts)


def _parse_partial(value):
    """Return the zero-filled version and number of specified numeric parts."""
    if value.startswith('v'):
        value = value[1:]
    # Metadata is legal only on a complete version.
    if _VERSION.fullmatch(value):
        return _parse_version(value), 3
    parts = value.split('.')
    if not 1 <= len(parts) <= 3:
        raise ValueError('Invalid partial version: ' + repr(value))
    numbers = []
    wildcard = False
    for part in parts:
        if part in ('*', 'x', 'X'):
            wildcard = True
        elif not wildcard and re.fullmatch(_NUMBER, part):
            numbers.append(int(part))
        else:
            raise ValueError('Invalid partial version: ' + repr(value))
    return _Version(tuple(numbers + [0] * (3 - len(numbers)))), len(numbers)


def _upper(version, index):
    core = list(version.core)
    core[index] += 1
    core[index + 1:] = [0] * (2 - index)
    return _Version(tuple(core), ('0',))


def _expand(operator, version, precision):
    """Expand one source comparator into ordinary comparisons."""
    if operator in ('~', '^'):
        if precision == 0:
            return [('>=', _Version((0, 0, 0)))]
        if operator == '~':
            index = 0 if precision == 1 else 1
        else:
            # Missing parts make the last specified component variable, even
            # when all specified components are zero (e.g. ^0.0).
            index = next((i for i in range(precision) if version.core[i]), precision - 1)
        return [('>=', version), ('<', _upper(version, index))]
    if precision == 3:
        return [(operator or '=', version)]
    if precision == 0:
        if operator in ('<', '>'):
            return [('<', _Version((0, 0, 0), ('0',)))]
        return [('>=', _Version((0, 0, 0)))]
    upper = _upper(version, precision - 1)
    if operator == '>':
        return [('>=', _Version(upper.core))]
    if operator == '>=':
        return [('>=', version)]
    if operator == '<':
        return [('<', _Version(version.core, ('0',)))]
    if operator == '<=':
        return [('<', upper)]
    return [('>=', version), ('<', upper)]


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError('Range must be a string')
    result = []
    for source_set in range_.split('||'):
        tokens = source_set.split()
        comparisons = []
        prerelease_cores = set()
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if index + 1 < len(tokens) and tokens[index + 1] == '-':
                if index + 2 >= len(tokens):
                    raise ValueError('Missing hyphen range endpoint')
                left, left_precision = _parse_partial(token)
                right, right_precision = _parse_partial(tokens[index + 2])
                if left_precision:
                    comparisons.append(('>=', left))
                if right_precision == 3:
                    comparisons.append(('<=', right))
                elif right_precision:
                    comparisons.append(('<', _upper(right, right_precision - 1)))
                for endpoint in (left, right):
                    if endpoint.prerelease:
                        prerelease_cores.add(endpoint.core)
                index += 3
                continue
            match = re.fullmatch(r'(<=|>=|[<>=~^])?(.*)', token)
            operator, value = match.groups()
            if not value:
                index += 1
                if index >= len(tokens):
                    raise ValueError('Missing comparator version')
                value = tokens[index]
            version, precision = _parse_partial(value)
            comparisons.extend(_expand(operator, version, precision))
            if version.prerelease:
                prerelease_cores.add(version.core)
            index += 1
        result.append((comparisons, prerelease_cores))
    return result


def _matches(version, sets):
    for comparisons, prerelease_cores in sets:
        if version.prerelease and version.core not in prerelease_cores:
            continue
        if all(
            (version == bound if operator == '=' else
             version < bound if operator == '<' else
             version <= bound if operator == '<=' else
             version > bound if operator == '>' else
             version >= bound)
            for operator, bound in comparisons
        ):
            return True
    return False


def satisfies(version: str, range_: str) -> bool:
    """Return whether a valid version matches a valid range; reject invalid input."""
    return _matches(_parse_version(version), _parse_range(range_))


def max_satisfying(versions: list, range_: str):
    """Return the first highest matching version string, skipping invalid entries."""
    sets = _parse_range(range_)
    best = None
    best_version = None
    for value in versions:
        try:
            version = _parse_version(value)
        except ValueError:
            continue
        if (best_version is None or version > best_version) and _matches(version, sets):
            best, best_version = value, version
    return best
