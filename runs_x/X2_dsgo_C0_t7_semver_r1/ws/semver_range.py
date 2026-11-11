"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_NUMERIC_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")
_DIGITS_RE = re.compile(r"^[0-9]+$")
_IDENTIFIER_RE = re.compile(r"^[0-9A-Za-z-]+$")
_OPERATOR_RE = re.compile(r"^(<=|>=|<|>|=|\^|~)?(.*)$")
_STANDALONE_OPERATORS = ("<", "<=", ">", ">=", "=", "^", "~")


class _Version(object):
    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(self, major, minor, patch, prerelease=(), build=()):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease)
        self.build = tuple(build)


class _Partial(object):
    """A possibly incomplete version, as used inside comparators."""

    __slots__ = ("major", "minor", "patch", "n", "prerelease", "build")

    def __init__(self, major, minor, patch, n, prerelease=(), build=()):
        self.major = major
        self.minor = minor
        self.patch = patch
        # Number of leading numeric components (0 for "*", 1 for "1.x", ...).
        self.n = n
        self.prerelease = tuple(prerelease)
        self.build = tuple(build)


class _ComparatorSet(object):
    __slots__ = ("comparators", "allow_prerelease", "impossible")

    def __init__(self, comparators, allow_prerelease, impossible):
        self.comparators = comparators
        self.allow_prerelease = allow_prerelease
        self.impossible = impossible


def _parse_identifiers(text, no_leading_zeros):
    if not text:
        raise ValueError("empty identifier list")
    identifiers = []
    for identifier in text.split("."):
        if not identifier or not _IDENTIFIER_RE.match(identifier):
            raise ValueError("invalid identifier: %r" % (identifier,))
        if (
            no_leading_zeros
            and _DIGITS_RE.match(identifier)
            and len(identifier) > 1
            and identifier[0] == "0"
        ):
            raise ValueError("numeric identifier has a leading zero")
        identifiers.append(identifier)
    return tuple(identifiers)


def _parse_partial(text, allow_equals=True):
    """Parse a full or partial version into a _Partial."""
    s = text.strip()
    if not s:
        raise ValueError("empty version")

    if s[0] == "=":
        if not allow_equals:
            raise ValueError("unexpected '='")
        s = s[1:]
    elif s[0] == "v":
        s = s[1:]
    if not s:
        raise ValueError("empty version")

    if s.count("+") > 1:
        raise ValueError("multiple build separators")
    build = None
    if "+" in s:
        s, build = s.split("+", 1)
        if not s:
            raise ValueError("missing version before build")
    if s.count("-") > 0:
        core, prerelease = s.split("-", 1)
        if not core:
            raise ValueError("missing version before prerelease")
        s = core
    else:
        prerelease = None

    if not s:
        raise ValueError("empty version")

    parts = s.split(".")
    if len(parts) > 3:
        raise ValueError("too many version components")

    comps = []
    n = 0
    seen_wildcard = False
    for part in parts:
        if part in ("*", "x", "X"):
            seen_wildcard = True
            comps.append(None)
        else:
            if seen_wildcard:
                raise ValueError("numeric component after a wildcard")
            if not _NUMERIC_RE.match(part):
                raise ValueError("invalid version component: %r" % (part,))
            comps.append(int(part))
            n += 1
    while len(comps) < 3:
        comps.append(None)

    full = n == 3
    if not full and (prerelease is not None or build is not None):
        raise ValueError("partial versions cannot have prerelease or build")

    prerelease_ids = ()
    if prerelease is not None:
        prerelease_ids = _parse_identifiers(prerelease, True)
    build_ids = ()
    if build is not None:
        build_ids = _parse_identifiers(build, False)

    return _Partial(comps[0], comps[1], comps[2], n, prerelease_ids, build_ids)


def _parse_version(text):
    partial = _parse_partial(text, allow_equals=True)
    if partial.n != 3:
        raise ValueError("not a complete version: %r" % (text,))
    return _Version(
        partial.major,
        partial.minor,
        partial.patch,
        partial.prerelease,
        partial.build,
    )


def _is_numeric_identifier(identifier):
    return bool(_DIGITS_RE.match(identifier))


def _compare_prerelease(left, right):
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1

    for left_id, right_id in zip(left, right):
        if left_id == right_id:
            continue
        left_numeric = _is_numeric_identifier(left_id)
        right_numeric = _is_numeric_identifier(right_id)
        if left_numeric and right_numeric:
            left_value = int(left_id)
            right_value = int(right_id)
            if left_value < right_value:
                return -1
            if left_value > right_value:
                return 1
        elif left_numeric:
            return -1
        elif right_numeric:
            return 1
        else:
            return -1 if left_id < right_id else 1

    if len(left) < len(right):
        return -1
    if len(left) > len(right):
        return 1
    return 0


def _compare_versions(left, right):
    for left_value, right_value in (
        (left.major, right.major),
        (left.minor, right.minor),
        (left.patch, right.patch),
    ):
        if left_value < right_value:
            return -1
        if left_value > right_value:
            return 1
    return _compare_prerelease(left.prerelease, right.prerelease)


def _version(major, minor, patch, prerelease=()):
    return _Version(major, minor, patch, prerelease)


def _desugar(op, partial):
    """Turn one comparator token into primitive comparators.

    Returns (comparators, allow_prerelease, impossible) where each comparator is
    an (operator, _Version) pair.
    """
    n = partial.n
    allowed = set()

    if n == 0:
        if op in (">", "<"):
            return [], allowed, True
        return [], allowed, False

    def lower_version():
        return _Version(
            partial.major or 0,
            partial.minor or 0,
            partial.patch or 0,
            partial.prerelease,
        )

    def note_prerelease():
        if n == 3 and partial.prerelease:
            allowed.add((partial.major, partial.minor, partial.patch))

    if op in (None, "="):
        if n == 3:
            note_prerelease()
            return [("=", lower_version())], allowed, False
        if n == 1:
            return [
                (">=", _version(partial.major, 0, 0)),
                ("<", _version(partial.major + 1, 0, 0, ("0",))),
            ], allowed, False
        return [
            (">=", _version(partial.major, partial.minor, 0)),
            ("<", _version(partial.major, partial.minor + 1, 0, ("0",))),
        ], allowed, False

    if op == ">":
        if n == 3:
            note_prerelease()
            return [(">", lower_version())], allowed, False
        if n == 1:
            return [(">=", _version(partial.major + 1, 0, 0))], allowed, False
        return [(">=", _version(partial.major, partial.minor + 1, 0))], allowed, False

    if op == ">=":
        if n == 3:
            note_prerelease()
            return [(">=", lower_version())], allowed, False
        if n == 1:
            return [(">=", _version(partial.major, 0, 0))], allowed, False
        return [(">=", _version(partial.major, partial.minor, 0))], allowed, False

    if op == "<":
        if n == 3:
            note_prerelease()
            return [("<", lower_version())], allowed, False
        if n == 1:
            return [("<", _version(partial.major, 0, 0, ("0",)))], allowed, False
        return [
            ("<", _version(partial.major, partial.minor, 0, ("0",)))
        ], allowed, False

    if op == "<=":
        if n == 3:
            note_prerelease()
            return [("<=", lower_version())], allowed, False
        if n == 1:
            return [
                ("<", _version(partial.major + 1, 0, 0, ("0",)))
            ], allowed, False
        return [
            ("<", _version(partial.major, partial.minor + 1, 0, ("0",)))
        ], allowed, False

    if op == "~":
        if n == 3:
            note_prerelease()
            return [
                (">=", lower_version()),
                ("<", _version(partial.major, partial.minor + 1, 0, ("0",))),
            ], allowed, False
        if n == 1:
            return [
                (">=", _version(partial.major, 0, 0)),
                ("<", _version(partial.major + 1, 0, 0, ("0",))),
            ], allowed, False
        return [
            (">=", _version(partial.major, partial.minor, 0)),
            ("<", _version(partial.major, partial.minor + 1, 0, ("0",))),
        ], allowed, False

    if op == "^":
        if n == 3:
            note_prerelease()
            lower = lower_version()
            if partial.major > 0:
                upper = _version(partial.major + 1, 0, 0, ("0",))
            elif partial.minor > 0:
                upper = _version(0, partial.minor + 1, 0, ("0",))
            else:
                upper = _version(0, 0, partial.patch + 1, ("0",))
            return [(">=", lower), ("<", upper)], allowed, False

        if n == 1:
            return [
                (">=", _version(partial.major, 0, 0)),
                ("<", _version(partial.major + 1, 0, 0, ("0",))),
            ], allowed, False

        lower = _version(partial.major, partial.minor, 0)
        if partial.major > 0:
            upper = _version(partial.major + 1, 0, 0, ("0",))
        else:
            upper = _version(0, partial.minor + 1, 0, ("0",))
        return [(">=", lower), ("<", upper)], allowed, False

    raise ValueError("invalid operator: %r" % (op,))


def _parse_comparator_token(token):
    match = _OPERATOR_RE.match(token)
    op = match.group(1)
    rest = match.group(2)
    partial = _parse_partial(rest, allow_equals=False)
    return op, partial


def _parse_hyphen(left_text, right_text):
    left = _parse_partial(left_text, allow_equals=True)
    right = _parse_partial(right_text, allow_equals=True)

    comparators = []
    allowed = set()

    if left.n > 0:
        comparators.append(
            (
                ">=",
                _version(
                    left.major or 0,
                    left.minor or 0,
                    left.patch or 0,
                    left.prerelease,
                ),
            )
        )
        if left.n == 3 and left.prerelease:
            allowed.add((left.major, left.minor, left.patch))

    if right.n == 3:
        comparators.append(
            (
                "<=",
                _version(right.major, right.minor, right.patch, right.prerelease),
            )
        )
        if right.prerelease:
            allowed.add((right.major, right.minor, right.patch))
    elif right.n == 2:
        comparators.append(
            ("<", _version(right.major, right.minor + 1, 0, ("0",)))
        )
    elif right.n == 1:
        comparators.append(("<", _version(right.major + 1, 0, 0, ("0",))))

    return _ComparatorSet(comparators, allowed, False)


def _parse_set(text):
    text = text.strip()
    if not text:
        return _ComparatorSet([], set(), False)

    tokens = text.split()

    if "-" in tokens:
        if len(tokens) != 3 or tokens[1] != "-":
            raise ValueError("invalid hyphen range")
        return _parse_hyphen(tokens[0], tokens[2])

    comparators = []
    allowed = set()
    impossible = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _STANDALONE_OPERATORS:
            if index + 1 >= len(tokens):
                raise ValueError("operator without a version")
            op = token
            partial = _parse_partial(tokens[index + 1], allow_equals=True)
            index += 2
        else:
            op, partial = _parse_comparator_token(token)
            index += 1

        token_comparators, token_allowed, token_impossible = _desugar(op, partial)
        comparators.extend(token_comparators)
        allowed |= token_allowed
        impossible = impossible or token_impossible

    return _ComparatorSet(comparators, allowed, impossible)


def _parse_range(range_):
    return [_parse_set(part) for part in range_.split("||")]


def _satisfies_set(version, comparator_set):
    if comparator_set.impossible:
        return False

    for op, bound in comparator_set.comparators:
        comparison = _compare_versions(version, bound)
        if op == "<":
            if comparison >= 0:
                return False
        elif op == "<=":
            if comparison > 0:
                return False
        elif op == ">":
            if comparison <= 0:
                return False
        elif op == ">=":
            if comparison < 0:
                return False
        elif op == "=":
            if comparison != 0:
                return False
        else:
            raise ValueError("invalid operator: %r" % (op,))

    if version.prerelease:
        triple = (version.major, version.minor, version.patch)
        if triple not in comparator_set.allow_prerelease:
            return False

    return True


def satisfies(version, range_):
    parsed_version = _parse_version(version)
    comparator_sets = _parse_range(range_)
    return any(
        _satisfies_set(parsed_version, comparator_set)
        for comparator_set in comparator_sets
    )


def max_satisfying(versions, range_):
    comparator_sets = _parse_range(range_)

    best = None
    best_version = None
    for candidate in versions:
        try:
            parsed = _parse_version(candidate)
        except (ValueError, TypeError, AttributeError):
            continue

        if not any(
            _satisfies_set(parsed, comparator_set)
            for comparator_set in comparator_sets
        ):
            continue

        if best_version is None or _compare_versions(parsed, best_version) > 0:
            best = candidate
            best_version = parsed

    return best
