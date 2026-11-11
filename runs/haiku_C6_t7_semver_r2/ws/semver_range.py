"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    rf"({_NUM})\.({_NUM})\.({_NUM})"
    rf"(?:-({_PRE_ID}(?:\.{_PRE_ID})*))?"
    rf"(?:\+{_BUILD_ID}(?:\.{_BUILD_ID})*)?"
)
_NUM_RE = re.compile(_NUM)

_OPERATORS = ("<=", ">=", "<", ">", "=", "~", "^")
_WILDCARDS = ("x", "X", "*")

_CMP = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
    "never": lambda key, bound: False,
}


def _pre_key(identifier):
    if identifier.isdigit():
        return (0, int(identifier), "")
    return (1, 0, identifier)


def _key(major, minor, patch, pre=()):
    # A release (no prerelease) sorts above every prerelease of the same version.
    pre_key = (0, tuple(_pre_key(i) for i in pre)) if pre else (1, ())
    return (major, minor, patch, pre_key)


def _is_prerelease(key):
    return key[3][0] == 0


def _parse_xversion(text):
    """Parse a full or partial version. Returns (parts, pre); wildcards are None."""
    if text[:1] in ("v", "="):
        text = text[1:]
    match = _FULL_RE.fullmatch(text)
    if match:
        pre = tuple(match.group(4).split(".")) if match.group(4) else ()
        return [int(g) for g in match.group(1, 2, 3)], pre

    fields = text.split(".")
    if len(fields) > 3:
        raise ValueError(f"invalid version: {text!r}")
    parts = []
    for field in fields:
        if _NUM_RE.fullmatch(field):
            parts.append(int(field))
        elif field in _WILDCARDS:
            parts.append(None)
        else:
            raise ValueError(f"invalid version: {text!r}")
    if None in parts:
        first = parts.index(None)
        if (first == 0 and len(parts) > 1) or any(p is not None for p in parts[first:]):
            raise ValueError(f"invalid version: {text!r}")
    parts += [None] * (3 - len(parts))
    return parts, ()


def _describe(text):
    """Return (specified, low, pre): leading parts given, zero-filled version, prerelease."""
    parts, pre = _parse_xversion(text)
    specified = sum(p is not None for p in parts)
    low = [p or 0 for p in parts]
    return specified, low, pre


def _bump(low, index, synthetic=False):
    """Version with the part at `index` incremented and the parts after it zeroed.

    `synthetic` adds the `-0` prerelease used for upper bounds.
    """
    bumped = low[:index] + [low[index] + 1] + [0] * (2 - index)
    return _key(*bumped, ("0",) if synthetic else ())


def _mmp(low, pre):
    # MAJOR.MINOR.PATCH of a comparator written with its own prerelease tag, else None.
    return tuple(low) if pre else None


def _comparators(op, text):
    """Desugar one comparator into (operator, bound_key, mmp) triples."""
    n, low, pre = _describe(text)
    if not op:
        op = "="
    if n == 0:
        if op in ("<", ">"):
            return [("never", None, None)]
        if op in ("=", ">=", "<="):
            return [(">=", _key(0, 0, 0), None)]
        raise ValueError(f"invalid comparator: {op}{text!r}")
    if op in ("~", "^"):
        if op == "~":
            index = min(n, 2) - 1
        else:
            # Caret keeps the left-most non-zero part fixed.
            index = next((i for i in range(n) if low[i]), n - 1)
        return [(">=", _key(*low, pre), _mmp(low, pre)), ("<", _bump(low, index, True), None)]
    if n == 3:
        return [(op, _key(*low, pre), _mmp(low, pre))]
    if op == "=":
        return [(">=", _key(*low), None), ("<", _bump(low, n - 1, True), None)]
    if op == ">":
        return [(">=", _bump(low, n - 1), None)]
    if op == ">=":
        return [(">=", _key(*low), None)]
    if op == "<":
        return [("<", _key(*low, ("0",)), None)]
    return [("<", _bump(low, n - 1, True), None)]


def _hyphen(left, right):
    """Desugar `left - right` into comparator triples."""
    n, low, pre = _describe(left)
    comparators = [(">=", _key(*low, pre), _mmp(low, pre))]
    rn, rlow, rpre = _describe(right)
    if rn == 3:
        comparators.append(("<=", _key(*rlow, rpre), _mmp(rlow, rpre)))
    elif rn:
        comparators.append(("<", _bump(rlow, rn - 1, True), None))
    return comparators


def _parse_set(text):
    items = []
    raw = text.split()
    i = 0
    while i < len(raw):
        token = raw[i]
        if token in _OPERATORS:
            if i + 1 >= len(raw) or raw[i + 1] in _OPERATORS or raw[i + 1] == "-":
                raise ValueError(f"invalid comparator set: {text!r}")
            token += raw[i + 1]
            i += 1
        items.append(token)
        i += 1

    comparators = []
    i = 0
    while i < len(items):
        if i + 2 < len(items) and items[i + 1] == "-":
            comparators += _hyphen(items[i], items[i + 2])
            i += 3
        else:
            op = next((o for o in _OPERATORS if items[i].startswith(o)), "")
            comparators += _comparators(op, items[i][len(op):])
            i += 1
    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_parse_set(text) for text in range_.split("||")]


def _parse_version(version):
    if not isinstance(version, str):
        raise ValueError(f"invalid version: {version!r}")
    n, low, pre = _describe(version.strip())
    if n != 3:
        raise ValueError(f"invalid version: {version!r}")
    return _key(*low, pre)


def _set_matches(comparators, key):
    if not all(_CMP[op](key, bound) for op, bound, _ in comparators):
        return False
    if _is_prerelease(key):
        return any(mmp == key[:3] for _, _, mmp in comparators if mmp is not None)
    return True


def _range_matches(sets, key):
    return any(_set_matches(s, key) for s in sets)


def satisfies(version, range_):
    key = _parse_version(version)
    return _range_matches(_parse_range(range_), key)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            key = _parse_version(text)
        except ValueError:
            continue
        if not _range_matches(sets, key):
            continue
        if best_key is None or key > best_key:
            best, best_key = text, key
    return best
