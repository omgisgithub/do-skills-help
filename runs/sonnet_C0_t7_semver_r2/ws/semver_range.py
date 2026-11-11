"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_PRE = r"%s(?:\.%s)*" % (_PRE_ID, _PRE_ID)
_BUILD = r"%s(?:\.%s)*" % (_BUILD_ID, _BUILD_ID)
_X = r"(?:[xX*]|%s)" % _NUM

_VERSION_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s))?(?:\+(%s))?" % (_NUM, _NUM, _NUM, _PRE, _BUILD),
    re.ASCII,
)
_PARTIAL_RE = re.compile(
    r"(%s)(?:\.(%s)(?:\.(%s)(?:-(%s))?(?:\+(%s))?)?)?" % (_X, _X, _X, _PRE, _BUILD),
    re.ASCII,
)
_OP_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.*)", re.DOTALL)
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")


def _pre_tuple(pre):
    return tuple(pre.split(".")) if pre is not None else None


def _key(v):
    """Sort key for an internal version (major, minor, patch, pre-tuple-or-None)."""
    major, minor, patch, pre = v
    if pre is None:
        return (major, minor, patch, 1, ())
    ids = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre)
    return (major, minor, patch, 0, ids)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("invalid version: %r" % (text,))
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = _VERSION_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), _pre_tuple(m.group(4)))


def _parse_partial(text):
    """Return (major, minor, patch, pre) where missing/wildcard parts are None."""
    s = text
    if s[:1] == "v":
        s = s[1:]
    m = _PARTIAL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    nums = []
    for g in m.group(1, 2, 3):
        nums.append(int(g) if g is not None and g.isdigit() else None)
    # a wildcard or missing part forces all following parts to be wildcards too
    for i in range(1, 3):
        if nums[i] is not None and nums[i - 1] is None:
            raise ValueError("invalid version: %r" % (text,))
    pre = m.group(4)
    if (pre is not None or m.group(5) is not None) and nums[2] is None:
        raise ValueError("invalid version: %r" % (text,))
    return (nums[0], nums[1], nums[2], _pre_tuple(pre))


# A comparator is (op, version, counts) where op in {">=", "<", "<=", ">", "="}.
_NOTHING = ("<", (0, 0, 0, ("0",)), False)
_ZERO = (">=", (0, 0, 0, None), False)


def _lo(v):
    return (">=", v, False)


def _hi(v):  # exclusive upper bound that excludes prereleases of v
    return ("<", (v[0], v[1], v[2], ("0",)), False)


def _fill(p):
    return (p[0] or 0, p[1] or 0, p[2] or 0, p[3])


def _upper_of_partial(p):
    """Exclusive bound just above everything matched by partial p (p[0] not None)."""
    if p[1] is None:
        return _hi((p[0] + 1, 0, 0))
    return _hi((p[0], p[1] + 1, 0))


def _desugar(op, p):
    major, minor, patch, pre = p
    full = patch is not None
    counts = pre is not None
    if op in ("", "="):
        if major is None:
            return [_ZERO]
        if full:
            return [("=", p, counts)]
        return [_lo(_fill(p)), _upper_of_partial(p)]
    if op == ">":
        if major is None:
            return [_NOTHING]
        if full:
            return [(">", p, counts)]
        if minor is None:
            return [_lo((major + 1, 0, 0, None))]
        return [_lo((major, minor + 1, 0, None))]
    if op == ">=":
        if major is None:
            return [_ZERO]
        return [(">=", _fill(p), counts)]
    if op == "<":
        if major is None:
            return [_NOTHING]
        if full:
            return [("<", p, counts)]
        return [_hi(_fill(p))]
    if op == "<=":
        if major is None:
            return [_ZERO]
        if full:
            return [("<=", p, counts)]
        return [_upper_of_partial(p)]
    if op == "~":
        if major is None:
            return [_ZERO]
        low = (">=", _fill(p), counts)
        if minor is None:
            return [low, _hi((major + 1, 0, 0))]
        return [low, _hi((major, minor + 1, 0))]
    if op == "^":
        if major is None:
            return [_ZERO]
        low = (">=", _fill(p), counts)
        if major > 0 or minor is None:
            return [low, _hi((major + 1, 0, 0))]
        if minor > 0 or patch is None:
            return [low, _hi((0, minor + 1, 0))]
        return [low, _hi((0, 0, patch + 1))]
    raise ValueError("invalid operator: %r" % (op,))


def _split_op(token):
    m = _OP_RE.fullmatch(token)
    return m.group(1) or "", m.group(2)


def _parse_set(text):
    raw = text.split()
    tokens = []
    i = 0
    while i < len(raw):
        tok = raw[i]
        op, rest = _split_op(tok)
        if op and not rest:
            if i + 1 >= len(raw):
                raise ValueError("dangling operator in %r" % (text,))
            nxt = raw[i + 1]
            if _split_op(nxt)[0] and not _split_op(nxt)[1] or nxt == "-":
                raise ValueError("invalid range: %r" % (text,))
            tok = op + nxt
            i += 1
        tokens.append(tok)
        i += 1

    comps = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-":
            raise ValueError("invalid hyphen range in %r" % (text,))
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError("invalid hyphen range in %r" % (text,))
            right = tokens[i + 2]
            if _split_op(tok)[0] or _split_op(right)[0] or right == "-":
                raise ValueError("invalid hyphen range in %r" % (text,))
            left_p = _parse_partial(tok)
            right_p = _parse_partial(right)
            comps.extend(_desugar(">=", left_p))
            if right_p[0] is not None:
                comps.extend(_desugar("<=", right_p))
            i += 3
            continue
        op, rest = _split_op(tok)
        comps.extend(_desugar(op, _parse_partial(rest)))
        i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


def _match_comp(comp, vkey):
    op, v, _ = comp
    k = _key(v)
    if op == ">=":
        return vkey >= k
    if op == ">":
        return vkey > k
    if op == "<=":
        return vkey <= k
    if op == "<":
        return vkey < k
    return vkey == k


def _match(v, sets):
    vkey = _key(v)
    for comps in sets:
        if not all(_match_comp(c, vkey) for c in comps):
            continue
        if v[3] is not None and not any(
            c[2] and c[1][:3] == v[:3] and c[1][3] is not None for c in comps
        ):
            continue
        return True
    return False


def satisfies(version, range_):
    v = _parse_version(version)
    return _match(v, _parse_range(range_))


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
        k = _key(v)
        if best_key is None or k > best_key:
            best, best_key = s, k
    return best
