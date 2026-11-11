"""npm-style version range matching. See TASK.md for the exact spec."""
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_FULL = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_PART = re.compile(r"(?:%s|[xX*])" % _NUM)
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")


def _pre_key(pre):
    if pre is None:
        return (1,)
    ids = []
    for p in pre.split("."):
        ids.append((0, int(p), "") if p.isdigit() else (1, 0, p))
    return (0, tuple(ids))


def _key(maj, mnr, pat, pre):
    return (maj, mnr, pat, _pre_key(pre))


def _parse_version(s):
    """Parse a full version (no surrounding whitespace). Returns (key, M, m, p, pre)."""
    if s[:1] in ("v", "=") and s[:1]:
        s = s[1:]
    m = _FULL.fullmatch(s)
    if not m:
        raise ValueError("invalid version")
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
    pre = m.group(4)
    return _key(a, b, c, pre), a, b, c, pre


def _parse_partial(s):
    """Return (nparts, M, m, p, pre) where nparts in 0..3."""
    if s[:1] == "v":
        s = s[1:]
    m = _FULL.fullmatch(s)
    if m:
        return 3, int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    parts = s.split(".")
    if not 1 <= len(parts) <= 3 or not all(_PART.fullmatch(p) for p in parts):
        raise ValueError("invalid range")
    nums = []
    wild = False
    for p in parts:
        if p in ("x", "X", "*"):
            wild = True
        else:
            if wild:
                raise ValueError("invalid range")
            nums.append(int(p))
    if len(nums) == 3:
        return 3, nums[0], nums[1], nums[2], None
    n = len(nums)
    nums += [0] * (3 - n)
    return n, nums[0], nums[1], nums[2], None


_NEVER = object()


def _c(op, M, m, p, pre=None):
    return (op, _key(M, m, p, pre))


def _upper(n, M, m):
    """Exclusive upper bound for a partial with n parts (1 or 2)."""
    if n == 1:
        return _c("<", M + 1, 0, 0, "0")
    return _c("<", M, m + 1, 0, "0")


def _desugar_op(op, part):
    n, M, m, p, pre = part
    if op in ("", "="):
        if n == 0:
            return [_c(">=", 0, 0, 0)]
        if n == 3:
            return [_c("=", M, m, p, pre)]
        return [_c(">=", M, m, 0), _upper(n, M, m)]
    if op == ">":
        if n == 0:
            return [_NEVER]
        if n == 3:
            return [_c(">", M, m, p, pre)]
        return [_c(">=", M + 1, 0, 0)] if n == 1 else [_c(">=", M, m + 1, 0)]
    if op == ">=":
        return [_c(">=", M, m, p, pre)]
    if op == "<":
        if n == 0:
            return [_NEVER]
        if n == 3:
            return [_c("<", M, m, p, pre)]
        return [_c("<", M, m, 0, "0")] if n == 2 else [_c("<", M, 0, 0, "0")]
    if op == "<=":
        if n == 0:
            return [_c(">=", 0, 0, 0)]
        if n == 3:
            return [_c("<=", M, m, p, pre)]
        return [_upper(n, M, m)]
    if op == "~":
        if n == 0:
            return [_c(">=", 0, 0, 0)]
        lo = _c(">=", M, m, p, pre)
        return [lo, _upper(1 if n == 1 else 2, M, m)]
    if op == "^":
        if n == 0:
            return [_c(">=", 0, 0, 0)]
        lo = _c(">=", M, m, p, pre)
        if M > 0 or n == 1:
            hi = _c("<", M + 1, 0, 0, "0")
        elif m > 0 or n == 2:
            hi = _c("<", M, m + 1, 0, "0")
        else:
            hi = _c("<", M, m, p + 1, "0")
        return [lo, hi]
    raise ValueError("invalid range")


def _parse_set(text):
    raw = text.split()
    toks = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t in _OPS:
            if i + 1 >= len(raw):
                raise ValueError("invalid range")
            t = t + raw[i + 1]
            i += 1
        toks.append(t)
        i += 1
    comps = []  # list of comparator or _NEVER
    tagged = set()
    i = 0
    while i < len(toks):
        t = toks[i]
        if i + 1 < len(toks) and toks[i + 1] == "-":
            if i + 2 >= len(toks):
                raise ValueError("invalid range")
            lo = _parse_partial(t)
            hi = _parse_partial(toks[i + 2])
            n, M, m, p, pre = lo
            comps.append(_c(">=", M, m, p, pre))
            if n == 3 and pre:
                tagged.add((M, m, p))
            n, M, m, p, pre = hi
            if n == 0:
                pass
            elif n == 3:
                comps.append(_c("<=", M, m, p, pre))
                if pre:
                    tagged.add((M, m, p))
            else:
                comps.append(_upper(n, M, m))
            i += 3
            continue
        if t == "-":
            raise ValueError("invalid range")
        op = ""
        for o in _OPS:
            if t.startswith(o):
                op = o
                break
        part = _parse_partial(t[len(op):])
        if part[0] == 3 and part[4]:
            tagged.add(part[1:4])
        comps.extend(_desugar_op(op, part))
        i += 1
    return comps, tagged


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(s) for s in range_.split("||")]


def _match(comps, key):
    for c in comps:
        if c is _NEVER:
            return False
        op, k = c
        if op == "<" and not key < k:
            return False
        if op == "<=" and not key <= k:
            return False
        if op == ">" and not key > k:
            return False
        if op == ">=" and not key >= k:
            return False
        if op == "=" and not key == k:
            return False
    return True


def _check(parsed, vinfo):
    key, M, m, p, pre = vinfo
    for comps, tagged in parsed:
        if not _match(comps, key):
            continue
        if pre is not None and (M, m, p) not in tagged:
            continue
        return True
    return False


def _parse_input_version(version):
    if not isinstance(version, str):
        raise ValueError("version must be a string")
    return _parse_version(version.strip())


def satisfies(version, range_):
    vinfo = _parse_input_version(version)
    return _check(_parse_range(range_), vinfo)


def max_satisfying(versions, range_):
    parsed = _parse_range(range_)
    best = None
    best_key = None
    for v in versions:
        try:
            vinfo = _parse_input_version(v)
        except ValueError:
            continue
        if _check(parsed, vinfo) and (best is None or vinfo[0] > best_key):
            best, best_key = v, vinfo[0]
    return best
