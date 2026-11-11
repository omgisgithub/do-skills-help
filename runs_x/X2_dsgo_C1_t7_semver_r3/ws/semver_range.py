"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_NUM_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")
_IDENT_RE = re.compile(r"^[0-9A-Za-z-]+$")
_FULL_VERSION_RE = re.compile(
    r"^([0-9]+)\.([0-9]+)\.([0-9]+)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_OPERATOR_RE = re.compile(r"^(<=|>=|<|>|=|~|\^)")

_SOLO_OPERATORS = frozenset(("<", "<=", ">", ">=", "=", "~", "^"))
_OPERATOR_STARTS = frozenset("<>=~^")

_NEVER_OP = "never"


# ---------------------------------------------------------------------------
# Version parsing
# ---------------------------------------------------------------------------

def _parse_numeric_part(text):
    if not _NUM_RE.match(text):
        raise ValueError("invalid numeric version component: %r" % (text,))
    return int(text)


def _parse_identifiers(text, forbid_leading_zero):
    identifiers = text.split(".")
    for identifier in identifiers:
        if not identifier or not _IDENT_RE.match(identifier):
            raise ValueError("invalid version identifier: %r" % (identifier,))
        if (
            forbid_leading_zero
            and identifier.isdigit()
            and len(identifier) > 1
            and identifier[0] == "0"
        ):
            raise ValueError(
                "numeric prerelease identifier has a leading zero: %r"
                % (identifier,)
            )
    return identifiers


def _parse_full_body(text):
    """Parse MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD] without any prefix."""
    match = _FULL_VERSION_RE.match(text)
    if not match:
        raise ValueError("invalid version: %r" % (text,))

    major = _parse_numeric_part(match.group(1))
    minor = _parse_numeric_part(match.group(2))
    patch = _parse_numeric_part(match.group(3))

    prerelease = None
    if match.group(4) is not None:
        prerelease = _parse_identifiers(match.group(4), True)

    if match.group(5) is not None:
        # Build metadata is validated but ignored for comparisons.
        _parse_identifiers(match.group(5), False)

    return major, minor, patch, prerelease


def _parse_partial_body(text):
    """Parse a partial version (wildcards allowed) without any prefix.

    Returns ``(major, minor, patch, prerelease)`` where missing/wildcard
    components are ``None``.  A partial version never has a prerelease.
    """
    if "-" in text or "+" in text:
        major, minor, patch, prerelease = _parse_full_body(text)
        return major, minor, patch, prerelease

    parts = text.split(".")
    if not parts or len(parts) > 3:
        raise ValueError("invalid partial version: %r" % (text,))

    values = []
    saw_wildcard = False
    for part in parts:
        if part in ("*", "x", "X"):
            saw_wildcard = True
            values.append(None)
        else:
            if saw_wildcard:
                raise ValueError(
                    "non-wildcard component after wildcard: %r" % (text,)
                )
            values.append(_parse_numeric_part(part))

    while len(values) < 3:
        values.append(None)

    return values[0], values[1], values[2], None


def _parse_range_version(text, allow_eq_prefix=False):
    """Parse a version as it appears inside a range (a leading ``v`` is ok)."""
    if text.startswith("v"):
        text = text[1:]
    elif allow_eq_prefix and text.startswith("="):
        text = text[1:]
    if not text:
        raise ValueError("empty version")
    return _parse_partial_body(text)


def _parse_version(text):
    """Parse a standalone version argument."""
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    text = text.strip()
    if text[:1] in ("v", "="):
        text = text[1:]
    if not text:
        raise ValueError("empty version")
    return _parse_full_body(text)


# ---------------------------------------------------------------------------
# Precedence keys
# ---------------------------------------------------------------------------

def _prerelease_key(identifiers):
    key = []
    for identifier in identifiers:
        if identifier.isdigit():
            key.append((0, int(identifier)))
        else:
            key.append((1, identifier))
    return tuple(key)


def _version_key(major, minor, patch, prerelease):
    if prerelease is None:
        return (major, minor, patch, 1, ())
    return (major, minor, patch, 0, _prerelease_key(prerelease))


# ---------------------------------------------------------------------------
# Comparators and desugaring
# ---------------------------------------------------------------------------

def _comparator(op, major, minor, patch, prerelease=None, counts=None):
    if prerelease is None:
        key = _version_key(major, minor, patch, None)
        if counts is None:
            counts = False
    else:
        key = _version_key(major, minor, patch, prerelease)
        if counts is None:
            counts = True
    return (op, key, counts)


def _synthetic_upper(major, minor, patch):
    """``<MAJOR.MINOR.PATCH-0`` -- lowest possible prerelease of that version.

    The synthetic ``0`` prerelease does not count for the prerelease rule.
    """
    return _comparator(
        "<", major, minor, patch, prerelease=["0"], counts=False
    )


def _never():
    return (_NEVER_OP, None, False)


def _any():
    return [_comparator(">=", 0, 0, 0)]


def _caret_upper(major, minor, patch):
    if major > 0:
        return major + 1, 0, 0
    if minor is None:
        return 1, 0, 0
    if minor > 0:
        return 0, minor + 1, 0
    if patch is None:
        return 0, 1, 0
    return 0, 0, patch + 1


def _desugar(op, partial):
    """Turn one comparator into a list of primitives."""
    major, minor, patch, prerelease = partial

    # A wildcard major means the whole version is a wildcard.
    if major is None:
        if op in (None, "=", ">=", "<=", "~", "^"):
            return _any()
        if op in (">", "<"):
            return [_never()]
        raise ValueError("invalid wildcard comparator")

    # Fully specified version.
    if minor is not None and patch is not None:
        if op in (None, "="):
            return [_comparator("=", major, minor, patch, prerelease)]
        if op in ("<", "<=", ">", ">="):
            return [_comparator(op, major, minor, patch, prerelease)]
        if op == "~":
            return [
                _comparator(">=", major, minor, patch, prerelease),
                _synthetic_upper(major, minor + 1, 0),
            ]
        if op == "^":
            upper = _caret_upper(major, minor, patch)
            return [
                _comparator(">=", major, minor, patch, prerelease),
                _synthetic_upper(*upper)
            ]
        raise ValueError("invalid operator")

    # Partial version: minor and/or patch may be wildcards.
    lower_minor = minor if minor is not None else 0
    lower_patch = patch if patch is not None else 0

    if op in (None, "="):
        if minor is None:
            return [
                _comparator(">=", major, 0, 0),
                _synthetic_upper(major + 1, 0, 0),
            ]
        return [
            _comparator(">=", major, minor, 0),
            _synthetic_upper(major, minor + 1, 0),
        ]

    if op == ">":
        if minor is None:
            return [_comparator(">=", major + 1, 0, 0)]
        return [_comparator(">=", major, minor + 1, 0)]

    if op == ">=":
        return [_comparator(">=", major, lower_minor, lower_patch)]

    if op == "<":
        return [
            _comparator(
                "<",
                major,
                lower_minor,
                lower_patch,
                prerelease=["0"],
                counts=False,
            )
        ]

    if op == "<=":
        if minor is None:
            return [_synthetic_upper(major + 1, 0, 0)]
        return [_synthetic_upper(major, minor + 1, 0)]

    if op == "~":
        if minor is None:
            return [
                _comparator(">=", major, 0, 0),
                _synthetic_upper(major + 1, 0, 0),
            ]
        return [
            _comparator(">=", major, minor, 0),
            _synthetic_upper(major, minor + 1, 0),
        ]

    if op == "^":
        upper = _caret_upper(major, minor, patch)
        return [
            _comparator(">=", major, lower_minor, lower_patch),
            _synthetic_upper(*upper),
        ]

    raise ValueError("invalid operator")


def _hyphen_range(left, right):
    left_major, left_minor, left_patch, left_pre = left
    right_major, right_minor, right_patch, right_pre = right

    comparators = []
    if left_major is None:
        comparators.append(_comparator(">=", 0, 0, 0))
    else:
        comparators.append(
            _comparator(
                ">=",
                left_major,
                left_minor if left_minor is not None else 0,
                left_patch if left_patch is not None else 0,
                left_pre,
            )
        )

    if right_major is None:
        pass
    elif right_minor is not None and right_patch is not None:
        comparators.append(
            _comparator(
                "<=", right_major, right_minor, right_patch, right_pre
            )
        )
    elif right_minor is None:
        comparators.append(_synthetic_upper(right_major + 1, 0, 0))
    else:
        comparators.append(_synthetic_upper(right_major, right_minor + 1, 0))

    return comparators


def _parse_comparator(token):
    match = _OPERATOR_RE.match(token)
    if match:
        op = match.group(1)
        body = token[match.end():]
    else:
        op = None
        body = token

    if not body:
        raise ValueError("missing version in comparator: %r" % (token,))

    return _desugar(op, _parse_range_version(body))


# ---------------------------------------------------------------------------
# Range parsing
# ---------------------------------------------------------------------------

def _glue_operators(raw_tokens):
    """Join a standalone operator with the token that follows it."""
    tokens = []
    index = 0
    while index < len(raw_tokens):
        token = raw_tokens[index]
        if token in _SOLO_OPERATORS:
            if index + 1 >= len(raw_tokens):
                raise ValueError("operator with no version: %r" % (token,))
            following = raw_tokens[index + 1]
            if not following or following[0] in _OPERATOR_STARTS:
                raise ValueError("operator with no version: %r" % (token,))
            tokens.append(token + following)
            index += 2
        else:
            tokens.append(token)
            index += 1
    return tokens


def _parse_comparator_set(text):
    tokens = _glue_operators(text.split())
    comparators = []

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "-":
            raise ValueError("misplaced hyphen range separator")

        if index + 1 < len(tokens) and tokens[index + 1] == "-":
            if index + 2 >= len(tokens):
                raise ValueError("hyphen range is missing its right side")
            left = _parse_range_version(token, allow_eq_prefix=True)
            right = _parse_range_version(tokens[index + 2], allow_eq_prefix=True)
            comparators.extend(_hyphen_range(left, right))
            index += 3
        else:
            comparators.extend(_parse_comparator(token))
            index += 1

    prerelease_mmps = set()
    for _op, key, counts in comparators:
        if counts and key is not None:
            prerelease_mmps.add((key[0], key[1], key[2]))

    return comparators, prerelease_mmps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")

    return [_parse_comparator_set(part) for part in range_.strip().split("||")]


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _match(comparator, key):
    op, boundary, _counts = comparator
    if op == _NEVER_OP:
        return False
    if op == "<":
        return key < boundary
    if op == "<=":
        return key <= boundary
    if op == ">":
        return key > boundary
    if op == ">=":
        return key >= boundary
    if op == "=":
        return key == boundary
    raise ValueError("unknown comparator operator: %r" % (op,))


def _satisfies_parsed(version, parsed_range):
    major, minor, patch, prerelease = version
    key = _version_key(major, minor, patch, prerelease)

    for comparators, prerelease_mmps in parsed_range:
        if not all(_match(comparator, key) for comparator in comparators):
            continue
        if prerelease is not None and (major, minor, patch) not in prerelease_mmps:
            continue
        return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def satisfies(version, range_):
    parsed_version = _parse_version(version)
    parsed_range = _parse_range(range_)
    return _satisfies_parsed(parsed_version, parsed_range)


def max_satisfying(versions, range_):
    parsed_range = _parse_range(range_)

    best = None
    best_key = None
    for entry in versions:
        try:
            parsed_version = _parse_version(entry)
        except (ValueError, TypeError, AttributeError):
            continue

        key = _version_key(*parsed_version)
        if not _satisfies_parsed(parsed_version, parsed_range):
            continue

        # Strict ``>`` keeps the first string in the list among versions that
        # are equal in precedence (e.g. differ only in build metadata).
        if best is None or key > best_key:
            best = entry
            best_key = key

    return best
