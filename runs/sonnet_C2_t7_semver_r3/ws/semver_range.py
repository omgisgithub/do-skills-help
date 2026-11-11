"""npm-style version range matching. See TASK.md for the exact spec."""
import re

_N = r"0|[1-9][0-9]*"
_PRE = rf"(?:{_N}|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
_BLD = r"[0-9A-Za-z-]+"
_PART = re.compile(
    rf"v?({_N}|[xX*])(?:\.({_N}|[xX*]))?(?:\.({_N}|[xX*]))?"
    rf"(?:-({_PRE}(?:\.{_PRE})*))?(?:\+({_BLD}(?:\.{_BLD})*))?"
)
_OP = re.compile(r"<=|>=|<|>|=|\^|~")
_ZERO_PRE = ((0, 0),)


def _ver(M, m, p, pre=None):
    # Sort key: a prerelease sorts below the plain release (flag 0 < 1).
    return (M, m, p, 0 if pre else 1, pre or ())


def _pre_key(s):
    return tuple((0, int(i)) if i.isdigit() else (1, i) for i in s.split("."))


def _partial(s):
    """Parse 'v1.2.x' style text into (M, m, p, pre); wildcards/missing are None."""
    mt = _PART.fullmatch(s)
    if not mt:
        raise ValueError(f"invalid version: {s!r}")
    nums = [None if g is None or g in "xX*" else int(g) for g in mt.groups()[:3]]
    given = [g is not None for g in mt.groups()[:3]]
    for i in (1, 2):  # a wildcard/missing part may only be followed by wildcard/missing
        if nums[i] is not None and nums[i - 1] is None:
            raise ValueError(f"invalid version: {s!r}")
    if mt.group(4) is not None and None in nums:
        raise ValueError(f"invalid version: {s!r}")
    if mt.group(5) is not None and None in nums:
        raise ValueError(f"invalid version: {s!r}")
    return (*nums, _pre_key(mt.group(4)) if mt.group(4) else None)


def _parse_version(v):
    if not isinstance(v, str):
        raise ValueError("version must be a string")
    v = v.strip()
    if v[:1] == "=":
        v = v[1:]
    M, m, p, pre = _partial(v)
    if p is None:
        raise ValueError(f"invalid version: {v!r}")
    return _ver(M, m, p, pre)


def _bump(M, m, pre=None):
    return _ver(M + 1, 0, 0, pre) if m is None else _ver(M, m + 1, 0, pre)


_NOTHING = ("<", _ver(0, 0, 0, _ZERO_PRE), False)


def _desugar(op, M, m, p, pre):
    """Return comparators (op, key, written_with_prerelease)."""
    flag = pre is not None
    low = _ver(M or 0, m or 0, p or 0, pre)
    if M is None:
        return {"": [(">=", low, False)], "=": [(">=", low, False)], ">=": [(">=", low, False)],
                "<=": [(">=", low, False)], "~": [(">=", low, False)], "^": [(">=", low, False)],
                ">": [_NOTHING], "<": [_NOTHING]}[op]
    full = p is not None
    if op in ("", "="):
        if full:
            return [("=", low, flag)]
        return [(">=", low, False), ("<", _bump(M, m, _ZERO_PRE), False)]
    if op == ">=":
        return [(">=", low, flag)]
    if op == "<":
        return [("<", low, flag)] if full else [("<", _ver(M, m or 0, 0, _ZERO_PRE), False)]
    if op == ">":
        return [(">", low, flag)] if full else [(">=", _bump(M, m), False)]
    if op == "<=":
        return [("<=", low, flag)] if full else [("<", _bump(M, m, _ZERO_PRE), False)]
    if op == "~":
        return [(">=", low, flag), ("<", _bump(M, m, _ZERO_PRE), False)]
    # caret: bump the left-most non-zero given part
    if M > 0 or m is None:
        hi = _ver(M + 1, 0, 0, _ZERO_PRE)
    elif m > 0 or p is None:
        hi = _ver(0, m + 1, 0, _ZERO_PRE)
    else:
        hi = _ver(0, 0, p + 1, _ZERO_PRE)
    return [(">=", low, flag), ("<", hi, False)]


def _parse_set(s):
    toks, out, i = s.split(), [], 0
    # glue a lone operator to the following token
    glued = []
    while toks:
        t = toks.pop(0)
        if _OP.fullmatch(t):
            if not toks:
                raise ValueError("dangling operator")
            t += toks.pop(0)
        glued.append(t)
    while i < len(glued):
        if i + 1 < len(glued) and glued[i + 1] == "-":
            if i + 2 >= len(glued):
                raise ValueError("dangling hyphen")
            out += _desugar(">=", *_partial(glued[i])) + _desugar("<=", *_partial(glued[i + 2]))
            i += 3
            continue
        mt = _OP.match(glued[i])
        op = mt.group() if mt else ""
        out += _desugar(op, *_partial(glued[i][len(op):]))
        i += 1
    return out


def _parse_range(r):
    if not isinstance(r, str):
        raise ValueError("range must be a string")
    return [_parse_set(s) for s in r.split("||")]


_TESTS = {
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b, "=": lambda a, b: a == b,
}


def _match(v, parsed):
    for cset in parsed:
        if not all(_TESTS[op](v, k) for op, k, _ in cset):
            continue
        if v[3] == 1 or any(f and k[:3] == v[:3] for _, k, f in cset):
            return True
    return False


def satisfies(version, range_):
    v = _parse_version(version)
    return _match(v, _parse_range(range_))


def max_satisfying(versions, range_):
    parsed = _parse_range(range_)
    best, best_key = None, None
    for s in versions:
        try:
            k = _parse_version(s)
        except ValueError:
            continue
        if _match(k, parsed) and (best_key is None or k > best_key):
            best, best_key = s, k
    return best


if __name__ == "__main__":
    ok = [("1.2.3", "^1.2.3"), ("1.9.9", "^1.2.3"), ("1.2.3-beta.4", "^1.2.3-beta.2"),
          ("0.0.3", "^0.0.3"), ("1.2.9", "1.2.x"), ("2.0.0", ">1"), ("2.3.4", "1.2.3 - 2.3"),
          ("1.0.0", ""), ("1.0.0", "<1 || >= 1.0.0"), ("v1.0.0+b", "=1.0.0"), ("0.9.0", "^0.x"),
          ("1.2.3", "1.2.3 - 2"), ("3.0.0", "*"), ("1.3.0", "<=1.2 || ~1.3")]
    bad = [("1.2.4-alpha", "^1.2.3"), ("1.0.0-rc.1", "*"), ("1.3.0", "~1.2"), ("0.0.4", "^0.0.3"),
           ("1.0.0", ">*"), ("1.0.0", "<*"), ("3.0.0", "1.2.3 - 2"), ("2.0.0-0", "^1.2.3"),
           ("1.2.3", "^0.0")]
    for v, r in ok:
        assert satisfies(v, r), (v, r)
    for v, r in bad:
        assert not satisfies(v, r), (v, r)
    for r in ["~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=a.b.c", "> = 1", "- 1", "1.x.3", "1.2.x-a", "01.2.3", "1.2 -2"]:
        try:
            satisfies("1.0.0", r)
        except ValueError:
            continue
        raise AssertionError(r)
    for v in ["1.2", "01.0.0", "1.0.0-01", "1.0.0-", "1.0.0+", "vv1.0.0", "1.0.0-a..b"]:
        try:
            satisfies(v, "*")
        except ValueError:
            continue
        raise AssertionError(v)
    order = "1.0.0-alpha 1.0.0-alpha.1 1.0.0-alpha.beta 1.0.0-beta 1.0.0-beta.2 1.0.0-beta.11 1.0.0-rc.1 1.0.0".split()
    ks = [_parse_version(x) for x in order]
    assert ks == sorted(ks) and len(set(ks)) == len(ks)
    assert max_satisfying(["1.0.0+a", "bad", "1.0.0+b", "0.5.0"], "1") == "1.0.0+a"
    assert max_satisfying(["2.0.0"], "1") is None
    print("ok")
