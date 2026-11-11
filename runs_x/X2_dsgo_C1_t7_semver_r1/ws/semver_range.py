"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_FULL_RE = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
_NUM_RE = re.compile(r"0|[1-9][0-9]*")

_IMPOSSIBLE = object()
_OPERATOR_ONLY = (">=", "<=", ">", "<", "=", "~", "^")
_WILDCARDS = ("*", "x", "X")


class _Version(object):
    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(self, major, minor, patch, prerelease=(), build=()):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease)
        self.build = tuple(build)


def _parse_version(text, allow_eq_prefix=True):
    """Parse a complete MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD] version."""
    if not isinstance(text, str):
        raise ValueError("invalid version: %r" % (text,))
    s = text.strip()
    if s.startswith("v"):
        s = s[1:]
    elif allow_eq_prefix and s.startswith("="):
        s = s[1:]
    match = _FULL_RE.fullmatch(s)
    if match is None:
        raise ValueError("invalid version: %r" % (text,))

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))

    prerelease = ()
    if match.group(4) is not None:
        identifiers = []
        for identifier in match.group(4).split("."):
            if identifier.isdigit():
                if len(identifier) > 1 and identifier[0] == "0":
                    raise ValueError("invalid version: %r" % (text,))
                identifiers.append(int(identifier))
            else:
                identifiers.append(identifier)
        prerelease = tuple(identifiers)

    build = ()
    if match.group(5) is not None:
        build = tuple(match.group(5).split("."))

    return _Version(major, minor, patch, prerelease, build)


def _parse_operand(text):
    """Parse a full version or a partial (X-range) operand.

    Returns ("full", _Version) or ("partial", major, minor, patch) where a
    None component means it was omitted or written as a wildcard.
    """
    s = text.strip()

    try:
        return ("full", _parse_version(s, allow_eq_prefix=False))
    except ValueError:
        pass

    if s.startswith("v"):
        s = s[1:]

    if s in _WILDCARDS:
        return ("partial", None, None, None)

    if not s:
        raise ValueError("invalid version: %r" % (text,))

    parts = s.split(".")
    if len(parts) > 3:
        raise ValueError("invalid version: %r" % (text,))

    values = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if part in _WILDCARDS:
            if index == 0 and len(parts) > 1:
                raise ValueError("invalid version: %r" % (text,))
            for rest in parts[index:]:
                if rest not in _WILDCARDS:
                    raise ValueError("invalid version: %r" % (text,))
            values.extend([None] * (3 - index))
            break
        if _NUM_RE.fullmatch(part) is None:
            raise ValueError("invalid version: %r" % (text,))
        values.append(int(part))
        index += 1

    if len(values) < 3:
        values.extend([None] * (3 - len(values)))
    if values[0] is None:
        raise ValueError("invalid version: %r" % (text,))

    return ("partial", values[0], values[1], values[2])


def _compare_identifiers(left, right):
    left_numeric = isinstance(left, int)
    right_numeric = isinstance(right, int)
    if left_numeric and right_numeric:
        if left < right:
            return -1
        if left > right:
            return 1
        return 0
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _compare(left, right):
    for attribute in ("major", "minor", "patch"):
        a = getattr(left, attribute)
        b = getattr(right, attribute)
        if a < b:
            return -1
        if a > b:
            return 1

    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1

    for a, b in zip(left.prerelease, right.prerelease):
        result = _compare_identifiers(a, b)
        if result:
            return result

    if len(left.prerelease) < len(right.prerelease):
        return -1
    if len(left.prerelease) > len(right.prerelease):
        return 1
    return 0


def _matches_comparator(version, operator, comparator_version):
    result = _compare(version, comparator_version)
    if operator == "<":
        return result < 0
    if operator == "<=":
        return result <= 0
    if operator == ">":
        return result > 0
    if operator == ">=":
        return result >= 0
    # "="
    return result == 0


def _desugar(operator, operand):
    """Turn a plain comparator (or X-range) into primitive comparators."""
    if operand[0] == "full":
        version = operand[1]
        explicit_prerelease = bool(version.prerelease)
        if operator in ("", "="):
            return [("=", version, explicit_prerelease)]
        return [(operator, version, explicit_prerelease)]

    _, major, minor, patch = operand

    # Wildcard only: *, x, X
    if major is None:
        if operator in ("", "=", ">=", "<="):
            return [(">=", _Version(0, 0, 0), False)]
        return _IMPOSSIBLE

    # Only MAJOR was specified (1, 1.x, 1.x.x, ...)
    if minor is None:
        lower = _Version(major, 0, 0)
        upper = _Version(major + 1, 0, 0, (0,))
        if operator in ("", "="):
            return [(">=", lower, False), ("<", upper, False)]
        if operator == ">":
            return [(">=", _Version(major + 1, 0, 0), False)]
        if operator == ">=":
            return [(">=", lower, False)]
        if operator == "<":
            return [("<", _Version(major, 0, 0, (0,)), False)]
        if operator == "<=":
            return [("<", upper, False)]

    # MAJOR.MINOR was specified (1.2, 1.2.x, 1.2.*, ...)
    if patch is None:
        lower = _Version(major, minor, 0)
        upper = _Version(major, minor + 1, 0, (0,))
        if operator in ("", "="):
            return [(">=", lower, False), ("<", upper, False)]
        if operator == ">":
            return [(">=", _Version(major, minor + 1, 0), False)]
        if operator == ">=":
            return [(">=", lower, False)]
        if operator == "<":
            return [("<", _Version(major, minor, 0, (0,)), False)]
        if operator == "<=":
            return [("<", upper, False)]

    raise ValueError("invalid comparator")


def _tilde(operand):
    if operand[0] == "full":
        version = operand[1]
        lower = version
        upper = _Version(version.major, version.minor + 1, 0, (0,))
        return [
            (">=", lower, bool(version.prerelease)),
            ("<", upper, False),
        ]

    _, major, minor, patch = operand
    if major is None:
        raise ValueError("invalid tilde range")
    if minor is None:
        lower = _Version(major, 0, 0)
        upper = _Version(major + 1, 0, 0, (0,))
    else:
        lower = _Version(major, minor, 0)
        upper = _Version(major, minor + 1, 0, (0,))
    return [(">=", lower, False), ("<", upper, False)]


def _caret(operand):
    if operand[0] == "full":
        version = operand[1]
        major = version.major
        minor = version.minor
        patch = version.patch
        lower = version
        explicit_prerelease = bool(version.prerelease)
        minor_specified = True
        patch_specified = True
    else:
        _, major, minor, patch = operand
        if major is None:
            raise ValueError("invalid caret range")
        lower = _Version(major, minor or 0, patch or 0)
        explicit_prerelease = False
        minor_specified = minor is not None
        patch_specified = patch is not None

    if major > 0:
        upper = _Version(major + 1, 0, 0, (0,))
    elif not minor_specified:
        upper = _Version(1, 0, 0, (0,))
    elif minor > 0:
        upper = _Version(0, minor + 1, 0, (0,))
    elif not patch_specified:
        upper = _Version(0, 1, 0, (0,))
    else:
        upper = _Version(0, 0, patch + 1, (0,))

    return [
        (">=", lower, explicit_prerelease),
        ("<", upper, False),
    ]


def _hyphen(left_operand, right_operand):
    if left_operand[0] == "full":
        lower = left_operand[1]
        explicit_prerelease = bool(lower.prerelease)
    else:
        _, major, minor, patch = left_operand
        if major is None:
            raise ValueError("invalid hyphen range")
        lower = _Version(major, minor or 0, patch or 0)
        explicit_prerelease = False

    if right_operand[0] == "full":
        upper = right_operand[1]
        upper_comparator = ("<=", upper, bool(upper.prerelease))
    else:
        _, major, minor, patch = right_operand
        if major is None:
            raise ValueError("invalid hyphen range")
        if minor is None:
            upper_comparator = ("<", _Version(major + 1, 0, 0, (0,)), False)
        elif patch is None:
            upper_comparator = ("<", _Version(major, minor + 1, 0, (0,)), False)
        else:
            upper_comparator = ("<=", _Version(major, minor, patch), False)

    return [(">=", lower, explicit_prerelease), upper_comparator]


def _split_operator(token):
    for operator in _OPERATOR_ONLY:
        if token.startswith(operator):
            return operator, token[len(operator):]
    return "", token


def _parse_set(text):
    """Parse one comparator set.  Returns a list of comparators, or None if
    the set is impossible to satisfy.  An empty list means "any version"."""
    s = text.strip()
    if not s:
        return []

    tokens = s.split()

    # An operator may be separated from its operand by whitespace.
    merged = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATOR_ONLY:
            if index + 1 >= len(tokens):
                raise ValueError("invalid range: %r" % (text,))
            next_token = tokens[index + 1]
            if next_token[:1] in "<>=~^":
                raise ValueError("invalid range: %r" % (text,))
            merged.append(token + next_token)
            index += 2
        else:
            merged.append(token)
            index += 1

    if "-" in merged:
        if len(merged) != 3 or merged[1] != "-":
            raise ValueError("invalid hyphen range: %r" % (text,))
        left = _parse_operand(merged[0])
        right = _parse_operand(merged[2])
        return _hyphen(left, right)

    comparators = []
    for token in merged:
        operator, operand_text = _split_operator(token)
        operand = _parse_operand(operand_text)
        if operator == "~":
            result = _tilde(operand)
        elif operator == "^":
            result = _caret(operand)
        else:
            result = _desugar(operator, operand)
        if result is _IMPOSSIBLE:
            return None
        comparators.extend(result)

    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


def _set_satisfies(version, comparators):
    if comparators is None:
        return False

    for operator, comparator_version, _explicit in comparators:
        if not _matches_comparator(version, operator, comparator_version):
            return False

    if version.prerelease:
        for _operator, comparator_version, explicit in comparators:
            if (
                explicit
                and comparator_version.major == version.major
                and comparator_version.minor == version.minor
                and comparator_version.patch == version.patch
            ):
                return True
        return False

    return True


def satisfies(version, range_):
    parsed_version = _parse_version(version)
    sets = _parse_range(range_)
    return any(_set_satisfies(parsed_version, comparators) for comparators in sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best_text = None
    best_version = None

    for candidate in versions:
        try:
            parsed_version = _parse_version(candidate)
        except (ValueError, TypeError, AttributeError):
            continue

        if not any(
            _set_satisfies(parsed_version, comparators) for comparators in sets
        ):
            continue

        if best_version is None or _compare(parsed_version, best_version) > 0:
            best_text = candidate
            best_version = parsed_version

    return best_text
