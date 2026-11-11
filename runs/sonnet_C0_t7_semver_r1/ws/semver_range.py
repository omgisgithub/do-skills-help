"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_PART = r"(x|X|\*|" + _NUM + r")"
_PARTIAL_RE = re.compile(
    r"v?" + _PART + r"(?:\." + _PART + r"(?:\." + _PART
    + r"(?:-(" + _PRE_ID + r"(?:\." + _PRE_ID + r")*))?"
    + r"(?:\+" + _BUILD_ID + r"(?:\." + _BUILD_ID + r")*)?"
    + r")?)?",
    re.ASCII,
)
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")
_WILD = (None, "x", "X", "*")

_LOWEST_PRE = ((0, 0),)  # the "-0" prerelease used for exclusive upper bounds


def _pre_key(pre):
    return tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split("."))


def _key(major, minor, patch, pre):
    """Sortable precedence key; pre is a dotted string, a key tuple, or None."""
    if pre is None:
        return (major, minor, patch, 1, ())
    if isinstance(pre, str):
        pre = _pre_key(pre)
    return (major, minor, patch, 0, pre)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("invalid version: %r" % (text,))
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = re.fullmatch(
        r"(" + _NUM + r")\.(" + _NUM + r")\.(" + _NUM + r")"
        r"(?:-(" + _PRE_ID + r"(?:\." + _PRE_ID + r")*))?"
        r"(?:\+" + _BUILD_ID + r"(?:\." + _BUILD_ID + r")*)?",
        s, re.ASCII)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)


def _parse_partial(text):
    """Return (major, minor, patch, pre) with None for missing/wildcard parts."""
    m = _PARTIAL_RE.fullmatch(text)
    if not m:
        raise ValueError("invalid range component: %r" % (text,))
    parts = []
    for g in m.group(1, 2, 3):
        parts.append(None if g in _WILD else int(g))
    pre = m.group(4)
    if parts[2] is None and len(m.group(0)) != len(m.group(0).split("-")[0].split("+")[0]):
        raise ValueError("invalid range component: %r" % (text,))
    seen_wild = False
    for p in parts:
        if p is None:
            seen_wild = True
        elif seen_wild:
            raise ValueError("invalid range component: %r" % (text,))
    return parts[0], parts[1], parts[2], pre


# A comparator is (op, key, counts_pre_tuple_or_None); op in <,<=,>,>=,=,none
def _cmp(op, v, pre_of=None):
    return (op, v, pre_of)


def _lo(major, minor, patch, pre):
    """Lower bound >= for a partial (zero filled)."""
    v = _key(major or 0, minor or 0, patch or 0, pre)
    return _cmp(">=", v, (major, minor, patch) if pre else None)


def _lt_next(major, minor, patch):
    """Exclusive upper bound just above the given partial's range."""
    if major is None:
        return None
    if minor is None:
        return _cmp("<", _key(major + 1, 0, 0, _LOWEST_PRE))
    if patch is None:
        return _cmp("<", _key(major, minor + 1, 0, _LOWEST_PRE))
    return _cmp("<", _key(major, minor, patch + 1, _LOWEST_PRE))


def _xrange(op, p):
    major, minor, patch, pre = p
    full = patch is not None
    if op == "=":
        if full:
            return [_cmp("=", _key(major, minor, patch, pre), (major, minor, patch) if pre else None)]
        out = [_lo(major, minor, patch, pre)]
        up = _lt_next(major, minor, patch)
        if up:
            out.append(up)
        return out
    if op == ">":
        if major is None:
            return [_cmp("none", None)]
        if full:
            return [_cmp(">", _key(major, minor, patch, pre), (major, minor, patch) if pre else None)]
        if minor is None:
            return [_cmp(">=", _key(major + 1, 0, 0, None))]
        return [_cmp(">=", _key(major, minor + 1, 0, None))]
    if op == ">=":
        return [_lo(major, minor, patch, pre)]
    if op == "<":
        if major is None:
            return [_cmp("none", None)]
        if full:
            return [_cmp("<", _key(major, minor, patch, pre), (major, minor, patch) if pre else None)]
        return [_cmp("<", _key(major, minor or 0, 0, _LOWEST_PRE))]
    if op == "<=":
        if major is None:
            return [_cmp(">=", _key(0, 0, 0, None))]
        if full:
            return [_cmp("<=", _key(major, minor, patch, pre), (major, minor, patch) if pre else None)]
        return [_lt_next(major, minor, patch)]
    raise ValueError("bad operator")


def _tilde(p):
    major, minor, patch, pre = p
    if major is None:
        return [_cmp(">=", _key(0, 0, 0, None))]
    return [_lo(major, minor, patch, pre), _lt_next(major, minor, None)]


def _caret(p):
    major, minor, patch, pre = p
    if major is None:
        return [_cmp(">=", _key(0, 0, 0, None))]
    if major > 0 or minor is None:
        up = _key(major + 1, 0, 0, _LOWEST_PRE)
    elif minor > 0 or patch is None:
        up = _key(0, minor + 1, 0, _LOWEST_PRE)
    else:
        up = _key(0, 0, patch + 1, _LOWEST_PRE)
    return [_lo(major, minor, patch, pre), _cmp("<", up)]


def _hyphen(left, right):
    out = [_lo(*left)] if left[0] is not None else [_cmp(">=", _key(0, 0, 0, None))]
    major, minor, patch, pre = right
    if major is None:
        return out
    if patch is not None:
        out.append(_cmp("<=", _key(major, minor, patch, pre), (major, minor, patch) if pre else None))
    else:
        out.append(_lt_next(major, minor, patch))
    return out


def _split_op(tok):
    for op in _OPS:
        if tok.startswith(op):
            return op, tok[len(op):]
    return "", tok


def _parse_set(text):
    raw = text.split()
    tokens = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t in _OPS:
            if i + 1 >= len(raw):
                raise ValueError("dangling operator in range")
            t += raw[i + 1]
            i += 1
        tokens.append(t)
        i += 1
    comps = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "-":
            raise ValueError("misplaced hyphen in range")
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError("incomplete hyphen range")
            left, right = tokens[i], tokens[i + 2]
            if _split_op(left)[0] or _split_op(right)[0]:
                raise ValueError("operator in hyphen range")
            comps += _hyphen(_parse_partial(left), _parse_partial(right))
            i += 3
            continue
        op, rest = _split_op(t)
        p = _parse_partial(rest)
        if op == "~":
            comps += _tilde(p)
        elif op == "^":
            comps += _caret(p)
        else:
            comps += _xrange(op or "=", p)
        i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


def _test(comp, key):
    op, v, _ = comp
    if op == "none":
        return False
    if op == "=":
        return key == v
    if op == ">":
        return key > v
    if op == ">=":
        return key >= v
    if op == "<":
        return key < v
    return key <= v


def _match(parsed_version, sets):
    major, minor, patch, pre = parsed_version
    key = _key(major, minor, patch, pre)
    for comps in sets:
        if not all(_test(c, key) for c in comps):
            continue
        if pre is not None and not any(
                c[2] == (major, minor, patch) for c in comps):
            continue
        return True
    return False


def satisfies(version, range_):
    v = _parse_version(version)
    sets = _parse_range(range_)
    return _match(v, sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if not _match(v, sets):
            continue
        k = _key(*v)
        if best_key is None or k > best_key:
            best, best_key = s, k
    return best
