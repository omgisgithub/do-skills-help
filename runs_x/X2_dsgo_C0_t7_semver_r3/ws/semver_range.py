"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_IDENT_CHARS = frozenset(
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-"
)

_PARTIAL_RE = re.compile(
    r"^(?P<major>[0-9]+|[xX*])"
    r"(?:\.(?P<minor>[0-9]+|[xX*]))?"
    r"(?:\.(?P<patch>[0-9]+|[xX*]))?"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)

_HYPHEN_RE = re.compile(r"^(\S+)\s+-\s+(\S+)$")

_OPERATORS = frozenset(("<", "<=", ">", ">=", "=", "~", "^"))

_IMPOSSIBLE = object()


class _Version(object):
    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(self, major, minor, patch, prerelease, build):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease
        self.build = build

    def key(self):
        """Sort key implementing SemVer precedence (build is ignored)."""
        if self.prerelease is None:
            pre = ()
            release = 1
        else:
            pre = tuple(
                (0, int(part)) if part.isdigit() else (1, part)
                for part in self.prerelease
            )
            release = 0
        return (self.major, self.minor, self.patch, release, pre)


class _Partial(object):
    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(self, major, minor, patch, prerelease, build):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease
        self.build = build


class _Comparator(object):
    __slots__ = ("op", "version", "counts_for_prerelease")

    def __init__(self, op, version, counts_for_prerelease):
        self.op = op
        self.version = version
        self.counts_for_prerelease = counts_for_prerelease

    def matches(self, version):
        left = version.key()
        right = self.version.key()
        if self.op == "<":
            return left < right
        if self.op == "<=":
            return left <= right
        if self.op == ">":
            return left > right
        if self.op == ">=":
            return left >= right
        return left == right  # "="


def _validate_identifiers(text):
    parts = text.split(".")
    if not parts:
        raise ValueError("empty identifier list")
    for part in parts:
        if not part or any(ch not in _IDENT_CHARS for ch in part):
            raise ValueError("invalid identifier")
    return tuple(parts)


def _parse_partial(text):
    """Parse a (possibly partial) version. Raise ValueError when invalid."""
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    text = text.strip()
    # A single leading "v" or "=" is ignored.
    if text[:1] in ("v", "="):
        text = text[1:]

    match = _PARTIAL_RE.match(text)
    if match is None:
        raise ValueError("invalid version: %r" % (text,))

    values = []
    seen_wildcard = False
    for group in ("major", "minor", "patch"):
        raw = match.group(group)
        if raw is None or raw in ("x", "X", "*"):
            if raw is not None:
                seen_wildcard = True
            values.append(None)
            continue
        if seen_wildcard:
            raise ValueError("numeric component after wildcard")
        if len(raw) > 1 and raw[0] == "0":
            raise ValueError("leading zero in version component")
        values.append(int(raw))

    major, minor, patch = values

    pre_raw = match.group("pre")
    build_raw = match.group("build")

    if (pre_raw is not None or build_raw is not None) and None in values:
        # Partial versions never carry a prerelease or build.
        raise ValueError("partial version cannot have prerelease/build")

    prerelease = None
    if pre_raw is not None:
        prerelease = _validate_identifiers(pre_raw)
        for part in prerelease:
            if part.isdigit() and len(part) > 1 and part[0] == "0":
                raise ValueError("leading zero in prerelease identifier")

    build = None
    if build_raw is not None:
        build = _validate_identifiers(build_raw)

    return _Partial(major, minor, patch, prerelease, build)


def _parse_version(text):
    partial = _parse_partial(text)
    if partial.major is None or partial.minor is None or partial.patch is None:
        raise ValueError("not a complete version")
    return _Version(
        partial.major,
        partial.minor,
        partial.patch,
        partial.prerelease,
        partial.build,
    )


def _ver(major, minor, patch, prerelease=None):
    return _Version(major, minor, patch, prerelease, None)


def _ge(version):
    return _Comparator(">=", version, False)


def _lt(version):
    return _Comparator("<", version, False)


def _caret_upper(major, minor, patch):
    """Upper bound (exclusive) for a caret range's version parts."""
    if major > 0:
        return _ver(major + 1, 0, 0, ("0",))
    if minor is None:
        return _ver(1, 0, 0, ("0",))
    if minor > 0:
        return _ver(0, minor + 1, 0, ("0",))
    if patch is None:
        return _ver(0, 1, 0, ("0",))
    if patch > 0:
        return _ver(0, 0, patch + 1, ("0",))
    return _ver(0, 0, 1, ("0",))


def _desugar(op, partial):
    """Turn one comparator into a list of primitive comparators.

    Returns ``_IMPOSSIBLE`` for comparators that can never match.
    """
    major = partial.major
    minor = partial.minor
    patch = partial.patch
    prerelease = partial.prerelease

    if major is None:
        # Fully wildcarded partial (``*``, ``x``, ...).
        if op in ("", "=", ">=", "<=", "~", "^"):
            return []
        return _IMPOSSIBLE  # >* and <* match nothing

    if op in ("", "="):
        if patch is None:
            if minor is None:
                return [_ge(_ver(major, 0, 0)), _lt(_ver(major + 1, 0, 0, ("0",)))]
            return [
                _ge(_ver(major, minor, 0)),
                _lt(_ver(major, minor + 1, 0, ("0",))),
            ]
        return [
            _Comparator(
                "=", _ver(major, minor, patch, prerelease), prerelease is not None
            )
        ]

    if op == ">":
        if patch is None:
            if minor is None:
                return [_ge(_ver(major + 1, 0, 0))]
            return [_ge(_ver(major, minor + 1, 0))]
        return [
            _Comparator(
                ">", _ver(major, minor, patch, prerelease), prerelease is not None
            )
        ]

    if op == ">=":
        if patch is None:
            return [_ge(_ver(major, minor or 0, 0))]
        return [
            _Comparator(
                ">=", _ver(major, minor, patch, prerelease), prerelease is not None
            )
        ]

    if op == "<":
        if patch is None:
            if minor is None:
                return [_lt(_ver(major, 0, 0, ("0",)))]
            return [_lt(_ver(major, minor, 0, ("0",)))]
        return [
            _Comparator(
                "<", _ver(major, minor, patch, prerelease), prerelease is not None
            )
        ]

    if op == "<=":
        if patch is None:
            if minor is None:
                return [_lt(_ver(major + 1, 0, 0, ("0",)))]
            return [_lt(_ver(major, minor + 1, 0, ("0",)))]
        return [
            _Comparator(
                "<=", _ver(major, minor, patch, prerelease), prerelease is not None
            )
        ]

    if op == "~":
        if patch is None:
            lower = _ge(_ver(major, minor or 0, 0))
        else:
            lower = _Comparator(
                ">=",
                _ver(major, minor, patch, prerelease),
                prerelease is not None,
            )
        if minor is None:
            upper = _lt(_ver(major + 1, 0, 0, ("0",)))
        else:
            upper = _lt(_ver(major, minor + 1, 0, ("0",)))
        return [lower, upper]

    if op == "^":
        if patch is None:
            lower = _ge(_ver(major, minor or 0, 0))
        else:
            lower = _Comparator(
                ">=",
                _ver(major, minor, patch, prerelease),
                prerelease is not None,
            )
        return [lower, _lt(_caret_upper(major, minor, patch))]

    raise ValueError("unknown operator")


def _split_comparator(token):
    """Split a comparator token into its operator and version part."""
    if token.startswith(">="):
        return ">=", token[2:]
    if token.startswith("<="):
        return "<=", token[2:]
    if token[:1] in ("<", ">", "="):
        return token[0], token[1:]
    if token.startswith("~"):
        return "~", token[1:]
    if token.startswith("^"):
        return "^", token[1:]
    return "", token


def _make_comparator(op, rest):
    """Build comparators for an operator/version pair.

    Returns ``(comparators, impossible)``.
    """
    if rest == "":
        raise ValueError("comparator without version")

    partial = _parse_partial(rest)
    result = _desugar(op, partial)
    if result is _IMPOSSIBLE:
        return [], True
    return result, False


def _hyphen_range(left_text, right_text):
    left = _parse_partial(left_text)
    right = _parse_partial(right_text)

    comparators = []

    if left.major is not None:
        if left.patch is not None:
            comparators.append(
                _Comparator(
                    ">=",
                    _ver(left.major, left.minor, left.patch, left.prerelease),
                    left.prerelease is not None,
                )
            )
        else:
            comparators.append(_ge(_ver(left.major, left.minor or 0, 0)))

    if right.major is not None:
        if right.patch is not None:
            comparators.append(
                _Comparator(
                    "<=",
                    _ver(right.major, right.minor, right.patch, right.prerelease),
                    right.prerelease is not None,
                )
            )
        elif right.minor is None:
            comparators.append(_lt(_ver(right.major + 1, 0, 0, ("0",))))
        else:
            comparators.append(_lt(_ver(right.major, right.minor + 1, 0, ("0",))))

    return comparators


def _parse_set(text):
    """Parse one comparator set.

    Returns a list of comparators, or ``None`` if the set can never match.
    """
    text = text.strip()
    if not text:
        return []

    hyphen = _HYPHEN_RE.match(text)
    if hyphen is not None:
        return _hyphen_range(hyphen.group(1), hyphen.group(2))

    tokens = text.split()
    comparators = []
    impossible = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATORS:
            if index + 1 >= len(tokens):
                raise ValueError("operator without version")
            op = token
            rest = tokens[index + 1]
            index += 2
        else:
            op, rest = _split_comparator(token)
            index += 1

        found, bad = _make_comparator(op, rest)
        if bad:
            impossible = True
        else:
            comparators.extend(found)

    if impossible:
        return None
    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(part) for part in range_.split("||")]


def _set_matches(version, comparators):
    if comparators is None:
        return False
    for comparator in comparators:
        if not comparator.matches(version):
            return False

    if version.prerelease is not None:
        for comparator in comparators:
            target = comparator.version
            if (
                comparator.counts_for_prerelease
                and target.major == version.major
                and target.minor == version.minor
                and target.patch == version.patch
                and target.prerelease is not None
            ):
                return True
        return False

    return True


def satisfies(version, range_):
    parsed_version = _parse_version(version)
    parsed_range = _parse_range(range_)
    return any(_set_matches(parsed_version, item) for item in parsed_range)


def max_satisfying(versions, range_):
    parsed_range = _parse_range(range_)

    best = None
    best_key = None
    for raw in versions:
        if not isinstance(raw, str):
            continue
        try:
            parsed = _parse_version(raw)
        except ValueError:
            continue
        if not any(_set_matches(parsed, item) for item in parsed_range):
            continue
        key = parsed.key()
        # Strictly greater, so ties keep the first string in the list.
        if best_key is None or key > best_key:
            best = raw
            best_key = key
    return best
