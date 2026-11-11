"""npm-style version range matching. See TASK.md for the exact spec."""
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_PRE = _PRE_ID + r"(?:\." + _PRE_ID + r")*"
_BUILD = _BUILD_ID + r"(?:\." + _BUILD_ID + r")*"

_VERSION_RE = re.compile(
    r"(" + _NUM + r")\.(" + _NUM + r")\.(" + _NUM + r")"
    r"(?:-(" + _PRE + r"))?(?:\+(" + _BUILD + r"))?"
)
_PART = r"(" + _NUM + r"|[xX*])"
_PARTIAL_RE = re.compile(
    _PART + r"(?:\." + _PART + r"(?:\." + _PART + r"(?:-(" + _PRE + r"))?(?:\+(" + _BUILD + r"))?)?)?"
)
_OPS = ("<=", ">=", "<", ">", "=")
_ANY = ((">=", (0, 0, 0, (1,))),)
_NOTHING = (("nothing", None),)


def _pre_key(pre):
    if pre is None:
        return (1,)
    ids = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split("."))
    return (0, ids)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("invalid version: %r" % (text,))
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = _VERSION_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), _pre_key(m.group(4)))


def _parse_partial(text, allow_v=True):
    """Return (nums, pre) where nums is the list of specified numbers (wildcards stop it)."""
    s = text
    if allow_v and s[:1] == "v":
        s = s[1:]
    m = _PARTIAL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid range part: %r" % (text,))
    parts = [m.group(1), m.group(2), m.group(3)]
    nums = []
    wild = False
    for p in parts:
        if p is None:
            wild = True  # missing, same as wildcard
            continue
        if p in ("x", "X", "*"):
            wild = True
        elif wild:
            raise ValueError("invalid range part: %r" % (text,))
        else:
            nums.append(int(p))
    pre = m.group(4)
    if pre is not None or m.group(5) is not None:
        if len(nums) != 3:
            raise ValueError("invalid range part: %r" % (text,))
    return nums, pre


def _v(maj, mi, pa, pre=None):
    return (maj, mi, pa, _pre_key(pre))


def _lt0(maj, mi, pa):
    """Exclusive upper bound `<maj.mi.pa-0`."""
    return ("<", (maj, mi, pa, (0, ((0, 0, ""),))))


def _full(nums, pre=None):
    n = nums + [0] * (3 - len(nums))
    return _v(n[0], n[1], n[2], pre)


def _bump(nums):
    """Upper bound (exclusive, -0) for a partial with 1 or 2 numbers."""
    if len(nums) == 1:
        return _lt0(nums[0] + 1, 0, 0)
    return _lt0(nums[0], nums[1] + 1, 0)


def _primitive(op, text):
    nums, pre = _parse_partial(text)
    n = len(nums)
    if n == 3:
        v = _full(nums, pre)
        return [(op if op else "=", v)], ([v[:3]] if pre else [])
    if op in ("", "="):
        if n == 0:
            return list(_ANY), []
        return [(">=", _full(nums)), _bump(nums)], []
    if op == ">":
        if n == 0:
            return list(_NOTHING), []
        return [(">=", _full([nums[0] + 1] if n == 1 else [nums[0], nums[1] + 1]))], []
    if op == ">=":
        return [(">=", _full(nums))] if n else list(_ANY), []
    if op == "<":
        if n == 0:
            return list(_NOTHING), []
        return [_lt0(*_full(nums)[:3])], []
    # "<="
    if n == 0:
        return list(_ANY), []
    return [_bump(nums)], []


def _tilde(text):
    nums, pre = _parse_partial(text)
    if not nums:
        return list(_ANY), []
    lo = _full(nums, pre)
    hi = _lt0(nums[0] + 1, 0, 0) if len(nums) == 1 else _lt0(nums[0], nums[1] + 1, 0)
    return [(">=", lo), hi], ([lo[:3]] if pre else [])


def _caret(text):
    nums, pre = _parse_partial(text)
    if not nums:
        return list(_ANY), []
    f = _full(nums, pre)
    M, m, p = f[:3]
    if M > 0 or len(nums) == 1:
        hi = _lt0(M + 1, 0, 0)
    elif m > 0 or len(nums) == 2:
        hi = _lt0(0, m + 1, 0)
    else:
        hi = _lt0(0, 0, p + 1)
    return [(">=", f), hi], ([f[:3]] if pre else [])


def _hyphen(left, right):
    ln, lpre = _parse_partial(left)
    rn, rpre = _parse_partial(right)
    cmps, pres = [], []
    if ln:
        lo = _full(ln, lpre)
        cmps.append((">=", lo))
        if lpre:
            pres.append(lo[:3])
    if len(rn) == 3:
        hi = _full(rn, rpre)
        cmps.append(("<=", hi))
        if rpre:
            pres.append(hi[:3])
    elif rn:
        cmps.append(_bump(rn))
    return cmps, pres


def _parse_set(text):
    toks = text.split()
    if not toks:
        return [], []
    if "-" in toks:
        if len(toks) != 3 or toks[1] != "-" or toks[0] == "-" or toks[2] == "-":
            raise ValueError("invalid range: %r" % (text,))
        return _hyphen(toks[0], toks[2])
    cmps, pres = [], []
    i = 0
    while i < len(toks):
        t = toks[i]
        i += 1
        op = ""
        for o in _OPS:
            if t.startswith(o):
                op = o
                break
        if op:
            t = t[len(op):]
            if not t:
                if i >= len(toks):
                    raise ValueError("invalid range: %r" % (text,))
                t = toks[i]
                i += 1
            c, p = _primitive(op, t)
        elif t[:1] == "~":
            c, p = _tilde(t[1:])
        elif t[:1] == "^":
            c, p = _caret(t[1:])
        else:
            c, p = _primitive("", t)
        cmps.extend(c)
        pres.extend(p)
    return cmps, pres


def _compile(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


def _check(key, op, bound):
    if op == "nothing":
        return False
    if op == "<":
        return key < bound
    if op == "<=":
        return key <= bound
    if op == ">":
        return key > bound
    if op == ">=":
        return key >= bound
    return key == bound


def _match(key, sets):
    for cmps, pres in sets:
        if not all(_check(key, op, b) for op, b in cmps):
            continue
        if key[3] != (1,) and key[:3] not in pres:
            continue
        return True
    return False


def satisfies(version, range_):
    key = _parse_version(version)
    return _match(key, _compile(range_))


def max_satisfying(versions, range_):
    sets = _compile(range_)
    best, best_key = None, None
    for v in versions:
        try:
            key = _parse_version(v)
        except ValueError:
            continue
        if _match(key, sets) and (best_key is None or key > best_key):
            best, best_key = v, key
    return best
