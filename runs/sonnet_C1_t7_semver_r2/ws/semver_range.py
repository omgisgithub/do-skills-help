"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_PARTIAL_RE = re.compile(r"([0-9A-Za-z*]+)(?:\.([0-9A-Za-z*]+))?(?:\.([0-9A-Za-z*]+))?")
_NUM_RE = re.compile(_NUM)
_OPS = ("<=", ">=", "<", ">", "=", "^", "~")
_WILD = ("*", "x", "X")


def _parse_version(text):
    """Return (major, minor, patch, pre) where pre is a tuple of identifiers."""
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = _VERSION_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    pre = tuple(m.group(4).split(".")) if m.group(4) else ()
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _pre_key(pre):
    return [(0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre]


def _cmp(a, b):
    ka, kb = a[:3], b[:3]
    if ka != kb:
        return -1 if ka < kb else 1
    pa, pb = a[3], b[3]
    if not pa and not pb:
        return 0
    if not pa:
        return 1
    if not pb:
        return -1
    xa, xb = _pre_key(pa), _pre_key(pb)
    if xa == xb:
        return 0
    return -1 if xa < xb else 1


def _parse_partial(text):
    """Return (major, minor, patch, pre) with None for wildcard/missing parts."""
    if text[:1] == "v":
        text = text[1:]
    if _VERSION_RE.fullmatch(text):
        return _parse_version(text)
    if not _PARTIAL_RE.fullmatch(text):
        raise ValueError("invalid version: %r" % (text,))
    parts = text.split(".")
    nums = []
    wild = False
    for p in parts:
        if p in _WILD:
            wild = True
            nums.append(None)
        elif wild or not _NUM_RE.fullmatch(p):
            raise ValueError("invalid version: %r" % (text,))
        else:
            nums.append(int(p))
    nums += [None] * (3 - len(nums))
    return (nums[0], nums[1], nums[2], ())


_NONE = ("none", None)


def _lo(v):
    return (">=", (v[0] or 0, v[1] or 0, v[2] or 0, v[3]))


def _upper_excl(p):
    """Exclusive '-0' upper bound for a partial/full version at its precision."""
    M, m, _, _ = p
    if m is None:
        return ("<", (M + 1, 0, 0, ("0",)))
    return ("<", (M, m + 1, 0, ("0",)))


def _desugar(op, p):
    """Return list of (op, version) for operator `op` (may be '') on partial p."""
    M, m, pt, pre = p
    full = pt is not None
    if op in ("", "="):
        if M is None:
            return [_lo(p)]
        if full:
            return [("=", p)]
        return [_lo(p), _upper_excl(p)]
    if op == ">":
        if M is None:
            return [_NONE]
        if full:
            return [(">", p)]
        if m is None:
            return [(">=", (M + 1, 0, 0, ()))]
        return [(">=", (M, m + 1, 0, ()))]
    if op == ">=":
        return [_lo(p)]
    if op == "<":
        if M is None:
            return [_NONE]
        if full:
            return [("<", p)]
        return [("<", (M, m or 0, 0, ("0",)))]
    if op == "<=":
        if M is None:
            return [(">=", (0, 0, 0, ()))]
        if full:
            return [("<=", p)]
        return [_upper_excl(p)]
    if op == "~":
        if M is None:
            return [_lo(p)]
        if m is None:
            return [_lo(p), ("<", (M + 1, 0, 0, ("0",)))]
        return [_lo(p), ("<", (M, m + 1, 0, ("0",)))]
    if op == "^":
        if M is None:
            return [_lo(p)]
        if M > 0 or m is None:
            hi = (M + 1, 0, 0, ("0",))
        elif m > 0 or pt is None:
            hi = (0, m + 1, 0, ("0",))
        else:
            hi = (0, 0, pt + 1, ("0",))
        return [_lo(p), ("<", hi)]
    raise ValueError("invalid operator")


def _tokens(set_text):
    raw = set_text.split()
    items = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t in _OPS:
            if i + 1 >= len(raw):
                raise ValueError("dangling operator")
            items.append((t, raw[i + 1]))
            i += 2
            continue
        op = ""
        for o in _OPS:
            if t.startswith(o):
                op, t = o, t[len(o):]
                break
        if op and not t:
            raise ValueError("dangling operator")
        items.append((op, t))
        i += 1
    return items


def _parse_set(set_text):
    """Return list of (op, version, counts_for_prerelease)."""
    items = _tokens(set_text)
    out = []
    i = 0
    n = len(items)
    while i < n:
        op, t = items[i]
        if (op, t) == ("", "-"):
            raise ValueError("misplaced hyphen")
        if i + 1 < n and items[i + 1] == ("", "-"):
            if i + 2 >= n or op or items[i + 2][0] or items[i + 2][1] == "-":
                raise ValueError("invalid hyphen range")
            left = _parse_partial(t)
            right = _parse_partial(items[i + 2][1])
            out.extend(_flag(_desugar(">=", left), left))
            out.extend(_flag(_desugar("<=", right), right))
            i += 3
            continue
        p = _parse_partial(t)
        out.extend(_flag(_desugar(op, p), p))
        i += 1
    return out


def _flag(cmps, p):
    """Mark which comparators count for the prerelease rule."""
    if isinstance(cmps, tuple):
        cmps = [cmps]
    res = []
    for c, v in cmps:
        counts = c != "none" and bool(p[3]) and v[:4] == p
        res.append((c, v, counts))
    return res


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(s) for s in range_.split("||")]


def _test(c, v, target):
    if c == "none":
        return False
    r = _cmp(target, v)
    return {
        "=": r == 0, ">": r > 0, ">=": r >= 0, "<": r < 0, "<=": r <= 0,
    }[c]


def _match(ver, sets):
    for comps in sets:
        if not all(_test(c, v, ver) for c, v, _ in comps):
            continue
        if ver[3] and not any(
            counts and v[:3] == ver[:3] for _, v, counts in comps
        ):
            continue
        return True
    return False


def satisfies(version, range_):
    ver = _parse_version(version)
    return _match(ver, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best, best_v = None, None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if _match(v, sets) and (best_v is None or _cmp(v, best_v) > 0):
            best, best_v = s, v
    return best
