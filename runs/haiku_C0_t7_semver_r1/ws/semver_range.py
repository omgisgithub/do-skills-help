"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = r"0|[1-9][0-9]*"
_IDENT = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    r"(" + _NUM + r")\.(" + _NUM + r")\.(" + _NUM + r")"
    r"(?:-(" + _IDENT + r"(?:\." + _IDENT + r")*))?"
    r"(?:\+" + _IDENT + r"(?:\." + _IDENT + r")*)?"
)
_PARTIAL_RE = re.compile(r"(?:" + _NUM + r"|[xX*])(?:\.(?:" + _NUM + r"|[xX*])){0,2}")
_COMPARATOR_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.*)")
_OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}

# Release tag and the "-0" prerelease tag used by generated upper bounds.
_REL = (1,)
_ZERO_PRE = (0, ((0, 0),))
_ZERO = (0, 0, 0, _REL)
_NOTHING = (0, 0, 0, _ZERO_PRE)


def _prerelease_key(pre):
    if pre is None:
        return _REL
    ids = []
    for ident in pre.split("."):
        if ident.isdigit():
            if len(ident) > 1 and ident[0] == "0":
                raise ValueError(f"leading zero in prerelease: {pre!r}")
            ids.append((0, int(ident)))
        else:
            ids.append((1, ident))
    return (0, tuple(ids))


def _full_key(body):
    m = _FULL_RE.fullmatch(body)
    if m is None:
        raise ValueError(f"invalid version: {body!r}")
    major, minor, patch, pre = m.groups()
    return (int(major), int(minor), int(patch), _prerelease_key(pre))


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError(f"invalid version: {text!r}")
    body = text.strip()
    if body[:1] in ("v", "="):
        body = body[1:]
    return _full_key(body)


def _parse_operand(text):
    """Return (key, parts): key is set for a full version, parts is [M, m, p] with None for wildcards."""
    body = text[1:] if text[:1] == "v" else text
    if _FULL_RE.fullmatch(body):
        key = _full_key(body)
        return key, list(key[:3])
    if _PARTIAL_RE.fullmatch(body):
        parts = [None if p in ("x", "X", "*") else int(p) for p in body.split(".")]
        parts += [None] * (3 - len(parts))
        for i, p in enumerate(parts):
            if p is None and any(q is not None for q in parts[i + 1:]):
                raise ValueError(f"invalid partial version: {text!r}")
        return None, parts
    raise ValueError(f"invalid version: {text!r}")


def _anchor(key):
    """MAJOR.MINOR.PATCH of a prerelease version, else None."""
    return key[:3] if key is not None and key[3][0] == 0 else None


def _below(key):
    """The `-0` form of a release triple, e.g. 1.3.0 -> 1.3.0-0."""
    return key[:3] + (_ZERO_PRE,)


def _zero_fill(parts):
    return (parts[0] or 0, parts[1] or 0, parts[2] or 0, _REL)


def _bump(parts):
    """Exclusive upper bound implied by a partial (or full) version's last given part."""
    major, minor, _ = parts
    if major is None:
        return None
    if minor is None:
        return (major + 1, 0, 0, _REL)
    return (major, minor + 1, 0, _REL)


def _caret_upper(parts):
    major, minor, patch = parts
    if major > 0 or minor is None:
        return (major + 1, 0, 0, _REL)
    if minor > 0 or patch is None:
        return (0, minor + 1, 0, _REL)
    return (0, 0, patch + 1, _REL)


def _comparators(op, text):
    """Desugar one `op operand` into a list of (op, key, anchor) bounds."""
    key, parts = _parse_operand(text)
    major = parts[0]
    anchor = _anchor(key)
    if major is None:
        if op in ("~", "^"):
            raise ValueError(f"invalid range operand: {text!r}")
        if op in ("<", ">"):
            return [("<", _NOTHING, None)]
        return [(">=", _ZERO, None)]

    lo = key if key is not None else _zero_fill(parts)
    if op in ("~", "^"):
        upper = _bump(parts) if op == "~" else _caret_upper(parts)
        return [(">=", lo, anchor), ("<", _below(upper), None)]
    if op in ("", "="):
        if key is not None:
            return [("=", key, anchor)]
        return [(">=", lo, None), ("<", _below(_bump(parts)), None)]
    if op == ">":
        if key is not None:
            return [(">", key, anchor)]
        return [(">=", _bump(parts), None)]
    if op == ">=":
        return [(">=", lo, anchor)]
    if op == "<":
        if key is not None:
            return [("<", key, anchor)]
        return [("<", _below(lo), None)]
    if key is not None:  # "<="
        return [("<=", key, anchor)]
    return [("<", _below(_bump(parts)), None)]


def _hyphen(left, right):
    lkey, lparts = _parse_operand(left)
    rkey, rparts = _parse_operand(right)
    lo = lkey if lkey is not None else _zero_fill(lparts)
    bounds = [(">=", lo, _anchor(lkey))]
    if rkey is not None:
        bounds.append(("<=", rkey, _anchor(rkey)))
    elif rparts[0] is not None:
        bounds.append(("<", _below(_bump(rparts)), None))
    return bounds


def _parse_set(text):
    # Glue an operator to its operand (">= 1.2" -> ">=1.2") and split on whitespace.
    tokens = re.sub(r"(<=|>=|<|>|=|~|\^)\s+", r"\1", text).split()
    bounds = []
    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens) and tokens[i + 1] == "-":
            bounds += _hyphen(tokens[i], tokens[i + 2])
            i += 3
            continue
        m = _COMPARATOR_RE.fullmatch(tokens[i])
        op, operand = m.group(1) or "", m.group(2)
        if not operand:
            raise ValueError(f"invalid comparator: {tokens[i]!r}")
        bounds += _comparators(op, operand)
        i += 1
    return bounds


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_parse_set(part) for part in range_.split("||")]


def _match_set(bounds, key):
    if not all(_OPS[op](key, bound) for op, bound, _ in bounds):
        return False
    if _anchor(key) is None:
        return True
    # A prerelease only matches if some bound was written with a prerelease on the same triple.
    return any(anchor == key[:3] for _, _, anchor in bounds if anchor is not None)


def satisfies(version, range_):
    key = _parse_version(version)
    return any(_match_set(bounds, key) for bounds in _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            key = _parse_version(text)
        except ValueError:
            continue
        if best_key is not None and key <= best_key:
            continue
        if any(_match_set(bounds, key) for bounds in sets):
            best, best_key = text, key
    return best
