"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = r"0|[1-9][0-9]*"
_IDS = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_VERSION_RE = re.compile(rf"({_NUM})\.({_NUM})\.({_NUM})(?:-({_IDS}))?(?:\+{_IDS})?")
_NUM_RE = re.compile(_NUM)
_WILDCARDS = ("*", "x", "X")
_OPERATORS = (">=", "<=", ">", "<", "=", "~", "^")
_COMPARE = {
    "=": operator.eq,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


def _strip_prefix(text):
    text = text.strip()
    return text[1:] if text[:1] in ("v", "=") else text


def _leading_zero(identifier):
    return len(identifier) > 1 and identifier[0] == "0" and identifier.isdigit()


def _key(major, minor, patch, pre=None):
    """Sort key for SemVer precedence; a release sorts above its prereleases."""
    if pre is None:
        return (major, minor, patch, 1, ())
    ids = tuple((0, int(x)) if x.isdigit() else (1, x) for x in pre.split("."))
    return (major, minor, patch, 0, ids)


def _parse_version(text):
    """Return ((major, minor, patch), prerelease) for a full version."""
    match = _VERSION_RE.fullmatch(_strip_prefix(text))
    if match is None:
        raise ValueError(f"invalid version: {text!r}")
    pre = match.group(4)
    if pre is not None and any(_leading_zero(x) for x in pre.split(".")):
        raise ValueError(f"invalid version: {text!r}")
    return tuple(int(match.group(i)) for i in (1, 2, 3)), pre


def _parse_operand(text):
    """Return ((major, minor, patch), prerelease); None marks a wildcard part."""
    if _VERSION_RE.fullmatch(_strip_prefix(text)):
        return _parse_version(text)
    parts = _strip_prefix(text).split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"invalid version: {text!r}")
    values = []
    for part in parts:
        if part in _WILDCARDS:
            values.append(None)
        elif _NUM_RE.fullmatch(part) and None not in values:
            values.append(int(part))
        else:
            raise ValueError(f"invalid version: {text!r}")
    values += [None] * (3 - len(values))
    return tuple(values), None


def _floor(parts):
    return tuple(0 if x is None else x for x in parts)


def _upper_parts(parts):
    """First version past a partial, e.g. 1.2 -> 1.3.0."""
    major, minor, _ = parts
    if minor is None:
        return (major + 1, 0, 0)
    return (major, minor + 1, 0)


def _caret_upper(parts):
    major, minor, patch = parts
    if major:
        return (major + 1, 0, 0)
    if minor is None:
        return (1, 0, 0)
    if minor:
        return (0, minor + 1, 0)
    if patch is None:
        return (0, 1, 0)
    return (0, 0, patch + 1)


def _comparators(op, text):
    """Desugar one comparator into (operator, bound key, marker) triples.

    The marker is the written version's MAJOR.MINOR.PATCH when that version has
    a prerelease tag, and None otherwise.
    """
    op = op or "="
    parts, pre = _parse_operand(text)
    if parts[0] is None:
        if op in ("<", ">"):
            # Nothing is below 0.0.0-0, the lowest possible version.
            return [("<", _key(0, 0, 0, "0"), None)]
        return [(">=", _key(0, 0, 0), None)]
    marker = parts if pre else None
    if op == "~":
        return [(">=", _key(*_floor(parts), pre), marker), ("<", _key(*_upper_parts(parts), "0"), None)]
    if op == "^":
        upper = _caret_upper(parts)
        return [(">=", _key(*_floor(parts), pre), marker), ("<", _key(*upper, "0"), None)]
    if None not in parts:
        return [(op, _key(*parts, pre), marker)]
    lower = _floor(parts)
    upper = _upper_parts(parts)
    if op == "=":
        return [(">=", _key(*lower), None), ("<", _key(*upper, "0"), None)]
    if op == ">":
        return [(">=", _key(*upper), None)]
    if op == ">=":
        return [(">=", _key(*lower), None)]
    if op == "<":
        return [("<", _key(*lower, "0"), None)]
    return [("<", _key(*upper, "0"), None)]


def _hyphen(left, right):
    comparators = _comparators(">=", left)
    if _parse_operand(right)[0][0] is not None:
        comparators += _comparators("<=", right)
    return comparators


def _parse_set(text):
    tokens = text.split()
    merged = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in _OPERATORS:
            # An operator may be separated from its version by spaces.
            if i + 1 == len(tokens):
                raise ValueError(f"invalid range: {text!r}")
            i += 1
            token += tokens[i]
        merged.append(token)
        i += 1

    comparators = []
    i = 0
    while i < len(merged):
        if i + 1 < len(merged) and merged[i + 1] == "-":
            if i + 2 == len(merged):
                raise ValueError(f"invalid range: {text!r}")
            comparators += _hyphen(merged[i], merged[i + 2])
            i += 3
        else:
            op = next((o for o in _OPERATORS if merged[i].startswith(o)), "")
            comparators += _comparators(op, merged[i][len(op):])
            i += 1
    return comparators


def _parse_range(range_):
    return [_parse_set(text) for text in range_.split("||")]


def _matches(parts, pre, sets):
    key = _key(*parts, pre)
    for comparators in sets:
        if not all(_COMPARE[op](key, bound) for op, bound, _ in comparators):
            continue
        # A prerelease only matches if a comparator names that same MAJOR.MINOR.PATCH with a prerelease.
        if pre is None or any(marker == parts for _, _, marker in comparators):
            return True
    return False


def satisfies(version, range_):
    parts, pre = _parse_version(version)
    return _matches(parts, pre, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for version in versions:
        if not isinstance(version, str):
            continue
        try:
            parts, pre = _parse_version(version)
        except ValueError:
            continue
        key = _key(*parts, pre)
        if _matches(parts, pre, sets) and (best_key is None or key > best_key):
            best, best_key = version, key
    return best
