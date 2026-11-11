"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_PART = r"(?:[xX*]|%s)" % _NUM
_PARTIAL_RE = re.compile(
    r"(%s)(?:\.(%s)(?:\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?)?)?"
    % (_PART, _PART, _PART, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")


class _Version(object):
    __slots__ = ("major", "minor", "patch", "pre", "key")

    def __init__(self, major, minor, patch, pre=None):
        self.major, self.minor, self.patch = major, minor, patch
        self.pre = pre  # tuple of identifier strings or None
        if pre is None:
            pk = (1,)
        else:
            pk = (0, tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre))
        self.key = (major, minor, patch, pk)

    def mmp(self):
        return (self.major, self.minor, self.patch)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("invalid version: %r" % (text,))
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = _VERSION_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    pre = tuple(m.group(4).split(".")) if m.group(4) else None
    return _Version(int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _parse_partial(text):
    """Return (major, minor, patch, pre); wildcards/missing parts are None."""
    s = text
    if s[:1] == "v":
        s = s[1:]
    m = _PARTIAL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid range part: %r" % (text,))
    nums = []
    for g in m.group(1, 2, 3):
        nums.append(None if g is None or g in "xX*" else int(g))
    # a wildcard must not be followed by a concrete number
    for i in range(1, 3):
        if nums[i - 1] is None and m.group(i + 1) is not None and nums[i] is not None:
            raise ValueError("invalid range part: %r" % (text,))
    if m.group(4) is not None and None in nums:
        raise ValueError("invalid range part: %r" % (text,))
    pre = tuple(m.group(4).split(".")) if m.group(4) else None
    return nums[0], nums[1], nums[2], pre


def _v(major, minor, patch, pre=None):
    return _Version(major, minor, patch, pre)


def _upper(major, minor, patch, pre=None):
    """Exclusive upper bound `<X-0`."""
    return ("<", _v(major, minor, patch, ("0",)), False)


def _bump_partial(M, m):
    """Exclusive upper bound covering the partial M[.m]."""
    if m is None:
        return _upper(M + 1, 0, 0)
    return _upper(M, m + 1, 0)


_NOTHING = ("never", None, False)


def _comparators(op, text):
    M, m, p, pre = _parse_partial(text)
    full = p is not None
    counts = pre is not None
    if op in ("", "="):
        if M is None:
            return [(">=", _v(0, 0, 0), False)]
        if full:
            return [("=", _v(M, m, p, pre), counts)]
        return [(">=", _v(M, m or 0, 0), False), _bump_partial(M, m)]
    if op == ">":
        if M is None:
            return [_NOTHING]
        if full:
            return [(">", _v(M, m, p, pre), counts)]
        if m is None:
            return [(">=", _v(M + 1, 0, 0), False)]
        return [(">=", _v(M, m + 1, 0), False)]
    if op == ">=":
        if M is None:
            return [(">=", _v(0, 0, 0), False)]
        return [(">=", _v(M, m or 0, p or 0, pre), counts)]
    if op == "<":
        if M is None:
            return [_NOTHING]
        if full:
            return [("<", _v(M, m, p, pre), counts)]
        return [_upper(M, m or 0, 0)]
    if op == "<=":
        if M is None:
            return [(">=", _v(0, 0, 0), False)]
        if full:
            return [("<=", _v(M, m, p, pre), counts)]
        return [_bump_partial(M, m)]
    if op == "~":
        if M is None:
            return [(">=", _v(0, 0, 0), False)]
        return [(">=", _v(M, m or 0, p or 0, pre), counts), _bump_partial(M, m)]
    if op == "^":
        if M is None:
            return [(">=", _v(0, 0, 0), False)]
        low = (">=", _v(M, m or 0, p or 0, pre), counts)
        if M > 0:
            high = _upper(M + 1, 0, 0)
        elif m is None:
            high = _upper(1, 0, 0)
        elif m > 0:
            high = _upper(0, m + 1, 0)
        elif p is None:
            high = _upper(0, 1, 0)
        else:
            high = _upper(0, 0, p + 1)
        return [low, high]
    raise ValueError("invalid operator: %r" % (op,))


def _split_op(token):
    for op in _OPS:
        if token.startswith(op):
            return op, token[len(op):]
    return "", token


def _hyphen(left, right):
    lop, ltext = _split_op(left)
    rop, rtext = _split_op(right)
    if lop or rop:
        raise ValueError("invalid hyphen range")
    M, m, p, pre = _parse_partial(ltext)
    out = []
    if M is None:
        out.append((">=", _v(0, 0, 0), False))
    else:
        out.append((">=", _v(M, m or 0, p or 0, pre), pre is not None))
    M, m, p, pre = _parse_partial(rtext)
    if M is None:
        pass
    elif p is not None:
        out.append(("<=", _v(M, m, p, pre), pre is not None))
    else:
        out.append(_bump_partial(M, m))
    return out


def _parse_set(text):
    raw = text.split()
    tokens = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t in _OPS:
            if i + 1 >= len(raw):
                raise ValueError("dangling operator")
            t += raw[i + 1]
            i += 1
        tokens.append(t)
        i += 1
    comps = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "-":
            raise ValueError("misplaced hyphen")
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError("dangling hyphen")
            comps.extend(_hyphen(t, tokens[i + 2]))
            i += 3
            continue
        op, rest = _split_op(t)
        comps.extend(_comparators(op, rest))
        i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


def _match_op(op, v, c):
    if op == "=":
        return v.key == c.key
    if op == ">":
        return v.key > c.key
    if op == ">=":
        return v.key >= c.key
    if op == "<":
        return v.key < c.key
    if op == "<=":
        return v.key <= c.key
    return False


def _set_matches(comps, v):
    for op, c, _ in comps:
        if not _match_op(op, v, c):
            return False
    if v.pre is not None:
        return any(
            counts and c.pre is not None and c.mmp() == v.mmp()
            for _, c, counts in comps
        )
    return True


def _check(v, sets):
    return any(_set_matches(s, v) for s in sets)


def satisfies(version, range_):
    v = _parse_version(version)
    sets = _parse_range(range_)
    return _check(v, sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if _check(v, sets) and (best_key is None or v.key > best_key):
            best, best_key = s, v.key
    return best
