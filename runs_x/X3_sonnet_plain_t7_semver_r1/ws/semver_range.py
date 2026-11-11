"""npm-style version range matching. See TASK.md for the exact spec."""
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    r"^(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?$"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_NUM_RE = re.compile(r"^%s$" % _NUM)
_WILD = ("*", "x", "X")
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")


def _pre_key(pre):
    out = []
    for ident in pre.split("."):
        if ident.isdigit():
            out.append((0, int(ident), ""))
        else:
            out.append((1, 0, ident))
    return tuple(out)


def _key(major, minor, patch, pre):
    """Sort key; pre is a tuple key or None (a release)."""
    if pre is None:
        return (major, minor, patch, 1, ())
    return (major, minor, patch, 0, pre)


_ZERO_PRE = ((0, 0, ""),)


def _strip_prefix(s):
    if s[:1] in ("v", "="):
        return s[1:]
    return s


def _parse_version(s):
    if not isinstance(s, str):
        raise ValueError("invalid version: %r" % (s,))
    m = _FULL_RE.match(_strip_prefix(s.strip()))
    if not m:
        raise ValueError("invalid version: %r" % (s,))
    pre = _pre_key(m.group(4)) if m.group(4) else None
    return _key(int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _parse_partial(s, allow_eq=True):
    """Return (parts, pre_key) where parts is the list of leading numeric
    components (0-3 long)."""
    if s[:1] == "v" or (allow_eq and s[:1] == "="):
        s = s[1:]
    m = _FULL_RE.match(s)
    if m:
        pre = _pre_key(m.group(4)) if m.group(4) else None
        return [int(m.group(1)), int(m.group(2)), int(m.group(3))], pre
    parts = s.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError("invalid range component: %r" % (s,))
    nums = []
    wild = False
    for p in parts:
        if p in _WILD:
            wild = True
        elif _NUM_RE.match(p) and not wild:
            nums.append(int(p))
        else:
            raise ValueError("invalid range component: %r" % (s,))
    return nums, None


_NOTHING = ("<", _key(0, 0, 0, _ZERO_PRE))


def _ver(nums, pre=None):
    n = list(nums) + [0] * (3 - len(nums))
    return _key(n[0], n[1], n[2], pre)


def _ver0(major, minor, patch):
    """Upper-bound style version X.Y.Z-0."""
    return _key(major, minor, patch, _ZERO_PRE)


def _bump(nums, level):
    """Version-with-'-0' of nums truncated to `level` parts, incremented at
    position level-1."""
    n = list(nums[:level]) + [0] * (3 - level)
    n[level - 1] += 1
    return _ver0(*n)


def _desugar(op, nums, pre, tagged):
    n = len(nums)
    if n == 3 and pre is not None:
        tagged.add(tuple(nums))
    full = _ver(nums, pre) if n == 3 else None
    if op in ("", "="):
        if n == 3:
            return [("=", full)]
        if n == 0:
            return [(">=", _ver([]))]
        return [(">=", _ver(nums)), ("<", _bump(nums, n))]
    if op == ">":
        if n == 3:
            return [(">", full)]
        if n == 0:
            return [_NOTHING]
        return [(">=", _bump(nums, n)[:3] + (1, ()))]
    if op == ">=":
        return [(">=", full if n == 3 else _ver(nums))]
    if op == "<":
        if n == 3:
            return [("<", full)]
        if n == 0:
            return [_NOTHING]
        return [("<", _ver0(*(list(nums) + [0] * (3 - n))))]
    if op == "<=":
        if n == 3:
            return [("<=", full)]
        if n == 0:
            return [(">=", _ver([]))]
        return [("<", _bump(nums, n))]
    if op == "~":
        if n == 0:
            return [(">=", _ver([]))]
        lo = full if n == 3 else _ver(nums)
        return [(">=", lo), ("<", _bump(nums, 1 if n == 1 else 2))]
    if op == "^":
        if n == 0:
            return [(">=", _ver([]))]
        lo = full if n == 3 else _ver(nums)
        if nums[0] > 0:
            hi = _bump(nums, 1)
        elif n == 1:
            hi = _bump(nums, 1)
        elif nums[1] > 0 or n == 2:
            hi = _bump(nums, 2)
        else:
            hi = _bump(nums, 3)
        return [(">=", lo), ("<", hi)]
    raise ValueError("invalid operator")


def _split_op(tok):
    for op in _OPS:
        if tok.startswith(op):
            return op, tok[len(op):]
    return "", tok


def _parse_set(text):
    toks = text.split()
    merged = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in _OPS:
            if i + 1 >= len(toks):
                raise ValueError("dangling operator")
            t = t + toks[i + 1]
            i += 1
        merged.append(t)
        i += 1

    comps = []
    tagged = set()
    i = 0
    while i < len(merged):
        t = merged[i]
        if i + 1 < len(merged) and merged[i + 1] == "-":
            if i + 2 >= len(merged):
                raise ValueError("dangling hyphen")
            lo_t, hi_t = t, merged[i + 2]
            for x in (lo_t, hi_t):
                if x == "-" or _split_op(x)[0]:
                    raise ValueError("invalid hyphen range")
            lo, lopre = _parse_partial(lo_t)
            hi, hipre = _parse_partial(hi_t)
            comps += _desugar(">=", lo, lopre, tagged)
            comps += _desugar("<=", hi, hipre, tagged)
            i += 3
            continue
        if t == "-":
            raise ValueError("dangling hyphen")
        op, rest = _split_op(t)
        if not rest or rest[:1] == "=":
            raise ValueError("invalid comparator: %r" % (t,))
        nums, pre = _parse_partial(rest, allow_eq=False)
        comps += _desugar(op, nums, pre, tagged)
        i += 1
    return comps, tagged


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


_CMP = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "=": lambda a, b: a == b,
}


def _match(key, parsed):
    has_pre = key[3] == 0
    for comps, tagged in parsed:
        if not all(_CMP[op](key, v) for op, v in comps):
            continue
        if has_pre and key[:3] not in tagged:
            continue
        return True
    return False


def satisfies(version, range_):
    key = _parse_version(version)
    parsed = _parse_range(range_)
    return _match(key, parsed)


def max_satisfying(versions, range_):
    parsed = _parse_range(range_)
    best = None
    best_key = None
    for v in versions:
        try:
            key = _parse_version(v)
        except ValueError:
            continue
        if _match(key, parsed) and (best_key is None or key > best_key):
            best, best_key = v, key
    return best
