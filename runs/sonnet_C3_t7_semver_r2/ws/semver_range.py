"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_PART = r"(%s|[xX*])" % _NUM
_PARTIAL_RE = re.compile(r"%s(?:\.%s(?:\.%s)?)?" % (_PART, _PART, _PART))
_TOKEN_RE = re.compile(r"\s*(?:(<=|>=|<|>|=|~|\^)\s*)?(\S+)")
_HYPHEN_RE = re.compile(r"\s+-\s+")
_WILD = ("x", "X", "*")


def _pre_key(pre):
    ids = []
    for ident in pre:
        if ident.isdigit():
            ids.append((0, int(ident), ""))
        else:
            ids.append((1, 0, ident))
    return tuple(ids)


def _key(major, minor, patch, pre):
    """Sort key: (M, m, p, pre) where pre is a tuple of identifier strings."""
    if pre:
        return (major, minor, patch, 0, _pre_key(pre))
    return (major, minor, patch, 1, ())


def _parse_version(text):
    """Parse a full version; returns (major, minor, patch, pre_tuple)."""
    if not isinstance(text, str):
        raise ValueError("invalid version: %r" % (text,))
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = _FULL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    pre = tuple(m.group(4).split(".")) if m.group(4) else ()
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _parse_partial(text, allow_eq=False):
    """Returns (nums, pre): nums is a list of 0-3 ints (wildcards/missing dropped)."""
    s = text
    if s[:1] == "v" or (allow_eq and s[:1] == "="):
        s = s[1:]
    m = _FULL_RE.fullmatch(s)
    if m:
        pre = tuple(m.group(4).split(".")) if m.group(4) else ()
        return [int(m.group(1)), int(m.group(2)), int(m.group(3))], pre
    m = _PARTIAL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    nums = []
    seen_wild = False
    for g in m.groups():
        if g is None:
            continue
        if g in _WILD:
            seen_wild = True
        elif seen_wild:
            raise ValueError("invalid version: %r" % (text,))
        else:
            nums.append(int(g))
    return nums, ()


# A comparator is (op, (M, m, p, pre), counts) with op in <, <=, >, >=, =.
_LOWEST = (0, 0, 0, ("0",))


def _cmp(op, major, minor, patch, pre=(), counts=False):
    return (op, (major, minor, patch, pre), counts)


def _nothing():
    return [("<", _LOWEST, False)]


def _padded(nums):
    return (nums + [0, 0, 0])[:3]


def _upper(nums):
    """Exclusive upper bound just above the partial version `nums` (1-2 parts)."""
    if len(nums) == 1:
        return _cmp("<", nums[0] + 1, 0, 0, ("0",))
    return _cmp("<", nums[0], nums[1] + 1, 0, ("0",))


def _lower(nums, pre=(), counts=False):
    return _cmp(">=", *_padded(nums), pre=pre, counts=counts)


def _xrange(op, nums, pre):
    n = len(nums)
    counts = bool(pre)
    if op in ("", "="):
        if n == 0:
            return [_lower([])]
        if n == 3:
            return [_cmp("=", *nums, pre=pre, counts=counts)]
        return [_lower(nums), _upper(nums)]
    if op == ">":
        if n == 0:
            return _nothing()
        if n == 3:
            return [_cmp(">", *nums, pre=pre, counts=counts)]
        if n == 1:
            return [_cmp(">=", nums[0] + 1, 0, 0)]
        return [_cmp(">=", nums[0], nums[1] + 1, 0)]
    if op == ">=":
        return [_lower(nums, pre, counts)]
    if op == "<":
        if n == 0:
            return _nothing()
        if n == 3:
            return [_cmp("<", *nums, pre=pre, counts=counts)]
        return [_cmp("<", *_padded(nums), pre=("0",))]
    if op == "<=":
        if n == 0:
            return [_lower([])]
        if n == 3:
            return [_cmp("<=", *nums, pre=pre, counts=counts)]
        return [_upper(nums)]
    raise ValueError("invalid operator: %r" % (op,))


def _tilde(nums, pre):
    n = len(nums)
    if n == 0:
        return [_lower([])]
    return [_lower(nums, pre, bool(pre)), _upper(nums[:2] if n >= 2 else nums)]


def _caret(nums, pre):
    n = len(nums)
    if n == 0:
        return [_lower([])]
    lower = _lower(nums, pre, bool(pre))
    major = nums[0]
    if major > 0:
        upper = _cmp("<", major + 1, 0, 0, ("0",))
    elif n == 1:
        upper = _cmp("<", 1, 0, 0, ("0",))
    elif nums[1] > 0 or n == 2:
        upper = _cmp("<", 0, nums[1] + 1, 0, ("0",))
    else:
        upper = _cmp("<", 0, 0, nums[2] + 1, ("0",))
    return [lower, upper]


def _parse_set(text):
    s = text.strip()
    if not s:
        return []
    parts = _HYPHEN_RE.split(s)
    if len(parts) > 1:
        if len(parts) != 2:
            raise ValueError("invalid range: %r" % (text,))
        lo_nums, lo_pre = _parse_partial(parts[0])
        hi_nums, hi_pre = _parse_partial(parts[1])
        comps = [_lower(lo_nums, lo_pre, bool(lo_pre))]
        if len(hi_nums) == 3:
            comps.append(_cmp("<=", *hi_nums, pre=hi_pre, counts=bool(hi_pre)))
        elif hi_nums:
            comps.append(_upper(hi_nums))
        return comps
    comps = []
    pos = 0
    while pos < len(s):
        m = _TOKEN_RE.match(s, pos)
        if not m:
            break
        pos = m.end()
        op, tok = m.group(1) or "", m.group(2)
        nums, pre = _parse_partial(tok, allow_eq=(op == ""))
        if op == "~":
            comps.extend(_tilde(nums, pre))
        elif op == "^":
            comps.extend(_caret(nums, pre))
        else:
            comps.extend(_xrange(op, nums, pre))
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


def _test(version, comps):
    major, minor, patch, pre = version
    vkey = _key(*version)
    for op, cv, _ in comps:
        ckey = _key(*cv)
        if op == "<":
            ok = vkey < ckey
        elif op == "<=":
            ok = vkey <= ckey
        elif op == ">":
            ok = vkey > ckey
        elif op == ">=":
            ok = vkey >= ckey
        else:
            ok = vkey == ckey
        if not ok:
            return False
    if pre:
        return any(
            counts and cv[3] and cv[:3] == (major, minor, patch)
            for _, cv, counts in comps
        )
    return True


def _matches(version, sets):
    return any(_test(version, comps) for comps in sets)


def satisfies(version, range_):
    v = _parse_version(version)
    return _matches(v, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for item in versions:
        try:
            v = _parse_version(item)
        except ValueError:
            continue
        if not _matches(v, sets):
            continue
        k = _key(*v)
        if best_key is None or k > best_key:
            best, best_key = item, k
    return best
