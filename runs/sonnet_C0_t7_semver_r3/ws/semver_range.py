"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BLD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    r"^(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?$"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BLD_ID, _BLD_ID)
)
_X = r"(?:[xX*]|%s)" % _NUM
_PARTIAL_RE = re.compile(r"^v?(%s)(?:\.(%s)(?:\.(%s))?)?$" % (_X, _X, _X))
_OP_RE = re.compile(r"^(<=|>=|<|>|=|~|\^)?(.*)$", re.S)

_LOWEST = (0, 0, 0, ())


def _pre_key(pre):
    return tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre)


def _cmp_key(v):
    major, minor, patch, pre = v
    return (major, minor, patch, 0 if pre else 1, _pre_key(pre))


def _parse_version(text):
    """Strict full version -> (major, minor, patch, pre tuple)."""
    if not isinstance(text, str):
        raise ValueError("invalid version: %r" % (text,))
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = _VERSION_RE.match(s)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    pre = tuple(m.group(4).split(".")) if m.group(4) else ()
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _parse_partial(text):
    """Returns (major, minor, patch, pre); wildcard/missing parts are None."""
    m = _PARTIAL_RE.match(text)
    if m:
        parts = []
        for g in m.groups():
            parts.append(None if g is None or g in "xX*" else int(g))
        # once a part is a wildcard/missing, the rest must be too
        for a, b in zip(parts, parts[1:]):
            if a is None and b is not None:
                raise ValueError("invalid range part: %r" % (text,))
        return tuple(parts) + ((),)
    s = text[1:] if text.startswith("v") else text
    m = _VERSION_RE.match(s)
    if not m:
        raise ValueError("invalid range part: %r" % (text,))
    return _parse_version(s)


def _bump(major, minor, patch):
    return (major, minor, patch, ("0",))


def _upper_exclusive(p):
    """Exclusive '-0' bound just above the partial; None if unbounded."""
    major, minor = p[0], p[1]
    if major is None:
        return None
    if minor is None:
        return _bump(major + 1, 0, 0)
    return _bump(major, minor + 1, 0)


def _fill(p):
    return (p[0] or 0, p[1] or 0, p[2] or 0, p[3])


def _is_full(p):
    return p[0] is not None and p[1] is not None and p[2] is not None


# A comparator is (op, version, tagged); op in '<', '<=', '>', '>=', '=' or 'none'.
_NONE = ("none", _LOWEST, False)


def _ge(v, tagged=False):
    return (">=", v, tagged)


def _lt(v):
    return ("<", v, False)


def _desugar(op, p):
    tagged = _is_full(p) and bool(p[3])
    if op in ("~", "^"):
        if p[0] is None:
            return [_ge(_LOWEST)]
        low = _fill(p)
        if op == "~":
            up = _upper_exclusive(p)
            if p[1] is not None:
                up = _bump(p[0], p[1] + 1, 0)
        else:
            major, minor, patch = p[0], p[1], p[2]
            if major > 0:
                up = _bump(major + 1, 0, 0)
            elif minor is None:
                up = _bump(1, 0, 0)
            elif minor > 0:
                up = _bump(0, minor + 1, 0)
            elif patch is None:
                up = _bump(0, 1, 0)
            else:
                up = _bump(0, 0, patch + 1)
        return [_ge(low, tagged), _lt(up)]
    if _is_full(p):
        return [("=" if op in (None, "=") else op, (p[0], p[1], p[2], p[3]), tagged)]
    if op in (None, "="):
        if p[0] is None:
            return [_ge(_LOWEST)]
        return [_ge(_fill(p)), _lt(_upper_exclusive(p))]
    if op == ">":
        if p[0] is None:
            return [_NONE]
        return [_ge(_upper_exclusive(p)[:3] + ((),))]
    if op == ">=":
        return [_ge(_fill(p))]
    if op == "<":
        if p[0] is None:
            return [_NONE]
        return [_lt(_bump(p[0], p[1] or 0, 0))]
    if op == "<=":
        if p[0] is None:
            return [_ge(_LOWEST)]
        return [_lt(_upper_exclusive(p))]
    raise ValueError("invalid operator")


def _parse_set(text):
    items = []
    words = text.split()
    i = 0
    while i < len(words):
        m = _OP_RE.match(words[i])
        op, rest = m.group(1), m.group(2)
        i += 1
        if op is not None and rest == "":
            if i >= len(words):
                raise ValueError("dangling operator in %r" % (text,))
            rest = words[i]
            i += 1
        items.append((op, rest))
    comps = []
    i = 0
    while i < len(items):
        op, rest = items[i]
        if rest == "-" or (i + 1 < len(items) and items[i + 1] == (None, "-")):
            if (
                i + 2 >= len(items)
                or op is not None
                or rest == "-"
                or items[i + 2][0] is not None
                or items[i + 2][1] == "-"
            ):
                raise ValueError("invalid hyphen range in %r" % (text,))
            left = _parse_partial(rest)
            right = _parse_partial(items[i + 2][1])
            comps.append(_ge(_fill(left), _is_full(left) and bool(left[3])))
            if _is_full(right):
                comps.append(("<=", right, bool(right[3])))
            else:
                up = _upper_exclusive(right)
                if up is not None:
                    comps.append(_lt(up))
            i += 3
            continue
        comps.extend(_desugar(op, _parse_partial(rest)))
        i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


def _match_comp(comp, key):
    op, v, _ = comp
    if op == "none":
        return False
    c = _cmp_key(v)
    return {
        "<": key < c,
        "<=": key <= c,
        ">": key > c,
        ">=": key >= c,
        "=": key == c,
    }[op]


def _match(version, sets):
    key = _cmp_key(version)
    for comps in sets:
        if not all(_match_comp(c, key) for c in comps):
            continue
        if version[3] and not any(
            tagged and v[3] and v[:3] == version[:3] for _, v, tagged in comps
        ):
            continue
        return True
    return False


def satisfies(version, range_):
    v = _parse_version(version)
    return _match(v, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best, best_key = None, None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if not _match(v, sets):
            continue
        k = _cmp_key(v)
        if best_key is None or k > best_key:
            best, best_key = s, k
    return best
