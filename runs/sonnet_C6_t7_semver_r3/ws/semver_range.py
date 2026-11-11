"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_PRE = _PRE_ID + r"(?:\." + _PRE_ID + r")*"
_BUILD = _BUILD_ID + r"(?:\." + _BUILD_ID + r")*"
_WS = " \t\n\r\f\v"

_VERSION_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s))?(?:\+(%s))?" % (_NUM, _NUM, _NUM, _PRE, _BUILD)
)
_PART = r"(?:%s|x|X|\*)" % _NUM
_PARTIAL_RE = re.compile(
    r"v?(%s)(?:\.(%s)(?:\.(%s)(?:-(%s))?(?:\+(%s))?)?)?" % (_PART, _PART, _PART, _PRE, _BUILD)
)
_OP_RE = re.compile(r"(<=|>=|<|>|=|~|\^)")
_WS_SPLIT = re.compile("[%s]+" % _WS)


def _pre_key(pre):
    return tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split("."))


def _parse_version(s):
    """Parse a full version into (major, minor, patch, pre) where pre is a tuple or None."""
    if not isinstance(s, str):
        raise ValueError("invalid version: %r" % (s,))
    t = s.strip(_WS)
    if t[:1] in ("v", "="):
        t = t[1:]
    m = _VERSION_RE.fullmatch(t)
    if not m:
        raise ValueError("invalid version: %r" % (s,))
    pre = _pre_key(m.group(4)) if m.group(4) is not None else None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _cmp(a, b):
    ta, tb = a[:3], b[:3]
    if ta != tb:
        return -1 if ta < tb else 1
    pa, pb = a[3], b[3]
    if pa is None and pb is None:
        return 0
    if pa is None:
        return 1
    if pb is None:
        return -1
    if pa == pb:
        return 0
    return -1 if pa < pb else 1


def _parse_partial(s):
    """Return (major, minor, patch, pre) with None for wildcard/missing parts."""
    m = _PARTIAL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (s,))
    parts = []
    for g in m.group(1, 2, 3):
        if g is None or g in ("x", "X", "*"):
            parts.append(None)
        else:
            parts.append(int(g))
    seen_wild = False
    for i, g in enumerate(m.group(1, 2, 3)):
        if g is None or g in ("x", "X", "*"):
            seen_wild = True
        elif seen_wild:
            raise ValueError("invalid version: %r" % (s,))
    pre = None
    if m.group(4) is not None or m.group(5) is not None:
        if parts[2] is None:
            raise ValueError("invalid version: %r" % (s,))
    if m.group(4) is not None:
        pre = _pre_key(m.group(4))
    return (parts[0], parts[1], parts[2], pre)


_ZERO = (0, 0, 0, None)


def _ceil(M, m=0, p=0):
    return (M, m, p, (_pre_key("0")))


def _desugar(op, part):
    """Return list of (op, version, counts) comparators; None entries mean 'match nothing'."""
    M, m, p, pre = part
    full = p is not None
    if op in ("", "="):
        if M is None:
            return [(">=", _ZERO, False)]
        if full:
            return [("=", (M, m, p, pre), pre is not None)]
        if m is None:
            return [(">=", (M, 0, 0, None), False), ("<", _ceil(M + 1), False)]
        return [(">=", (M, m, 0, None), False), ("<", _ceil(M, m + 1), False)]
    if op == ">":
        if M is None:
            return None
        if full:
            return [(">", (M, m, p, pre), pre is not None)]
        if m is None:
            return [(">=", (M + 1, 0, 0, None), False)]
        return [(">=", (M, m + 1, 0, None), False)]
    if op == ">=":
        if M is None:
            return [(">=", _ZERO, False)]
        return [(">=", (M, m or 0, p or 0, pre), pre is not None)]
    if op == "<":
        if M is None:
            return None
        if full:
            return [("<", (M, m, p, pre), pre is not None)]
        return [("<", _ceil(M, m or 0), False)]
    if op == "<=":
        if M is None:
            return [(">=", _ZERO, False)]
        if full:
            return [("<=", (M, m, p, pre), pre is not None)]
        if m is None:
            return [("<", _ceil(M + 1), False)]
        return [("<", _ceil(M, m + 1), False)]
    if op == "~":
        if M is None:
            return [(">=", _ZERO, False)]
        if m is None:
            return [(">=", (M, 0, 0, None), False), ("<", _ceil(M + 1), False)]
        return [(">=", (M, m, p or 0, pre), pre is not None), ("<", _ceil(M, m + 1), False)]
    if op == "^":
        if M is None:
            return [(">=", _ZERO, False)]
        if m is None:
            return [(">=", (M, 0, 0, None), False), ("<", _ceil(M + 1), False)]
        low = (">=", (M, m, p or 0, pre), pre is not None)
        if M > 0:
            up = _ceil(M + 1)
        elif not full:
            up = _ceil(0, m + 1)
        elif m > 0:
            up = _ceil(0, m + 1)
        else:
            up = _ceil(0, 0, p + 1)
        return [low, ("<", up, False)]
    raise ValueError("invalid operator")


def _hyphen(left, right):
    lM, lm, lp, lpre = left
    out = [(">=", (lM or 0, lm or 0, lp or 0, lpre), lpre is not None)]
    rM, rm, rp, rpre = right
    if rM is None:
        pass
    elif rp is not None:
        out.append(("<=", (rM, rm, rp, rpre), rpre is not None))
    elif rm is None:
        out.append(("<", _ceil(rM + 1), False))
    else:
        out.append(("<", _ceil(rM, rm + 1), False))
    return out


def _parse_set(text):
    """Return a list of comparators, or None if the set can never match."""
    tokens = [t for t in _WS_SPLIT.split(text.strip(_WS)) if t]
    # merge operators with the following token
    merged = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if _OP_RE.fullmatch(t):
            if i + 1 >= len(tokens):
                raise ValueError("dangling operator")
            nxt = tokens[i + 1]
            if nxt == "-" or _OP_RE.match(nxt):
                raise ValueError("invalid range")
            merged.append(("op", t, nxt))
            i += 2
        else:
            m = _OP_RE.match(t)
            if m:
                merged.append(("op", m.group(1), t[m.end():]))
            elif t == "-":
                merged.append(("hy",))
            else:
                merged.append(("op", "", t))
            i += 1
    comps = []
    nothing = False
    i = 0
    while i < len(merged):
        item = merged[i]
        if item[0] == "hy":
            raise ValueError("invalid hyphen range")
        if i + 1 < len(merged) and merged[i + 1][0] == "hy":
            if i + 2 >= len(merged):
                raise ValueError("invalid hyphen range")
            right = merged[i + 2]
            if item[1] != "" or right[0] != "op" or right[1] != "":
                raise ValueError("invalid hyphen range")
            comps.extend(_hyphen(_parse_partial(item[2]), _parse_partial(right[2])))
            i += 3
            continue
        res = _desugar(item[1], _parse_partial(item[2]))
        if res is None:
            nothing = True
        else:
            comps.extend(res)
        i += 1
    return None if nothing else comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    sets = [_parse_set(part) for part in range_.split("||")]
    return sets


def _test(v, op, w):
    c = _cmp(v, w)
    if op == "=":
        return c == 0
    if op == "<":
        return c < 0
    if op == "<=":
        return c <= 0
    if op == ">":
        return c > 0
    return c >= 0


def _match(v, sets):
    for comps in sets:
        if comps is None:
            continue
        if not all(_test(v, op, w) for op, w, _ in comps):
            continue
        if v[3] is not None and not any(
            counts and w[:3] == v[:3] for _, w, counts in comps
        ):
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
    best_v = None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if not _match(v, sets):
            continue
        if best_v is None or _cmp(v, best_v) > 0:
            best, best_v = s, v
    return best
