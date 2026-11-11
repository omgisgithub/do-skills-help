"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

# Term: MAJOR[.MINOR[.PATCH]][-PRE][+BUILD], where a part may be a wildcard (x, X, *).
# Whether the term is a valid full version or a partial version is checked in _parse_term.
_TERM_RE = re.compile(
    r"(0|[1-9][0-9]*|[xX*])"
    r"(?:\.(0|[1-9][0-9]*|[xX*])(?:\.(0|[1-9][0-9]*|[xX*]))?)?"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
_OPERATOR_ONLY = frozenset(["<", "<=", ">", ">=", "=", "~", "^"])
_OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}

# Pre-release key for "no prerelease": sorts above every prerelease of the same core version.
_RELEASE = (1,)
# Pre-release key for "-0": sorts below every prerelease of the same core version.
_LOWEST_PRE = (0, ((0, 0),))
# Comparator that matches nothing: nothing sorts below 0.0.0-0.
_NEVER = ("<", (0, 0, 0, _LOWEST_PRE), None)


def _rel(major, minor=0, patch=0):
    return (major, minor, patch, _RELEASE)


def _low(major, minor=0, patch=0):
    return (major, minor, patch, _LOWEST_PRE)


def _key(parts, pre):
    if pre is None:
        pre_key = _RELEASE
    else:
        pre_key = (0, tuple((0, int(i)) if i.isdigit() else (1, i) for i in pre.split(".")))
    return (*parts, pre_key)


def _parse_term(text):
    """Parse a version or partial version without a leading v/=. Returns (parts, pre, build).

    parts is a tuple of three entries, None for a missing or wildcard part.
    """
    m = _TERM_RE.fullmatch(text)
    if m is None:
        raise ValueError(f"invalid version: {text!r}")
    major, minor, patch, pre, build = m.groups()
    parts = tuple(None if p is None or p in ("x", "X", "*") else int(p) for p in (major, minor, patch))

    seen_wildcard = False
    for p in parts:
        if p is None:
            seen_wildcard = True
        elif seen_wildcard:
            raise ValueError(f"invalid version: {text!r}")

    partial = None in parts
    if partial and (pre is not None or build is not None):
        raise ValueError(f"partial version cannot have prerelease or build: {text!r}")
    if pre is not None:
        for ident in pre.split("."):
            if ident.isdigit() and len(ident) > 1 and ident[0] == "0":
                raise ValueError(f"leading zero in prerelease: {text!r}")
    return parts, pre, build


def _parse_term_text(text):
    if text[:1] == "v":
        text = text[1:]
    return _parse_term(text)


def _parse_version(text):
    """Parse a full version. Returns (precedence key, (major, minor, patch))."""
    if not isinstance(text, str):
        raise ValueError(f"invalid version: {text!r}")
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    parts, pre, _ = _parse_term(s)
    if None in parts:
        raise ValueError(f"not a full version: {text!r}")
    return _key(parts, pre), parts


def _expand_partial(op, parts):
    """Desugar a comparator with a partial version (fewer than three numeric parts)."""
    major, minor, patch = (p or 0 for p in parts)
    n = sum(p is not None for p in parts)
    if n == 0:
        return [_NEVER] if op in ("<", ">") else [(">=", _rel(0), None)]

    lo_rel = _rel(major, minor, patch)
    lo_low = _low(major, minor, patch)
    if n == 1:
        hi_rel, hi_low = _rel(major + 1), _low(major + 1)
    else:
        hi_rel, hi_low = _rel(major, minor + 1), _low(major, minor + 1)

    if op in ("", "="):
        return [(">=", lo_rel, None), ("<", hi_low, None)]
    if op == ">=":
        return [(">=", lo_rel, None)]
    if op == ">":
        return [(">=", hi_rel, None)]
    if op == "<":
        return [("<", lo_low, None)]
    return [("<", hi_low, None)]  # "<="


def _expand_tilde(parts, pre):
    major, minor, patch = (p or 0 for p in parts)
    n = sum(p is not None for p in parts)
    if n == 0:
        return [(">=", _rel(0), None)]
    base = parts if pre is not None else None
    hi = _low(major + 1) if n == 1 else _low(major, minor + 1)
    return [(">=", _key((major, minor, patch), pre), base), ("<", hi, None)]


def _expand_caret(parts, pre):
    major, minor, patch = (p or 0 for p in parts)
    n = sum(p is not None for p in parts)
    if n == 0:
        return [(">=", _rel(0), None)]
    base = parts if pre is not None else None
    if major > 0:
        hi = _low(major + 1)
    elif n == 1:
        hi = _low(1)
    elif minor > 0:
        hi = _low(0, minor + 1)
    elif n == 2:
        hi = _low(0, 1)
    else:
        hi = _low(0, 0, patch + 1)
    return [(">=", _key((major, minor, patch), pre), base), ("<", hi, None)]


def _expand(op, term):
    """Desugar one comparator into (operator, bound key, base) tuples.

    base is the (major, minor, patch) of a version written with a prerelease, used by the
    prerelease rule; it is None for everything else, including generated upper bounds.
    """
    parts, pre, _ = term
    if op == "~":
        return _expand_tilde(parts, pre)
    if op == "^":
        return _expand_caret(parts, pre)
    if None in parts:
        return _expand_partial(op, parts)
    base = parts if pre is not None else None
    return [(op or "=", _key(parts, pre), base)]


def _parse_bare(token):
    if token[0] in "<>=~^":
        raise ValueError(f"unexpected operator in hyphen range: {token!r}")
    return _parse_term_text(token)


def _parse_comparator(token):
    m = re.match(r"(<=|>=|<|>|=|~|\^)?(.*)", token, re.DOTALL)
    op = m.group(1) or ""
    return _expand(op, _parse_term_text(m.group(2)))


def _parse_set(text):
    """Parse one comparator set into a list of (operator, bound key, base) tuples."""
    raw = text.split()
    tokens = []
    i = 0
    while i < len(raw):
        token = raw[i]
        i += 1
        if token in _OPERATOR_ONLY:
            if i >= len(raw):
                raise ValueError(f"operator without version: {text!r}")
            token += raw[i]
            i += 1
        tokens.append(token)

    comparators = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError(f"incomplete hyphen range: {text!r}")
            low = _parse_bare(tokens[i])
            high = _parse_bare(tokens[i + 2])
            comparators += _expand(">=", low) + _expand("<=", high)
            i += 3
        else:
            comparators += _parse_comparator(tokens[i])
            i += 1
    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_parse_set(s) for s in range_.split("||")]


def _satisfies_set(key, mmp, comparators):
    # Prerelease rule: a prerelease version needs a comparator written with the same
    # major.minor.patch and its own prerelease tag.
    if key[3] != _RELEASE:
        if not any(base is not None and base == mmp for _, _, base in comparators):
            return False
    return all(_OPS[op](key, bound) for op, bound, _ in comparators)


def satisfies(version, range_):
    key, mmp = _parse_version(version)
    sets = _parse_range(range_)
    return any(_satisfies_set(key, mmp, s) for s in sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for candidate in versions:
        try:
            key, mmp = _parse_version(candidate)
        except ValueError:
            continue
        if not any(_satisfies_set(key, mmp, s) for s in sets):
            continue
        if best_key is None or key > best_key:
            best, best_key = candidate, key
    return best
