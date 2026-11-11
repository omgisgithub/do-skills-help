"""npm-style version range matching. See TASK.md for the exact spec."""
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_ID = r"[0-9A-Za-z-]+"
_PART = r"(x|X|\*|" + _NUM + ")"
_PARTIAL = re.compile(
    "%s(?:\\.%s(?:\\.%s(?:-(%s(?:\\.%s)*))?(?:\\+(%s(?:\\.%s)*))?)?)?" % (_PART, _PART, _PART, _ID, _ID, _ID, _ID),
    re.ASCII,
)
_OP = re.compile(r"(>=|<=|>|<|=|~|\^)?(.*)", re.DOTALL)
_OPS = {">=", "<=", ">", "<", "=", "~", "^"}
_LOWEST = (0, 0, 0, ("0",))  # nothing sorts below 0.0.0-0


def _pre(s):
    ids = tuple(s.split("."))
    if any(i.isdigit() and len(i) > 1 and i[0] == "0" for i in ids):
        raise ValueError("bad prerelease: " + s)
    return ids


def _partial(s):
    """-> (major, minor, patch, pre); wildcards are None."""
    m = _PARTIAL.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % s)
    parts = [None if g in (None, "x", "X", "*") else int(g) for g in m.groups()[:3]]
    for a, b in zip(parts, parts[1:]):
        if a is None and b is not None:
            raise ValueError("invalid version: %r" % s)
    return (*parts, _pre(m.group(4)) if m.group(4) else ())


def _parse_version(s):
    s = s.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    v = _partial(s)
    if None in v[:3]:
        raise ValueError("invalid version: %r" % s)
    return v


def _key(v):
    pre = v[3]
    return (v[0], v[1], v[2], 0 if pre else 1,
            tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre))


def _lt(M, m, p):  # exclusive upper bound that keeps out prereleases of the bound
    return ("<", (M, m, p, ("0",)))


_NOTHING = ("<", _LOWEST)
_ANY = (">=", (0, 0, 0, ()))


def _upper(M, m):
    """Upper bound for a partial: <M+1.0.0-0 / <M.m+1.0-0; None when M is a wildcard."""
    if M is None:
        return None
    return _lt(M + 1, 0, 0) if m is None else _lt(M, m + 1, 0)


def _desugar(op, v):
    M, m, p, pre = v
    z = lambda x: x or 0
    if M is None:
        return {">": [_NOTHING], "<": [_NOTHING]}.get(op, [_ANY])
    full = p is not None
    lo = (">=", (M, z(m), z(p), pre))
    if op in ("", "="):
        return [("=", lo[1])] if full else [lo, _upper(M, m)]
    if op == ">=":
        return [lo]
    if op == "<=":
        return [("<=", lo[1])] if full else [_upper(M, m)]
    if op == "<":
        return [("<", lo[1])] if full else [_lt(M, z(m), 0)]
    if op == ">":
        if full:
            return [(">", lo[1])]
        return [(">=", (M + 1, 0, 0, ()) if m is None else (M, m + 1, 0, ()))]
    if op == "~":
        return [lo, _upper(M, m)]
    # caret: bump the left-most non-zero part
    if M > 0 or m is None:
        hi = _lt(M + 1, 0, 0)
    elif m > 0 or p is None:
        hi = _lt(0, m + 1, 0)
    else:
        hi = _lt(0, 0, p + 1)
    return [lo, hi]


def _parse_set(text):
    toks = text.split()
    comps, allowed = [], set()

    def add(op, v):
        comps.extend(_desugar(op, v))
        if v[3]:
            allowed.add(v[:3])

    i = 0
    while i < len(toks):
        t = toks[i]
        if t in _OPS:  # operator separated from its version by spaces
            if i + 1 >= len(toks):
                raise ValueError("dangling operator")
            t += toks[i + 1]
            i += 1
        i += 1
        if i < len(toks) and toks[i] == "-":  # hyphen range
            if i + 1 >= len(toks) or _OP.fullmatch(t).group(1):
                raise ValueError("invalid hyphen range")
            lo = _partial(t[1:] if t[0] == "v" else t)
            hi = _partial(toks[i + 1][1:] if toks[i + 1][0] == "v" else toks[i + 1])
            add(">=", lo)
            if hi[0] is not None:
                add("<=", hi)
            i += 2
            continue
        op, rest = _OP.fullmatch(t).groups()
        op = op or ""
        if rest[:1] == "v" and op != "=":
            rest = rest[1:]
        add(op, _partial(rest))
    return comps, allowed


def _parse_range(range_):
    return [_parse_set(s) for s in range_.split("||")]


_TESTS = {
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b, "=": lambda a, b: a == b,
}


def _match(v, sets):
    k = _key(v)
    for comps, allowed in sets:
        if all(_TESTS[op](k, _key(cv)) for op, cv in comps) and (not v[3] or v[:3] in allowed):
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
        except (ValueError, AttributeError, TypeError):
            continue
        if _match(v, sets) and (best is None or _key(v) > best_key):
            best, best_key = s, _key(v)
    return best


if __name__ == "__main__":
    ok = [("1.2.3", "^1.2.3"), ("1.9.0", "^1.2"), ("1.3.0", "1.2.3 - 2"), ("1.2.3-beta.4", "^1.2.3-beta.2"),
          ("0.2.9", "^0.2.3"), ("2.0.0", "<=1 || 2.x"), ("1.2.3", ""), ("3.0.0", ">=*"), ("1.5.0", ">= 1.2.3 < 2"),
          ("1.2.9", "~1.2"), ("v1.2.3", "=1.2.3"), ("1.2.3+b", "1.2.3"), ("1.2.3", "1.2 - 1.3")]
    bad = [("1.2.4-alpha", "^1.2.3"), ("1.0.0-rc.1", "*"), ("2.0.0", "^1.2.3"), ("2.0.0-0", "^1.2.3"),
           ("1.0.0", ">*"), ("1.0.0", "<*"), ("0.3.0", "^0.2.3"), ("0.0.4", "^0.0.3"), ("1.3.0", "~1.2.3"),
           ("1.2.3-a", "<1.2.3 >1.0.0"), ("1.2.0", ">1.2"), ("2.4.0", "1.2.3 - 2.3")]
    for v, r in ok:
        assert satisfies(v, r), (v, r)
    for v, r in bad:
        assert not satisfies(v, r), (v, r)
    for bv, br in [("1.2", "*"), ("01.2.3", "*"), ("1.0.0", "~>1.2"), ("1.0.0", ">=1.2.3 -"), ("1.0.0", "1.2.3.4"),
                   ("1.0.0", "^"), ("1.0.0", ">=a.b.c"), ("1.0.0-01", "*"), ("==1.0.0", "*"), ("1.0.0", "1.2.3-4 -2")]:
        try:
            satisfies(bv, br)
        except ValueError:
            continue
        raise AssertionError((bv, br))
    order = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
             "1.0.0-rc.1", "1.0.0"]
    assert all(_key(_parse_version(a)) < _key(_parse_version(b)) for a, b in zip(order, order[1:]))
    assert max_satisfying(["1.0.0+a", "bad", "1.0.0+b", "0.9.0"], "1") == "1.0.0+a"
    assert max_satisfying(["2.0.0"], "1") is None
    print("ok")
