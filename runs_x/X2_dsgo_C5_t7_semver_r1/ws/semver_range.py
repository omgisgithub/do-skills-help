"""npm-style version range matching. See TASK.md for the exact spec."""

import re
from functools import total_ordering

_NUM = r'(?:0|[1-9][0-9]*)'
_WILD = r'[xX*]'
_IDENT = r'[0-9A-Za-z-]+'
_PRE = _IDENT + r'(?:\.' + _IDENT + r')*'

_VERSION_RE = re.compile(
    r'^(?:v|=)?(' + _NUM + r')\.(' + _NUM + r')\.(' + _NUM + r')'
    r'(?:-(' + _PRE + r'))?(?:\+(' + _PRE + r'))?$'
)

# MAJOR[.MINOR[.PATCH]][-PRERELEASE][+BUILD]; components may be wildcards.
_PARTIAL_RE = re.compile(
    r'^v?(' + _NUM + '|' + _WILD + r')'
    r'(?:\.(' + _NUM + '|' + _WILD + r')'
    r'(?:\.(' + _NUM + '|' + _WILD + r')'
    r'(?:-(' + _PRE + r'))?'
    r'(?:\+(' + _PRE + r'))?'
    r')?)?$'
)

_OPERATORS = ('<', '<=', '>', '>=', '=', '~', '^')


def _invalid(what):
    raise ValueError('invalid %s' % (what,))


def _is_wild(value):
    return value in ('x', 'X', '*')


def _validate_prerelease(pre):
    for ident in pre.split('.'):
        if not ident:
            _invalid('prerelease')
        if ident.isdigit() and len(ident) > 1 and ident[0] == '0':
            _invalid('prerelease')


def _parse_version(text):
    """Parse a full version string into a _Version."""
    if not isinstance(text, str):
        _invalid('version')
    m = _VERSION_RE.match(text.strip())
    if m is None:
        _invalid('version')
    major, minor, patch, pre, _build = m.groups()
    prerelease = ()
    if pre is not None:
        _validate_prerelease(pre)
        prerelease = tuple(pre.split('.'))
    return _Version(int(major), int(minor), int(patch), prerelease)


def _parse_partial(text):
    """Parse a (possibly partial / wildcard) version.

    Returns (major, minor, patch, prerelease); missing or wildcard components
    are None.  Raises ValueError when invalid.
    """
    m = _PARTIAL_RE.match(text)
    if m is None:
        _invalid('version')
    raw_major, raw_minor, raw_patch, pre, build = m.groups()

    if _is_wild(raw_major):
        if raw_minor is not None and not _is_wild(raw_minor):
            _invalid('version')
        if raw_patch is not None and not _is_wild(raw_patch):
            _invalid('version')
    elif raw_minor is not None and _is_wild(raw_minor):
        if raw_patch is not None and not _is_wild(raw_patch):
            _invalid('version')

    full = (
        raw_major is not None and raw_minor is not None and raw_patch is not None
        and not _is_wild(raw_major) and not _is_wild(raw_minor)
        and not _is_wild(raw_patch)
    )
    if (pre is not None or build is not None) and not full:
        _invalid('version')

    prerelease = ()
    if pre is not None:
        _validate_prerelease(pre)
        prerelease = tuple(pre.split('.'))

    major = None if _is_wild(raw_major) else int(raw_major)
    minor = None if raw_minor is None or _is_wild(raw_minor) else int(raw_minor)
    patch = None if raw_patch is None or _is_wild(raw_patch) else int(raw_patch)
    return major, minor, patch, prerelease


def _cmp_ident(a, b):
    a_num = a.isdigit()
    b_num = b.isdigit()
    if a_num and b_num:
        ai, bi = int(a), int(b)
        return (ai > bi) - (ai < bi)
    if a_num:
        return -1
    if b_num:
        return 1
    return (a > b) - (a < b)


def _compare_versions(a, b):
    for attr in ('major', 'minor', 'patch'):
        av = getattr(a, attr)
        bv = getattr(b, attr)
        if av != bv:
            return -1 if av < bv else 1
    pa, pb = a.prerelease, b.prerelease
    if not pa and not pb:
        return 0
    if not pa:
        return 1
    if not pb:
        return -1
    for ia, ib in zip(pa, pb):
        c = _cmp_ident(ia, ib)
        if c:
            return c
    if len(pa) == len(pb):
        return 0
    return -1 if len(pa) < len(pb) else 1


@total_ordering
class _Version(object):
    __slots__ = ('major', 'minor', 'patch', 'prerelease')

    def __init__(self, major, minor, patch, prerelease=()):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease)

    def __eq__(self, other):
        if not isinstance(other, _Version):
            return NotImplemented
        return _compare_versions(self, other) == 0

    def __lt__(self, other):
        if not isinstance(other, _Version):
            return NotImplemented
        return _compare_versions(self, other) < 0

    def __hash__(self):
        return hash((self.major, self.minor, self.patch, self.prerelease))


class _Comparator(object):
    """A single primitive comparator.

    ``anchor`` is (major, minor, patch) when this comparator was written with a
    prerelease version; it makes prerelease versions eligible under the
    prerelease rule.  Synthetic ``-0`` upper bounds have ``anchor`` None.
    """

    __slots__ = ('op', 'version', 'anchor')

    def __init__(self, op, version, anchor=None):
        self.op = op
        self.version = version
        self.anchor = anchor

    def matches(self, version):
        if self.op == 'never':
            return False
        c = _compare_versions(version, self.version)
        if self.op == '<':
            return c < 0
        if self.op == '<=':
            return c <= 0
        if self.op == '>':
            return c > 0
        if self.op == '>=':
            return c >= 0
        return c == 0  # '='


def _anchor(pre, major, minor, patch):
    return (major, minor, patch) if pre else None


def _upper(major, minor, patch):
    """Synthetic exclusive upper bound at major.minor.patch-0."""
    return _Comparator('<', _Version(major, minor, patch, ('0',)))


def _lower(major, minor, patch, prerelease=()):
    return _Comparator('>=', _Version(major, minor, patch, prerelease))


def _never():
    return [_Comparator('never', _Version(0, 0, 0))]


def _all():
    return [_Comparator('>=', _Version(0, 0, 0))]


def _desugar(op, major, minor, patch, pre):
    if op in ('', '='):
        if major is None:
            return _all()
        if patch is None:
            low = _lower(major, minor or 0, 0)
            if minor is None:
                return [low, _upper(major + 1, 0, 0)]
            return [low, _upper(major, minor + 1, 0)]
        version = _Version(major, minor, patch, pre)
        return [_Comparator('=', version, _anchor(pre, major, minor, patch))]

    if op == '>=':
        if major is None:
            return _all()
        return [_Comparator('>=', _Version(major, minor or 0, patch or 0, pre),
                            _anchor(pre, major, minor, patch))]

    if op == '>':
        if major is None:
            return _never()
        if patch is None:
            if minor is None:
                return [_Comparator('>=', _Version(major + 1, 0, 0))]
            return [_Comparator('>=', _Version(major, minor + 1, 0))]
        return [_Comparator('>', _Version(major, minor, patch, pre),
                            _anchor(pre, major, minor, patch))]

    if op == '<':
        if major is None:
            return _never()
        if patch is None:
            return [_upper(major, minor or 0, 0)]
        return [_Comparator('<', _Version(major, minor, patch, pre),
                            _anchor(pre, major, minor, patch))]

    if op == '<=':
        if major is None:
            return _all()
        if patch is None:
            if minor is None:
                return [_upper(major + 1, 0, 0)]
            return [_upper(major, minor + 1, 0)]
        return [_Comparator('<=', _Version(major, minor, patch, pre),
                            _anchor(pre, major, minor, patch))]

    if op == '~':
        if major is None:
            return _all()
        if patch is None:
            low = _lower(major, minor or 0, 0)
            if minor is None:
                return [low, _upper(major + 1, 0, 0)]
            return [low, _upper(major, minor + 1, 0)]
        return [_Comparator('>=', _Version(major, minor, patch, pre),
                            _anchor(pre, major, minor, patch)),
                _upper(major, minor + 1, 0)]

    # op == '^'
    if major is None:
        return _all()
    if major != 0:
        high = (major + 1, 0, 0)
    elif minor is None:
        high = (1, 0, 0)
    elif minor != 0:
        high = (0, minor + 1, 0)
    elif patch is None:
        high = (0, 1, 0)
    else:
        high = (0, 0, patch + 1)
    return [_Comparator('>=', _Version(major, minor or 0, patch or 0, pre),
                        _anchor(pre, major, minor, patch)),
            _upper(*high)]


def _desugar_hyphen(left, right):
    lmaj, lmin, lpat, lpre = _parse_partial(left)
    rmaj, rmin, rpat, rpre = _parse_partial(right)
    comparators = []
    if lmaj is not None:
        comparators.append(_Comparator(
            '>=', _Version(lmaj, lmin or 0, lpat or 0, lpre),
            _anchor(lpre, lmaj, lmin or 0, lpat or 0)))
    if rmaj is not None:
        if rpat is None:
            if rmin is None:
                comparators.append(_upper(rmaj + 1, 0, 0))
            else:
                comparators.append(_upper(rmaj, rmin + 1, 0))
        else:
            comparators.append(_Comparator(
                '<=', _Version(rmaj, rmin, rpat, rpre),
                _anchor(rpre, rmaj, rmin, rpat)))
    return comparators


def _parse_comparator(token):
    m = re.match(r'^(<=|>=|<|>|=|~|\^)?(.*)$', token)
    op = m.group(1) or ''
    rest = m.group(2)
    if not rest:
        _invalid('range')
    major, minor, patch, pre = _parse_partial(rest)
    return _desugar(op, major, minor, patch, pre)


def _parse_set(text):
    tokens = text.split()

    # Allow whitespace between an operator and its version (`>= 1.2.3`).
    merged = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in _OPERATORS:
            if i + 1 >= len(tokens) or tokens[i + 1] in _OPERATORS:
                _invalid('range')
            merged.append(token + tokens[i + 1])
            i += 2
        else:
            merged.append(token)
            i += 1

    comparators = []
    i = 0
    while i < len(merged):
        token = merged[i]
        if token == '-':
            _invalid('range')
        if i + 2 < len(merged) and merged[i + 1] == '-':
            comparators.extend(_desugar_hyphen(token, merged[i + 2]))
            i += 3
        else:
            comparators.extend(_parse_comparator(token))
            i += 1
    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        _invalid('range')
    return [_parse_set(part) for part in range_.split('||')]


def _set_matches(comparators, version):
    for comparator in comparators:
        if not comparator.matches(version):
            return False
    if version.prerelease is not None and version.prerelease:
        key = (version.major, version.minor, version.patch)
        return any(c.anchor == key for c in comparators if c.anchor is not None)
    return True


def _matches_any(version, sets):
    return any(_set_matches(comparators, version) for comparators in sets)


def satisfies(version, range_):
    parsed_version = _parse_version(version)
    sets = _parse_range(range_)
    return _matches_any(parsed_version, sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_version = None
    for candidate in versions:
        try:
            parsed = _parse_version(candidate)
        except (ValueError, TypeError):
            continue
        if not _matches_any(parsed, sets):
            continue
        if best is None or _compare_versions(parsed, best_version) > 0:
            best = candidate
            best_version = parsed
    return best
