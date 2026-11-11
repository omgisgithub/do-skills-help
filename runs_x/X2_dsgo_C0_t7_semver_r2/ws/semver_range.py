"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_IDENT = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    r"^(" + _NUM + r")\.(" + _NUM + r")\.(" + _NUM + r")"
    r"(?:-(" + _IDENT + r"(?:\." + _IDENT + r")*))?"
    r"(?:\+(" + _IDENT + r"(?:\." + _IDENT + r")*))?$"
)
_PART_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")
_IDENT_RE = re.compile(r"^[0-9A-Za-z-]+$")

_ZERO_PRE = ((0, 0, ""),)


class _Version:
    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(self, major, minor, patch, prerelease=None, build=None):
        self.major = major
        self.minor = minor
        self.patch = patch
        # A tuple of (kind, number, text) keys, or None.  Build metadata is
        # stored for completeness but ignored by every comparison.
        self.prerelease = prerelease
        self.build = build


class _Comparator:
    __slots__ = ("op", "version", "allow_prerelease")

    def __init__(self, op, version, allow_prerelease=False):
        self.op = op
        self.version = version
        self.allow_prerelease = allow_prerelease


def _validate_build(raw):
    if not raw:
        raise ValueError("empty build metadata")
    for part in raw.split("."):
        if not _IDENT_RE.match(part):
            raise ValueError("invalid build metadata")


def _parse_prerelease(raw):
    if not raw:
        raise ValueError("empty prerelease")
    result = []
    for part in raw.split("."):
        if not _IDENT_RE.match(part):
            raise ValueError("invalid prerelease identifier")
        if part.isdigit():
            if len(part) > 1 and part[0] == "0":
                raise ValueError("numeric prerelease identifier has leading zero")
            result.append((0, int(part), ""))
        else:
            result.append((1, 0, part))
    return tuple(result)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    s = text.strip()
    if not s:
        raise ValueError("empty version")
    if s[0] in ("v", "="):
        s = s[1:]
    match = _VERSION_RE.match(s)
    if not match:
        raise ValueError("invalid version: %r" % (text,))
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    pre = match.group(4)
    prerelease = _parse_prerelease(pre) if pre is not None else None
    return _Version(major, minor, patch, prerelease, match.group(5))


def _parse_partial(text):
    """Parse a (possibly partial) version used inside a range."""
    s = text.strip()
    if not s:
        raise ValueError("empty version")
    # The "=" prefix is an operator in ranges, so only "v" is accepted here.
    if s[0] == "v":
        s = s[1:]
    if not s:
        raise ValueError("empty version")
    if s in ("*", "x", "X"):
        return (None, None, None, None)

    build = None
    if "+" in s:
        s, build = s.split("+", 1)
        _validate_build(build)

    prerelease = None
    if "-" in s:
        core, pre = s.split("-", 1)
        prerelease = _parse_prerelease(pre)
    else:
        core = s

    parts = core.split(".")
    if len(parts) > 3:
        raise ValueError("too many version components")

    values = []
    wildcard_seen = False
    for part in parts:
        if part in ("*", "x", "X"):
            wildcard_seen = True
            values.append(None)
        else:
            if not _PART_RE.match(part):
                raise ValueError("invalid version component")
            if wildcard_seen:
                raise ValueError("version component after wildcard")
            values.append(int(part))

    if values and values[0] is None and len(values) > 1:
        raise ValueError("wildcard major version with more components")

    while len(values) < 3:
        values.append(None)
    major, minor, patch = values

    if (prerelease is not None or build is not None) and (
        major is None or minor is None or patch is None
    ):
        raise ValueError("partial versions cannot have prerelease/build")

    return (major, minor, patch, prerelease)


def _v(major, minor, patch, prerelease=None):
    return _Version(major, minor, patch, prerelease)


def _c(op, version, allow_prerelease=False):
    return _Comparator(op, version, allow_prerelease)


def _never():
    # There is no version lower than 0.0.0-0.
    return _c("<", _v(0, 0, 0, _ZERO_PRE))


def _desugar_plain(op, partial):
    major, minor, patch, pre = partial

    if major is None:
        if op in ("", "=", ">=", "<="):
            return [_c(">=", _v(0, 0, 0))]
        return [_never()]

    if minor is None:
        if op in ("", "="):
            return [
                _c(">=", _v(major, 0, 0)),
                _c("<", _v(major + 1, 0, 0, _ZERO_PRE)),
            ]
        if op == ">":
            return [_c(">=", _v(major + 1, 0, 0))]
        if op == ">=":
            return [_c(">=", _v(major, 0, 0))]
        if op == "<":
            return [_c("<", _v(major, 0, 0, _ZERO_PRE))]
        if op == "<=":
            return [_c("<", _v(major + 1, 0, 0, _ZERO_PRE))]

    if patch is None:
        if op in ("", "="):
            return [
                _c(">=", _v(major, minor, 0)),
                _c("<", _v(major, minor + 1, 0, _ZERO_PRE)),
            ]
        if op == ">":
            return [_c(">=", _v(major, minor + 1, 0))]
        if op == ">=":
            return [_c(">=", _v(major, minor, 0))]
        if op == "<":
            return [_c("<", _v(major, minor, 0, _ZERO_PRE))]
        if op == "<=":
            return [_c("<", _v(major, minor + 1, 0, _ZERO_PRE))]

    version = _v(major, minor, patch, pre)
    allow = pre is not None
    if op in ("", "="):
        return [_c("=", version, allow)]
    return [_c(op, version, allow)]


def _desugar_tilde(partial):
    major, minor, patch, pre = partial
    if major is None:
        raise ValueError("tilde requires a version")

    if minor is None:
        lower = _v(major, 0, 0)
        upper = _v(major + 1, 0, 0, _ZERO_PRE)
    else:
        lower = _v(major, minor, patch or 0, pre)
        upper = _v(major, minor + 1, 0, _ZERO_PRE)

    return [
        _c(">=", lower, pre is not None),
        _c("<", upper),
    ]


def _desugar_caret(partial):
    major, minor, patch, pre = partial
    if major is None:
        raise ValueError("caret requires a version")

    lower = _v(major, minor or 0, patch or 0, pre)

    if major != 0:
        upper = _v(major + 1, 0, 0, _ZERO_PRE)
    elif minor is None:
        upper = _v(1, 0, 0, _ZERO_PRE)
    elif minor != 0:
        upper = _v(0, minor + 1, 0, _ZERO_PRE)
    elif patch is None:
        upper = _v(0, 1, 0, _ZERO_PRE)
    else:
        upper = _v(0, 0, patch + 1, _ZERO_PRE)

    return [
        _c(">=", lower, pre is not None),
        _c("<", upper),
    ]


def _desugar_hyphen(left, right):
    comparators = []

    lmajor, lminor, lpatch, lpre = left
    if lmajor is None:
        comparators.append(_c(">=", _v(0, 0, 0)))
    else:
        comparators.append(
            _c(">=", _v(lmajor, lminor or 0, lpatch or 0, lpre), lpre is not None)
        )

    rmajor, rminor, rpatch, rpre = right
    if rmajor is None:
        pass
    elif rminor is None:
        comparators.append(_c("<", _v(rmajor + 1, 0, 0, _ZERO_PRE)))
    elif rpatch is None:
        comparators.append(_c("<", _v(rmajor, rminor + 1, 0, _ZERO_PRE)))
    else:
        comparators.append(
            _c("<=", _v(rmajor, rminor, rpatch, rpre), rpre is not None)
        )

    return comparators


def _parse_comparator_set(text):
    s = text.strip()
    if not s:
        return []

    tokens = s.split()
    if "-" in tokens:
        if len(tokens) != 3 or tokens[1] != "-":
            raise ValueError("invalid hyphen range")
        left = _parse_partial(tokens[0])
        right = _parse_partial(tokens[2])
        return _desugar_hyphen(left, right)

    comparators = []
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break

        op = ""
        for candidate in (">=", "<=", ">", "<", "=", "~", "^"):
            if s.startswith(candidate, i):
                op = candidate
                i += len(candidate)
                break

        while i < n and s[i].isspace():
            i += 1

        j = i
        while j < n and not s[j].isspace():
            j += 1
        token = s[i:j]
        if not token:
            raise ValueError("operator without a version")
        i = j

        partial = _parse_partial(token)
        if op == "~":
            comparators.extend(_desugar_tilde(partial))
        elif op == "^":
            comparators.extend(_desugar_caret(partial))
        else:
            comparators.extend(_desugar_plain(op, partial))

    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_comparator_set(part) for part in range_.split("||")]


def _compare(a, b):
    for attr in ("major", "minor", "patch"):
        av = getattr(a, attr)
        bv = getattr(b, attr)
        if av != bv:
            return -1 if av < bv else 1

    apre = a.prerelease
    bpre = b.prerelease
    if apre is None and bpre is None:
        return 0
    if apre is None:
        return 1
    if bpre is None:
        return -1
    if apre == bpre:
        return 0
    return -1 if apre < bpre else 1


def _test_comparator(comparator, version):
    result = _compare(version, comparator.version)
    op = comparator.op
    if op == "<":
        return result < 0
    if op == "<=":
        return result <= 0
    if op == ">":
        return result > 0
    if op == ">=":
        return result >= 0
    return result == 0


def _matches_set(comparators, version):
    for comparator in comparators:
        if not _test_comparator(comparator, version):
            return False

    if version.prerelease is not None:
        for comparator in comparators:
            allowed = comparator.version
            if (
                comparator.allow_prerelease
                and allowed.prerelease is not None
                and allowed.major == version.major
                and allowed.minor == version.minor
                and allowed.patch == version.patch
            ):
                return True
        return False

    return True


def satisfies(version, range_):
    parsed_version = _parse_version(version)
    sets = _parse_range(range_)
    return any(_matches_set(comparators, parsed_version) for comparators in sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_version = None
    for item in versions:
        try:
            parsed = _parse_version(item)
        except ValueError:
            continue
        if any(_matches_set(comparators, parsed) for comparators in sets):
            if best is None or _compare(parsed, best_version) > 0:
                best = item
                best_version = parsed
    return best
