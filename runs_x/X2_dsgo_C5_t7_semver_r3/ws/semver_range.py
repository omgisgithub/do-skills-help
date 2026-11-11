"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_IDENT = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    r"^([0-9]+)\.([0-9]+)\.([0-9]+)"
    r"(?:-(" + _IDENT + r"(?:\." + _IDENT + r")*))?"
    r"(?:\+(" + _IDENT + r"(?:\." + _IDENT + r")*))?$"
)
_NUM_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")
_HYPHEN_RE = re.compile(r"^(\S+)\s+-\s+(\S+)$")
_COMP_RE = re.compile(r"\s*(>=|<=|>|<|=|~|\^)?\s*(\S+)")
_WILDCARDS = frozenset(("*", "x", "X"))


class _Version:
    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(self, major, minor, patch, prerelease=None, build=()):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease
        self.build = build


class _Partial:
    """A parsed (possibly partial) version, with wildcards replaced by zeros."""

    __slots__ = ("vals", "k", "pre", "full")

    def __init__(self, vals, k, pre, full):
        self.vals = vals
        self.k = k
        self.pre = pre
        self.full = full


class _Comparator:
    __slots__ = ("op", "version", "written_pre")

    def __init__(self, op, version, written_pre=False):
        self.op = op
        self.version = version
        self.written_pre = written_pre


def _parse_identifiers(text, allow_numeric_leading_zeros=False):
    identifiers = text.split(".")
    result = []
    for ident in identifiers:
        if not ident:
            raise ValueError("empty identifier")
        if (
            not allow_numeric_leading_zeros
            and ident.isdigit()
            and len(ident) > 1
            and ident[0] == "0"
        ):
            raise ValueError("leading zero in numeric prerelease identifier")
        result.append(ident)
    return tuple(result)


def _parse_full_version(text):
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    match = _FULL_RE.match(s)
    if not match:
        raise ValueError("invalid version: %r" % (text,))
    major_s, minor_s, patch_s, pre_s, build_s = match.groups()
    for number in (major_s, minor_s, patch_s):
        if len(number) > 1 and number[0] == "0":
            raise ValueError("leading zero in version")
    prerelease = _parse_identifiers(pre_s) if pre_s else None
    build = _parse_identifiers(build_s, True) if build_s else ()
    return _Version(
        int(major_s), int(minor_s), int(patch_s), prerelease, build
    )


def _parse_partial(token):
    if not isinstance(token, str):
        raise ValueError("version must be a string")
    s = token.strip()
    if s[:1] == "v":
        s = s[1:]
    if not s:
        raise ValueError("empty version")
    if s[:1] == "=":
        raise ValueError("invalid partial version: %r" % (token,))

    if "-" in s or "+" in s:
        version = _parse_full_version(s)
        return _Partial(
            [version.major, version.minor, version.patch],
            3,
            version.prerelease,
            True,
        )

    pieces = s.split(".")
    if not 1 <= len(pieces) <= 3:
        raise ValueError("invalid partial version: %r" % (token,))

    parts = []
    seen_wildcard = False
    for piece in pieces:
        if piece in _WILDCARDS:
            parts.append(None)
            seen_wildcard = True
        else:
            if seen_wildcard or not _NUM_RE.match(piece):
                raise ValueError("invalid partial version: %r" % (token,))
            parts.append(int(piece))

    n = len(parts)
    k = parts.index(None) if seen_wildcard else n
    vals = [0, 0, 0]
    for i in range(k):
        vals[i] = parts[i]
    return _Partial(vals, k, None, k == 3)


def _incremented(vals, index):
    out = list(vals)
    out[index] += 1
    for i in range(index + 1, 3):
        out[i] = 0
    return out


def _zero_version():
    return _Version(0, 0, 0)


def _desugar_tilde(p):
    if p.k == 0:
        return [_Comparator(">=", _zero_version())]
    lower = _Version(*p.vals, p.pre)
    if p.k == 1:
        upper = _Version(p.vals[0] + 1, 0, 0, ("0",))
    else:
        upper = _Version(p.vals[0], p.vals[1] + 1, 0, ("0",))
    return [
        _Comparator(">=", lower, p.pre is not None),
        _Comparator("<", upper),
    ]


def _desugar_caret(p):
    if p.k == 0:
        return [_Comparator(">=", _zero_version())]
    lower = _Version(*p.vals, p.pre)
    a, b, c = p.vals
    if p.k == 1:
        upper = _Version(a + 1, 0, 0, ("0",))
    elif p.k == 2:
        if a != 0:
            upper = _Version(a + 1, 0, 0, ("0",))
        elif b != 0:
            upper = _Version(0, b + 1, 0, ("0",))
        else:
            upper = _Version(0, 1, 0, ("0",))
    else:
        if a != 0:
            upper = _Version(a + 1, 0, 0, ("0",))
        elif b != 0:
            upper = _Version(0, b + 1, 0, ("0",))
        else:
            upper = _Version(0, 0, c + 1, ("0",))
    return [
        _Comparator(">=", lower, p.pre is not None),
        _Comparator("<", upper),
    ]


def _desugar(token, op):
    p = _parse_partial(token)

    if op == "~":
        return _desugar_tilde(p)
    if op == "^":
        return _desugar_caret(p)

    if p.k == 0:
        # A bare wildcard (or one with >= / <= / =) matches everything.
        if op in (">", "<"):
            return None
        return [_Comparator(">=", _zero_version())]

    if p.full:
        version = _Version(*p.vals, p.pre)
        if op in ("", "="):
            return [_Comparator("=", version, p.pre is not None)]
        return [_Comparator(op, version, p.pre is not None)]

    # Partial version with an X-range style desugaring.
    if op in ("", "="):
        lower = _Version(*p.vals)
        upper = _Version(*_incremented(p.vals, p.k - 1), ("0",))
        return [_Comparator(">=", lower), _Comparator("<", upper)]
    if op == ">=":
        return [_Comparator(">=", _Version(*p.vals))]
    if op == ">":
        return [_Comparator(">=", _Version(*_incremented(p.vals, p.k - 1)))]
    if op == "<":
        return [_Comparator("<", _Version(*p.vals, ("0",)))]
    if op == "<=":
        upper = _Version(*_incremented(p.vals, p.k - 1), ("0",))
        return [_Comparator("<", upper)]
    raise ValueError("invalid operator")


def _desugar_hyphen(left, right):
    lp = _parse_partial(left)
    rp = _parse_partial(right)
    comparators = []

    if lp.k == 0:
        comparators.append(_Comparator(">=", _zero_version()))
    else:
        comparators.append(
            _Comparator(">=", _Version(*lp.vals, lp.pre), lp.pre is not None)
        )

    if rp.k != 0:
        if rp.full:
            comparators.append(
                _Comparator("<=", _Version(*rp.vals, rp.pre), rp.pre is not None)
            )
        else:
            upper = _Version(*_incremented(rp.vals, rp.k - 1), ("0",))
            comparators.append(_Comparator("<", upper))
    return comparators


def _parse_set(text):
    s = text.strip()
    if not s:
        return []

    hyphen = _HYPHEN_RE.match(s)
    if hyphen:
        return _desugar_hyphen(hyphen.group(1), hyphen.group(2))

    comparators = []
    pos = 0
    while pos < len(s):
        match = _COMP_RE.match(s, pos)
        if not match:
            raise ValueError("invalid comparator set: %r" % (text,))
        op = match.group(1) or ""
        token = match.group(2)
        desugared = _desugar(token, op)
        if desugared is None:
            return None
        comparators.extend(desugared)
        pos = match.end()
    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(part) for part in range_.split("||")]


def _compare_prerelease(a, b):
    if a is None and b is None:
        return 0
    if a is None:
        return 1
    if b is None:
        return -1
    for x, y in zip(a, b):
        if x == y:
            continue
        x_numeric = x.isdigit()
        y_numeric = y.isdigit()
        if x_numeric and y_numeric:
            xi, yi = int(x), int(y)
            if xi != yi:
                return -1 if xi < yi else 1
        elif x_numeric:
            return -1
        elif y_numeric:
            return 1
        else:
            return -1 if x < y else 1
    if len(a) == len(b):
        return 0
    return -1 if len(a) < len(b) else 1


def _compare_versions(a, b):
    if a.major != b.major:
        return -1 if a.major < b.major else 1
    if a.minor != b.minor:
        return -1 if a.minor < b.minor else 1
    if a.patch != b.patch:
        return -1 if a.patch < b.patch else 1
    return _compare_prerelease(a.prerelease, b.prerelease)


def _matches(comparator, version):
    relation = _compare_versions(version, comparator.version)
    op = comparator.op
    if op == "=":
        return relation == 0
    if op == "<":
        return relation < 0
    if op == "<=":
        return relation <= 0
    if op == ">":
        return relation > 0
    if op == ">=":
        return relation >= 0
    return False


def _set_satisfies(version, comparators):
    if comparators is None:
        return False
    for comparator in comparators:
        if not _matches(comparator, version):
            return False
    if version.prerelease is not None:
        for comparator in comparators:
            other = comparator.version
            if (
                comparator.written_pre
                and other.major == version.major
                and other.minor == version.minor
                and other.patch == version.patch
            ):
                return True
        return False
    return True


def _satisfies_parsed(version, sets):
    return any(_set_satisfies(version, comparators) for comparators in sets)


def satisfies(version, range_):
    parsed_version = _parse_full_version(version)
    parsed_range = _parse_range(range_)
    return _satisfies_parsed(parsed_version, parsed_range)


def max_satisfying(versions, range_):
    parsed_range = _parse_range(range_)
    best_text = None
    best_version = None
    for entry in versions:
        try:
            candidate = _parse_full_version(entry)
        except (ValueError, TypeError, AttributeError):
            continue
        if _satisfies_parsed(candidate, parsed_range):
            if best_version is None or _compare_versions(candidate, best_version) > 0:
                best_text = entry
                best_version = candidate
    return best_text
