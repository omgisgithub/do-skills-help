"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_IDENT = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(" + _IDENT + r"(?:\." + _IDENT + r")*))?"
    r"(?:\+(" + _IDENT + r"(?:\." + _IDENT + r")*))?"
)
_NUM_RE = re.compile(r"0|[1-9][0-9]*")
_OP_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.*)", re.S)
_WILD = ("*", "x", "X")


def _pre_key(pre):
    if not pre:
        return (1,)
    ids = []
    for ident in pre.split("."):
        if ident.isascii() and ident.isdigit():
            if len(ident) > 1 and ident[0] == "0":
                raise ValueError("leading zero in prerelease: %r" % pre)
            ids.append((0, int(ident), ""))
        else:
            ids.append((1, 0, ident))
    return (0, tuple(ids))


def _make(major, minor, patch, pre=None):
    return (major, minor, patch, _pre_key(pre))


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = _FULL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    return _make(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))


def _parse_partial(text):
    """Return (major, minor, patch, pre_or_None); None parts are wildcards."""
    s = text
    if s[:1] == "v":
        s = s[1:]
    if not s:
        raise ValueError("empty version")
    m = _FULL_RE.fullmatch(s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))
    parts = s.split(".")
    if len(parts) > 3:
        raise ValueError("invalid version: %r" % (text,))
    vals = []
    wild = False
    for part in parts:
        if part in _WILD:
            wild = True
            vals.append(None)
        elif wild or not _NUM_RE.fullmatch(part):
            raise ValueError("invalid version: %r" % (text,))
        else:
            vals.append(int(part))
    vals += [None] * (3 - len(vals))
    return (vals[0], vals[1], vals[2], None)


# A comparator is (op, version_key, counts) where counts says it was written
# with a prerelease version.  op "none" matches nothing.
_NOTHING = ("none", None, False)
_ZERO = _make(0, 0, 0)


def _lo(M, m, p, pre=None, counts=False):
    return (">=", _make(M, m, p, pre), counts)


def _hi(M, m, p):  # exclusive upper bound "<M.m.p-0"
    return ("<", _make(M, m, p, "0"), False)


def _any():
    return [(">=", _ZERO, False)]


def _desugar(op, part):
    M, m, p, pre = part
    counts = pre is not None
    if op in (None, "="):
        if M is None:
            return _any()
        if m is None:
            return [_lo(M, 0, 0), _hi(M + 1, 0, 0)]
        if p is None:
            return [_lo(M, m, 0), _hi(M, m + 1, 0)]
        return [("=", _make(M, m, p, pre), counts)]
    if op == ">":
        if M is None:
            return [_NOTHING]
        if m is None:
            return [_lo(M + 1, 0, 0)]
        if p is None:
            return [_lo(M, m + 1, 0)]
        return [(">", _make(M, m, p, pre), counts)]
    if op == ">=":
        if M is None:
            return _any()
        return [_lo(M, m or 0, p or 0, pre, counts)]
    if op == "<":
        if M is None:
            return [_NOTHING]
        if m is None:
            return [_hi(M, 0, 0)]
        if p is None:
            return [_hi(M, m, 0)]
        return [("<", _make(M, m, p, pre), counts)]
    if op == "<=":
        if M is None:
            return _any()
        if m is None:
            return [_hi(M + 1, 0, 0)]
        if p is None:
            return [_hi(M, m + 1, 0)]
        return [("<=", _make(M, m, p, pre), counts)]
    if op == "~":
        if M is None:
            return _any()
        if m is None:
            return [_lo(M, 0, 0), _hi(M + 1, 0, 0)]
        return [_lo(M, m, p or 0, pre, counts), _hi(M, m + 1, 0)]
    if op == "^":
        if M is None:
            return _any()
        if m is None:
            return [_lo(M, 0, 0), _hi(M + 1, 0, 0)]
        lo = _lo(M, m, p or 0, pre, counts)
        if M > 0:
            return [lo, _hi(M + 1, 0, 0)]
        if p is None or m > 0:
            return [lo, _hi(0, m + 1, 0)]
        return [lo, _hi(0, 0, p + 1)]
    raise ValueError("bad operator")


def _hyphen(left, right):
    out = _desugar(">=", left)
    M, m, p, pre = right
    if M is None:
        return out
    if m is None:
        return out + [_hi(M + 1, 0, 0)]
    if p is None:
        return out + [_hi(M, m + 1, 0)]
    return out + [("<=", _make(M, m, p, pre), pre is not None)]


def _parse_set(text):
    items = []
    toks = text.split()
    i = 0
    while i < len(toks):
        op, rest = _OP_RE.fullmatch(toks[i]).groups()
        if op is not None and rest == "":
            i += 1
            if i >= len(toks):
                raise ValueError("operator without version")
            rest = toks[i]
        items.append((op, rest))
        i += 1
    comps = []
    i = 0
    while i < len(items):
        op, rest = items[i]
        if i + 1 < len(items) and items[i + 1] == (None, "-"):
            if i + 2 >= len(items) or op is not None or items[i + 2][0] is not None:
                raise ValueError("invalid hyphen range")
            comps += _hyphen(_parse_partial(rest), _parse_partial(items[i + 2][1]))
            i += 3
            continue
        comps += _desugar(op, _parse_partial(rest))
        i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(s) for s in range_.split("||")]


def _cmp_ok(op, v, c):
    if op == "=":
        return v == c
    if op == ">":
        return v > c
    if op == ">=":
        return v >= c
    if op == "<":
        return v < c
    return v <= c


def _match(v, sets):
    has_pre = v[3][0] == 0
    for comps in sets:
        ok = True
        for op, c, _ in comps:
            if op == "none" or not _cmp_ok(op, v, c):
                ok = False
                break
        if not ok:
            continue
        if has_pre and not any(
            counts and c[:3] == v[:3] for _, c, counts in comps
        ):
            continue
        return True
    return False


def satisfies(version, range_):
    v = _parse_version(version)
    return _match(v, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if _match(v, sets) and (best_key is None or v > best_key):
            best, best_key = s, v
    return best
