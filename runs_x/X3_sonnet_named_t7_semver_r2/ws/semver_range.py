"""npm-style version range matching. See TASK.md for the exact spec."""
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_W = r"(?:[xX*]|%s)" % _NUM
_PARTIAL_RE = re.compile(
    r"(%s)(?:\.(%s)(?:\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?)?)?"
    % (_W, _W, _W, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_OP_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.*)", re.S)
_OP_SPACE_RE = re.compile(r"(<=|>=|<|>|=|~|\^)\s+(?![<>=~^])")
_HYPHEN_RE = re.compile(r"\s+-\s+")

_ZERO_PRE = ("0",)


def _pre_key(pre):
    if pre is None:
        return (1,)
    return (0, tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre))


def _key(v):
    return (v[0], v[1], v[2]) + _pre_key(v[3])


def _strip_v(s):
    if s[:1] in ("v", "="):
        return s[1:]
    return s


def _parse_version(s):
    if not isinstance(s, str):
        raise ValueError("invalid version: %r" % (s,))
    m = _VERSION_RE.fullmatch(_strip_v(s.strip()))
    if not m:
        raise ValueError("invalid version: %r" % (s,))
    pre = tuple(m.group(4).split(".")) if m.group(4) else None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _parse_partial(s):
    """Return (maj, min, pat, pre, n) with None for wildcard parts; n = specified parts."""
    if s[:1] == "v":
        s = s[1:]
    m = _PARTIAL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid range element: %r" % (s,))
    parts = []
    for g in m.group(1, 2, 3):
        if g is None or g in ("x", "X", "*"):
            parts.append(None)
        else:
            parts.append(int(g))
    n = 0
    for p in parts:
        if p is None:
            break
        n += 1
    if any(p is not None for p in parts[n:]):
        raise ValueError("invalid wildcard placement: %r" % (s,))
    pre = None
    if m.group(4):
        if n != 3:
            raise ValueError("partial with prerelease: %r" % (s,))
        pre = tuple(m.group(4).split("."))
    if m.group(5) and n != 3:
        raise ValueError("partial with build: %r" % (s,))
    return (parts[0], parts[1], parts[2], pre, n)


# comparator: (op, version, tagged)
_NOTHING = ("<", (0, 0, 0, _ZERO_PRE), False)
_ANY = (">=", (0, 0, 0, None), False)


def _lower(p):
    return (p[0] or 0, p[1] or 0, p[2] or 0, p[3])


def _upper(p):
    """Exclusive upper bound (with -0) of a partial with 1<=n<=2."""
    if p[4] == 1:
        return (p[0] + 1, 0, 0, _ZERO_PRE)
    return (p[0], p[1] + 1, 0, _ZERO_PRE)


def _bump(p):
    v = _upper(p)
    return (v[0], v[1], v[2], None)


def _tag(p):
    return p[4] == 3 and p[3] is not None


def _primitive(op, p):
    n = p[4]
    if n == 3:
        v = _lower(p)
        return [(op, v, _tag(p))]
    if op in ("", "="):
        if n == 0:
            return [_ANY]
        return [(">=", _lower(p), False), ("<", _upper(p), False)]
    if op == ">":
        return [_NOTHING] if n == 0 else [(">=", _bump(p), False)]
    if op == ">=":
        return [(">=", _lower(p), False)]
    if op == "<":
        return [_NOTHING] if n == 0 else [("<", _lower(p)[:3] + (_ZERO_PRE,), False)]
    if op == "<=":
        return [_ANY] if n == 0 else [("<", _upper(p), False)]
    raise ValueError("bad operator")


def _tilde(p):
    n = p[4]
    if n == 0:
        return [_ANY]
    return [(">=", _lower(p), _tag(p)), ("<", _upper_tilde(p), False)]


def _upper_tilde(p):
    if p[4] == 1:
        return (p[0] + 1, 0, 0, _ZERO_PRE)
    return (p[0], p[1] + 1, 0, _ZERO_PRE)


def _caret(p):
    n = p[4]
    if n == 0:
        return [_ANY]
    maj, mnr, pat = p[0], p[1] or 0, p[2] or 0
    if maj > 0 or n == 1:
        up = (maj + 1, 0, 0, _ZERO_PRE)
    elif n == 2:
        up = (0, mnr + 1, 0, _ZERO_PRE)
    elif mnr > 0:
        up = (0, mnr + 1, 0, _ZERO_PRE)
    else:
        up = (0, 0, pat + 1, _ZERO_PRE)
    return [(">=", _lower(p), _tag(p)), ("<", up, False)]


def _parse_set(s):
    s = s.strip()
    if not s:
        return []
    if _HYPHEN_RE.search(s):
        parts = _HYPHEN_RE.split(s)
        if len(parts) != 2:
            raise ValueError("invalid hyphen range: %r" % (s,))
        left, right = _parse_partial(parts[0]), _parse_partial(parts[1])
        return _primitive(">=", left) + _primitive("<=", right)
    comps = []
    for tok in _OP_SPACE_RE.sub(r"\1", s).split():
        op, rest = _OP_RE.fullmatch(tok).groups()
        p = _parse_partial(rest)
        if op == "~":
            comps += _tilde(p)
        elif op == "^":
            comps += _caret(p)
        else:
            comps += _primitive(op or "", p)
    return comps


def _parse_range(r):
    if not isinstance(r, str):
        raise ValueError("invalid range: %r" % (r,))
    return [_parse_set(part) for part in r.split("||")]


def _match(op, cv, v):
    a, b = _key(v), _key(cv)
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    return a == b


def _check(v, sets):
    for comps in sets:
        if not all(_match(op, cv, v) for op, cv, _ in comps):
            continue
        if v[3] is not None and not any(
            t and cv[:3] == v[:3] for _, cv, t in comps
        ):
            continue
        return True
    return False


def satisfies(version, range_):
    v = _parse_version(version)
    sets = _parse_range(range_)
    return _check(v, sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best, best_key = None, None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if not _check(v, sets):
            continue
        k = _key(v)
        if best_key is None or k > best_key:
            best, best_key = s, k
    return best
