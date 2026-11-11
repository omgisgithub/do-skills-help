"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_IDENT = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_VERSION_RE = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(" + _IDENT + r"(?:\." + _IDENT + r")*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
_PART_RE = re.compile(r"[xX*]|0|[1-9][0-9]*")
_COMPARATOR_RE = re.compile(r"(<=|>=|<|>|=)?(.*)", re.S)
_OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}
_ZERO = ((0, 0),)  # the "-0" prerelease used for upper bounds


def _pre_key(pre):
    return tuple((0, int(i)) if i.isdigit() else (1, i) for i in pre.split("."))


def _key(major, minor, patch, pre=None):
    if pre is None:
        return (major, minor, patch, 1, ())
    return (major, minor, patch, 0, pre)


def _strip_v(text):
    return text[1:] if text[:1] == "v" else text


def _operand(text):
    """Parse a version or partial version with no operator. Returns (parts, pre)."""
    m = _VERSION_RE.fullmatch(text)
    if m:
        return [int(m[1]), int(m[2]), int(m[3])], (_pre_key(m[4]) if m[4] else None)
    parts = text.split(".")
    if len(parts) > 3 or not all(_PART_RE.fullmatch(p) for p in parts):
        raise ValueError(f"invalid version: {text!r}")
    values = [None if p in ("x", "X", "*") else int(p) for p in parts]
    values += [None] * (3 - len(values))
    for i in range(2):
        if values[i] is None and values[i + 1] is not None:
            raise ValueError(f"invalid version: {text!r}")
    return values, None


def _version(text):
    text = text.strip()
    if text[:1] in ("v", "="):
        text = text[1:]
    parts, pre = _operand(text)
    if parts[2] is None:
        raise ValueError(f"invalid version: {text!r}")
    return parts, pre


def _bound(op, key, anchor=None):
    return (lambda v: _OPS[op](v, key)), anchor


def _partial_hi(parts):
    major, minor, _ = parts
    return (major + 1, 0, 0) if minor is None else (major, minor + 1, 0)


def _full(op, parts, pre):
    anchor = tuple(parts) if pre else None
    return [_bound(op, _key(*parts, pre), anchor)]


def _partial(op, parts):
    if parts[0] is None:
        return [(lambda v: False, None)] if op in (">", "<") else []
    lo = _key(parts[0], parts[1] or 0, 0)
    hi = _partial_hi(parts)
    if op == "=":
        return [_bound(">=", lo), _bound("<", _key(*hi, _ZERO))]
    if op == ">":
        return [_bound(">=", _key(*hi))]
    if op == ">=":
        return [_bound(">=", lo)]
    if op == "<":
        return [_bound("<", _key(parts[0], parts[1] or 0, 0, _ZERO))]
    return [_bound("<", _key(*hi, _ZERO))]  # "<="


def _tilde_caret(kind, parts, pre):
    major, minor, patch = parts
    if major is None:
        raise ValueError(f"invalid range: {kind}")
    lo = _key(major, minor or 0, patch or 0, pre)
    anchor = tuple(parts) if pre else None
    if kind == "~":
        hi = _partial_hi(parts)
    elif major > 0 or minor is None:
        hi = (major + 1, 0, 0)
    elif minor > 0 or patch is None:
        hi = (0, minor + 1, 0)
    else:
        hi = (0, 0, patch + 1)
    return [_bound(">=", lo, anchor), _bound("<", _key(*hi, _ZERO))]


def _hyphen(left, right):
    lparts, lpre = _operand(_strip_v(left))
    rparts, rpre = _operand(_strip_v(right))
    lo = _key(lparts[0] or 0, lparts[1] or 0, lparts[2] or 0, lpre)
    lanchor = tuple(lparts) if lpre else None
    comparators = [_bound(">=", lo, lanchor)]
    if rparts[0] is None:
        return comparators
    if rparts[2] is None:
        comparators.append(_bound("<", _key(*_partial_hi(rparts), _ZERO)))
    else:
        ranchor = tuple(rparts) if rpre else None
        comparators.append(_bound("<=", _key(*rparts, rpre), ranchor))
    return comparators


def _comparator(token):
    if token[:1] in ("~", "^"):
        parts, pre = _operand(_strip_v(token[1:]))
        return _tilde_caret(token[0], parts, pre)
    op, text = _COMPARATOR_RE.fullmatch(token).groups()
    parts, pre = _operand(_strip_v(text))
    op = op or "="
    if parts[2] is None:
        return _partial(op, parts)
    return _full(op, parts, pre)


def _parse_set(text):
    tokens = text.split()
    comparators = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError(f"invalid hyphen range: {text!r}")
            comparators += _hyphen(tokens[i], tokens[i + 2])
            i += 3
        elif tokens[i] in ("<", "<=", ">", ">=", "=") and i + 1 < len(tokens):
            comparators += _comparator(tokens[i] + tokens[i + 1])
            i += 2
        else:
            comparators += _comparator(tokens[i])
            i += 1
    return comparators


def _parse_range(range_):
    return [_parse_set(text) for text in range_.split("||")]


def _satisfies_set(comparators, parts, pre):
    key = _key(*parts, pre)
    if not all(test(key) for test, _ in comparators):
        return False
    return pre is None or any(anchor == tuple(parts) for _, anchor in comparators)


def satisfies(version, range_):
    parts, pre = _version(version)
    return any(_satisfies_set(s, parts, pre) for s in _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best, best_key = None, None
    for text in versions:
        if not isinstance(text, str):
            continue
        try:
            parts, pre = _version(text)
        except ValueError:
            continue
        key = _key(*parts, pre)
        if best_key is not None and key <= best_key:
            continue
        if any(_satisfies_set(s, parts, pre) for s in sets):
            best, best_key = text, key
    return best
