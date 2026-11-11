"""Reference solution for t7_semver (hidden from agents)."""
import re

_NUM = r"(?:0|[1-9]\d*)"
_ID = r"[0-9A-Za-z-]+"
_VER = re.compile(r"^\s*[v=]?(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?\s*$"
                  % (_NUM, _NUM, _NUM, _ID, _ID, _ID, _ID))
_XR = r"(?:x|X|\*|%s)" % _NUM
_PARTIAL = re.compile(r"^[v=]?(%s)(?:\.(%s)(?:\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?)?)?$"
                      % (_XR, _XR, _XR, _ID, _ID, _ID, _ID))


class V:
    __slots__ = ("major", "minor", "patch", "pre")

    def __init__(self, major, minor, patch, pre=()):
        self.major, self.minor, self.patch, self.pre = major, minor, patch, tuple(pre)

    def key(self):
        pre = self.pre
        if not pre:
            pk = (1,)
        else:
            pk = (0,) + tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre)
            # shorter prerelease is lower when prefix equal: compare tuples elementwise,
            # a prefix tuple is lower in Python too.
        return (self.major, self.minor, self.patch, pk)

    def tup(self):
        return (self.major, self.minor, self.patch)


def _check_pre(pre):
    for p in pre:
        if p.isdigit() and len(p) > 1 and p[0] == "0":
            raise ValueError("leading zero in prerelease")


def parse_version(s):
    if not isinstance(s, str):
        raise ValueError("not a string")
    m = _VER.match(s)
    if not m:
        raise ValueError("invalid version %r" % s)
    pre = tuple(m.group(4).split(".")) if m.group(4) else ()
    _check_pre(pre)
    return V(int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _cmp(a, b):
    ka, kb = a.key(), b.key()
    return (ka > kb) - (ka < kb)


ANY = ("any",)
NONE = ("none",)


class Comp:
    """op in < <= > >= =, ver V, counts: whether it may admit prereleases of its tuple."""

    def __init__(self, op, ver, counts):
        self.op, self.ver, self.counts = op, ver, counts

    def test(self, v):
        c = _cmp(v, self.ver)
        return {"<": c < 0, "<=": c <= 0, ">": c > 0, ">=": c >= 0, "=": c == 0}[self.op]


def _isx(p):
    return p is None or p in ("x", "X", "*")


def _parse_partial(s):
    m = _PARTIAL.match(s)
    if not m:
        raise ValueError("invalid version in range: %r" % s)
    ma, mi, pa, pre = m.group(1), m.group(2), m.group(3), m.group(4)
    parts = [ma, mi, pa]
    # once a part is x/missing, the rest must be x/missing
    seen_x = False
    for p in parts:
        if _isx(p):
            seen_x = True
        elif seen_x:
            raise ValueError("number after wildcard")
    if (pre or m.group(5)) and any(_isx(p) for p in parts):
        raise ValueError("prerelease on partial")
    pre_t = tuple(pre.split(".")) if pre else ()
    _check_pre(pre_t)
    nums = [None if _isx(p) else int(p) for p in parts]
    return nums, pre_t


def _lo(n):  # fill a partial with zeros
    return V(n[0] or 0, n[1] or 0, n[2] or 0)


def _upper_excl(n):  # partial n (at least major given) -> exclusive upper bound of the x-range
    if n[1] is None:
        return V(n[0] + 1, 0, 0, ("0",))
    return V(n[0], n[1] + 1, 0, ("0",))


def _comparators(tok):
    """Return list of Comp, or [] for any, or None for match-nothing."""
    m = re.match(r"^(<=|>=|<|>|=|~|\^)?(.*)$", tok)
    op, rest = m.group(1) or "", m.group(2)
    if rest == "":
        raise ValueError("operator without version")
    nums, pre = _parse_partial(rest)
    full = nums[2] is not None
    if op in ("", "="):
        if full:
            return [Comp("=", V(*nums, pre), bool(pre))]
        if nums[0] is None:
            return []
        return [Comp(">=", _lo(nums), False), Comp("<", _upper_excl(nums), False)]
    if op in ("<", "<=", ">", ">="):
        if nums[0] is None:
            return [] if op in ("<=", ">=") else None
        if full:
            return [Comp(op, V(*nums, pre), bool(pre))]
        if op == ">=":
            return [Comp(">=", _lo(nums), False)]
        if op == ">":
            if nums[1] is None:
                return [Comp(">=", V(nums[0] + 1, 0, 0), False)]
            return [Comp(">=", V(nums[0], nums[1] + 1, 0), False)]
        if op == "<":
            return [Comp("<", V(nums[0], nums[1] or 0, 0, ("0",)), False)]
        return [Comp("<", _upper_excl(nums), False)]  # <=
    if op == "~":
        if nums[0] is None:
            return []
        lo = V(nums[0], nums[1] or 0, nums[2] or 0, pre)
        if nums[1] is None:
            hi = V(nums[0] + 1, 0, 0, ("0",))
        else:
            hi = V(nums[0], nums[1] + 1, 0, ("0",))
        return [Comp(">=", lo, bool(pre)), Comp("<", hi, False)]
    # caret
    if nums[0] is None:
        return []
    ma, mi, pa = nums
    lo = V(ma, mi or 0, pa or 0, pre)
    if ma > 0:
        hi = V(ma + 1, 0, 0, ("0",))
    elif mi is None:
        hi = V(1, 0, 0, ("0",))
    elif mi > 0:
        hi = V(0, mi + 1, 0, ("0",))
    elif pa is None:
        hi = V(0, 1, 0, ("0",))
    else:
        hi = V(0, 0, pa + 1, ("0",))
    return [Comp(">=", lo, bool(pre)), Comp("<", hi, False)]


def _parse_set(s):
    s = s.strip()
    if s == "":
        return []
    hy = re.match(r"^(\S+)\s+-\s+(\S+)$", s)
    if hy:
        ln, lp = _parse_partial(hy.group(1))
        rn, rp = _parse_partial(hy.group(2))
        comps = []
        if ln[0] is not None:
            lo = V(ln[0], ln[1] or 0, ln[2] or 0, lp)
            comps.append(Comp(">=", lo, bool(lp)))
        if rn[0] is not None:
            if rn[2] is not None:
                comps.append(Comp("<=", V(*rn, rp), bool(rp)))
            else:
                comps.append(Comp("<", _upper_excl(rn), False))
        return comps
    # join an operator separated from its version by spaces
    out = []
    raw = s.split()
    i = 0
    while i < len(raw):
        t = raw[i]
        if t in ("<", "<=", ">", ">=", "=", "~", "^") and i + 1 < len(raw):
            t = t + raw[i + 1]
            i += 1
        if t == "-":
            raise ValueError("bad hyphen")
        out.append(t)
        i += 1
    comps = []
    for t in out:
        c = _comparators(t)
        if c is None:
            return None
        comps.extend(c)
    return comps


def _parse_range(r):
    if not isinstance(r, str):
        raise ValueError("range must be str")
    return [_parse_set(p) for p in r.split("||")]


def _test_set(comps, v):
    if comps is None:
        return False
    if not all(c.test(v) for c in comps):
        return False
    if v.pre:
        return any(c.counts and c.ver.pre and c.ver.tup() == v.tup() for c in comps)
    return True


def satisfies(version, range_):
    v = parse_version(version)
    sets = _parse_range(range_)
    return any(_test_set(s, v) for s in sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best, bestv = None, None
    for s in versions:
        try:
            v = parse_version(s)
        except ValueError:
            continue
        if any(_test_set(x, v) for x in sets):
            if bestv is None or _cmp(v, bestv) > 0:
                best, bestv = s, v
    return best
