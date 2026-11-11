"""npm-style version range matching. See TASK.md for the exact spec."""
import re

_NUM = r"0|[1-9][0-9]*"
_PRE = rf"(?:{_NUM}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BLD = r"[0-9A-Za-z-]+"
_X = rf"(?:[xX*]|{_NUM})"
_PART = re.compile(
    rf"({_X})(?:\.({_X})(?:\.({_X})(?:-({_PRE}(?:\.{_PRE})*))?(?:\+({_BLD}(?:\.{_BLD})*))?)?)?"
)
_OP = re.compile(r"(<=|>=|<|>|=|~|\^)?(.*)")
# lowest possible prerelease of a version: keeps prereleases of the next version out
_NEVER = ("<", (0, 0, 0, ("0",)), False)


def _parse(s, prefix):
    """Return ((major, minor, patch), pre); missing/wildcard parts are None."""
    if not isinstance(s, str):
        raise ValueError(f"invalid version: {s!r}")
    s = s.strip()
    if s[:1] in prefix and s[:1]:
        s = s[1:]
    m = _PART.fullmatch(s)
    if not m:
        raise ValueError(f"invalid version: {s!r}")
    nums = tuple(None if g is None or g in "xX*" else int(g) for g in m.groups()[:3])
    for a, b in zip(nums, nums[1:]):
        if a is None and b is not None:
            raise ValueError(f"invalid version: {s!r}")
    pre = m.group(4)
    if (pre or m.group(5)) and None in nums:
        raise ValueError(f"invalid version: {s!r}")
    return nums, (tuple(pre.split(".")) if pre else None)


def _version(s):
    nums, pre = _parse(s, "v=")
    if None in nums:
        raise ValueError(f"invalid version: {s!r}")
    return (*nums, pre)


def _key(v):
    if v[3] is None:
        return (v[:3], 1, ())
    return (v[:3], 0, tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in v[3]))


def _upper(nums, caret=False):
    """Exclusive upper bound (as a '<' comparator) for a tilde/caret/partial range."""
    M, m, p = nums
    if caret and M == 0 and m is not None and (m > 0 or p is not None):
        v = (0, m, p + 1, ("0",)) if m == 0 else (0, m + 1, 0, ("0",))
    elif m is None or (caret and M > 0):
        v = (M + 1, 0, 0, ("0",))
    else:
        v = (M, m + 1, 0, ("0",))
    return ("<", v, False)


def _comps(op, nums, pre):
    if nums[0] is None:
        return [_NEVER] if op in ("<", ">") else [(">=", (0, 0, 0, None), False)]
    lo = (nums[0], nums[1] or 0, nums[2] or 0, pre)
    w = pre is not None
    full = nums[2] is not None
    if op in ("", "="):
        return [("=", lo, w)] if full else [(">=", lo, False), _upper(nums)]
    if op == ">":
        if full:
            return [(">", lo, w)]
        up = _upper(nums)[1]
        return [(">=", up[:3] + (None,), False)]
    if op == ">=":
        return [(">=", lo, w)]
    if op == "<":
        return [("<", lo, w)] if full else [("<", lo[:3] + (("0",),), False)]
    if op == "<=":
        return [("<=", lo, w)] if full else [_upper(nums)]
    return [(">=", lo, w), _upper(nums, caret=op == "^")]


def _parse_set(s):
    toks = re.sub(r"(<=|>=|<|>|=|~|\^)\s+", r"\1", s).split()
    comps = []
    i = 0
    while i < len(toks):
        if i + 1 < len(toks) and toks[i + 1] == "-":
            if i + 2 >= len(toks):
                raise ValueError(f"invalid range: {s!r}")
            comps += _comps(">=", *_parse(toks[i], "v"))
            hi = _parse(toks[i + 2], "v")
            comps += _comps("<=", *hi) if hi[0][0] is not None else []
            i += 3
        else:
            op, rest = _OP.fullmatch(toks[i]).groups()
            comps += _comps(op or "", *_parse(rest, "v"))
            i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_parse_set(s) for s in range_.split("||")]


_CMP = {
    "=": lambda a, b: a == b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


def _match(v, sets):
    k = _key(v)
    for comps in sets:
        if all(_CMP[op](k, _key(c)) for op, c, _ in comps) and (
            v[3] is None or any(w and c[:3] == v[:3] for _, c, w in comps)
        ):
            return True
    return False


def satisfies(version, range_):
    v = _version(version)
    return _match(v, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = best_key = None
    for s in versions:
        try:
            v = _version(s)
        except ValueError:
            continue
        if _match(v, sets) and (best is None or _key(v) > best_key):
            best, best_key = s, _key(v)
    return best
