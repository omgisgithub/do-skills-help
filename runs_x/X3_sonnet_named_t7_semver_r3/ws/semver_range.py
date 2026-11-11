"""npm-style version range matching. See TASK.md for the exact spec."""
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_PART = r"(?:%s|[xX*])" % _NUM
_PARTIAL_RE = re.compile(
    r"(%s)(?:\.(%s))?(?:\.(%s))?(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?"
    % (_PART, _PART, _PART, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")
_ZERO_PRE = (0,)


def _pre_tuple(s):
    if s is None:
        return None
    return tuple(int(x) if x.isdigit() else x for x in s.split("."))


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


def _cmp_pre(a, b):
    if a is None and b is None:
        return 0
    if a is None:
        return 1
    if b is None:
        return -1
    for x, y in zip(a, b):
        if x == y:
            continue
        xi, yi = isinstance(x, int), isinstance(y, int)
        if xi and yi:
            return -1 if x < y else 1
        if xi:
            return -1
        if yi:
            return 1
        return -1 if x < y else 1
    return (len(a) > len(b)) - (len(a) < len(b))


def _cmp(a, b):
    for x, y in zip(a[:3], b[:3]):
        if x != y:
            return -1 if x < y else 1
    return _cmp_pre(a[3], b[3])


def _parse_partial(text):
    """Return (major, minor, patch, pre, n) where n = number of specified numeric parts."""
    s = text
    if s[:1] == "v":
        s = s[1:]
    m = _PARTIAL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid range element: %r" % (text,))
    parts = []
    wild = False
    for g in m.groups()[:3]:
        if g is None or g in ("x", "X", "*"):
            wild = True
            parts.append(None)
        else:
            if wild:
                raise ValueError("invalid range element: %r" % (text,))
            parts.append(int(g))
    pre = _pre_tuple(m.group(4))
    n = sum(p is not None for p in parts)
    if (pre is not None or m.group(5) is not None) and n != 3:
        raise ValueError("invalid range element: %r" % (text,))
    return (parts[0] or 0, parts[1] or 0, parts[2] or 0, pre, n)


def _bounds(op, p):
    """Desugar to list of (op, version, flagged)."""
    M, m, pt, pre, n = p
    full = (M, m, pt, pre)
    flag = pre is not None
    lo = lambda v: (">=", v, False)
    hi = lambda v: ("<", v, False)
    NOTHING = [("<", (0, 0, 0, _ZERO_PRE), False)]
    ANY = [(">=", (0, 0, 0, None), False)]
    if op in ("", "="):
        if n == 0:
            return ANY
        if n == 1:
            return [lo((M, 0, 0, None)), hi((M + 1, 0, 0, _ZERO_PRE))]
        if n == 2:
            return [lo((M, m, 0, None)), hi((M, m + 1, 0, _ZERO_PRE))]
        return [("=", full, flag)]
    if op == ">":
        if n == 0:
            return NOTHING
        if n == 1:
            return [lo((M + 1, 0, 0, None))]
        if n == 2:
            return [lo((M, m + 1, 0, None))]
        return [(">", full, flag)]
    if op == ">=":
        if n == 0:
            return ANY
        if n == 3:
            return [(">=", full, flag)]
        return [lo((M, m if n == 2 else 0, 0, None))]
    if op == "<":
        if n == 0:
            return NOTHING
        if n == 1:
            return [hi((M, 0, 0, _ZERO_PRE))]
        if n == 2:
            return [hi((M, m, 0, _ZERO_PRE))]
        return [("<", full, flag)]
    if op == "<=":
        if n == 0:
            return ANY
        if n == 1:
            return [hi((M + 1, 0, 0, _ZERO_PRE))]
        if n == 2:
            return [hi((M, m + 1, 0, _ZERO_PRE))]
        return [("<=", full, flag)]
    if op == "~":
        if n == 0:
            return ANY
        if n == 1:
            return [lo((M, 0, 0, None)), hi((M + 1, 0, 0, _ZERO_PRE))]
        return [(">=", full if n == 3 else (M, m, 0, None), flag),
                hi((M, m + 1, 0, _ZERO_PRE))]
    if op == "^":
        if n == 0:
            return ANY
        lower = (">=", full if n == 3 else (M, m if n == 2 else 0, 0, None), flag)
        if M > 0:
            upper = (M + 1, 0, 0, _ZERO_PRE)
        elif n == 1:
            upper = (1, 0, 0, _ZERO_PRE)
        elif m > 0 or n == 2:
            upper = (0, m + 1, 0, _ZERO_PRE)
        else:
            upper = (0, 0, pt + 1, _ZERO_PRE)
        return [lower, hi(upper)]
    raise ValueError("bad operator")


def _hyphen(a, b):
    pa, pb = _parse_partial(a), _parse_partial(b)
    res = _bounds(">=", pa)
    M, m, pt, pre, n = pb
    if n == 3:
        res += _bounds("<=", pb)
    elif n == 0:
        res += []
    else:
        res += _bounds("<=", pb)
    return res


def _parse_set(text):
    raw = text.split()
    tokens = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t in _OPS:
            if i + 1 >= len(raw) or raw[i + 1] in _OPS or raw[i + 1] == "-":
                raise ValueError("dangling operator in %r" % (text,))
            t = t + raw[i + 1]
            i += 1
        tokens.append(t)
        i += 1
    comps = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens) or tokens[i + 2] == "-":
                raise ValueError("bad hyphen range in %r" % (text,))
            for side in (t, tokens[i + 2]):
                if side[:1] in "<>=~^" or side == "-":
                    raise ValueError("bad hyphen range in %r" % (text,))
            comps += _hyphen(t, tokens[i + 2])
            i += 3
            continue
        if t == "-":
            raise ValueError("bad hyphen range in %r" % (text,))
        op = ""
        for o in _OPS:
            if t.startswith(o):
                op = o
                break
        rest = t[len(op):]
        comps += _bounds(op, _parse_partial(rest))
        i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(s) for s in range_.split("||")]


def _match_set(v, comps):
    for op, cv, _ in comps:
        c = _cmp(v, cv)
        if op == "<" and not c < 0:
            return False
        if op == "<=" and not c <= 0:
            return False
        if op == ">" and not c > 0:
            return False
        if op == ">=" and not c >= 0:
            return False
        if op == "=" and c != 0:
            return False
    if v[3] is not None:
        return any(f and cv[:3] == v[:3] for _, cv, f in comps)
    return True


def _satisfies(v, sets):
    return any(_match_set(v, s) for s in sets)


def satisfies(version, range_):
    v = _parse_version(version)
    return _satisfies(v, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best, best_v = None, None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if _satisfies(v, sets) and (best_v is None or _cmp(v, best_v) > 0):
            best, best_v = s, v
    return best
