"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"0|[1-9][0-9]*"
_PRE_ID = r"[0-9A-Za-z-]+"
_PART = r"(?:%s|[xX*])" % _NUM

_FULL_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _PRE_ID, _PRE_ID),
    re.ASCII,
)
_PARTIAL_RE = re.compile(
    r"(%s)(?:\.(%s)(?:\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?)?)?"
    % (_PART, _PART, _PART, _PRE_ID, _PRE_ID, _PRE_ID, _PRE_ID),
    re.ASCII,
)
_OP_ONLY_RE = re.compile(r"(?:<=|>=|<|>|=|~|\^)\Z")
_COMPARATOR_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.*)\Z", re.DOTALL)
_NUM_ID_RE = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_DIGITS_RE = re.compile(r"[0-9]+\Z")


def _pre_key(pre):
    """Sort key for a prerelease string (None = no prerelease)."""
    if pre is None:
        return (1,)
    ids = []
    for ident in pre.split("."):
        if _DIGITS_RE.match(ident):
            ids.append((0, int(ident), ""))
        else:
            ids.append((1, 0, ident))
    return (0, tuple(ids))


def _check_pre(pre):
    if pre is None:
        return
    for ident in pre.split("."):
        if _DIGITS_RE.match(ident) and not _NUM_ID_RE.match(ident):
            raise ValueError("invalid prerelease identifier: %r" % ident)


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
        raise ValueError("invalid version: %r" % text)
    _check_pre(m.group(4))
    return _make(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))


def _parse_partial(text):
    """Return (major, minor, patch, pre); wildcards/missing parts are None."""
    s = text
    if s[:1] == "v":
        s = s[1:]
    m = _PARTIAL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version in range: %r" % text)
    parts = []
    for i in (1, 2, 3):
        g = m.group(i)
        parts.append(None if g is None or g in "xX*" else int(g))
    seen_wild = False
    for i, g in enumerate((m.group(1), m.group(2), m.group(3))):
        wild = g is None or g in "xX*"
        if seen_wild and not wild:
            raise ValueError("invalid version in range: %r" % text)
        seen_wild = seen_wild or wild
    pre = m.group(4)
    _check_pre(pre)
    return parts[0], parts[1], parts[2], pre


# A primitive comparator is (op, version_key, pre_tuple) where pre_tuple is
# (major, minor, patch) if it was written with a prerelease tag, else None.
# op "none" never matches.

_NEVER = ("none", None, None)


def _ge(M, m, p, pre=None, counts=False):
    return (">=", _make(M, m, p, pre), (M, m, p) if counts else None)


def _lt0(M, m, p):
    return ("<", _make(M, m, p, "0"), None)


_ANY = _ge(0, 0, 0)


def _desugar_primitive(op, part):
    M, m, p, pre = part
    if M is None:
        return [_NEVER] if op in ("<", ">") else [_ANY]
    if m is None:
        if op in ("", "="):
            return [_ge(M, 0, 0), _lt0(M + 1, 0, 0)]
        if op == ">":
            return [_ge(M + 1, 0, 0)]
        if op == ">=":
            return [_ge(M, 0, 0)]
        if op == "<":
            return [_lt0(M, 0, 0)]
        return [_lt0(M + 1, 0, 0)]  # <=
    if p is None:
        if op in ("", "="):
            return [_ge(M, m, 0), _lt0(M, m + 1, 0)]
        if op == ">":
            return [_ge(M, m + 1, 0)]
        if op == ">=":
            return [_ge(M, m, 0)]
        if op == "<":
            return [_lt0(M, m, 0)]
        return [_lt0(M, m + 1, 0)]  # <=
    tag = (M, m, p) if pre is not None else None
    key = _make(M, m, p, pre)
    return [("=" if op == "" else op, key, tag)]


def _desugar_tilde(part):
    M, m, p, pre = part
    if M is None:
        return [_ANY]
    if m is None:
        return [_ge(M, 0, 0), _lt0(M + 1, 0, 0)]
    if p is None:
        return [_ge(M, m, 0), _lt0(M, m + 1, 0)]
    return [_ge(M, m, p, pre, pre is not None), _lt0(M, m + 1, 0)]


def _desugar_caret(part):
    M, m, p, pre = part
    if M is None:
        return [_ANY]
    if m is None:
        return [_ge(M, 0, 0), _lt0(M + 1, 0, 0)]
    if p is None:
        lo = _ge(M, m, 0)
        hi = _lt0(M + 1, 0, 0) if M > 0 else _lt0(0, m + 1, 0)
        return [lo, hi]
    lo = _ge(M, m, p, pre, pre is not None)
    if M > 0:
        hi = _lt0(M + 1, 0, 0)
    elif m > 0:
        hi = _lt0(0, m + 1, 0)
    else:
        hi = _lt0(0, 0, p + 1)
    return [lo, hi]


def _desugar_hyphen(left, right):
    M, m, p, pre = left
    if M is None:
        out = [_ANY]
    else:
        m0 = m or 0
        p0 = p or 0
        out = [_ge(M, m0, p0, pre, pre is not None) if p is not None else _ge(M, m0, p0)]
    M, m, p, pre = right
    if M is None:
        pass
    elif m is None:
        out.append(_lt0(M + 1, 0, 0))
    elif p is None:
        out.append(_lt0(M, m + 1, 0))
    else:
        out.append(("<=", _make(M, m, p, pre), (M, m, p) if pre is not None else None))
    return out


def _parse_set(text):
    tokens = text.split()
    items = []  # strings; "-" marks hyphen
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if _OP_ONLY_RE.match(tok):
            if i + 1 >= len(tokens):
                raise ValueError("dangling operator in range")
            tok += tokens[i + 1]
            i += 1
        items.append(tok)
        i += 1

    prims = []
    i = 0
    while i < len(items):
        tok = items[i]
        if tok == "-":
            raise ValueError("misplaced hyphen in range")
        if i + 1 < len(items) and items[i + 1] == "-":
            if i + 2 >= len(items) or items[i + 2] == "-":
                raise ValueError("incomplete hyphen range")
            left = _parse_partial(tok)
            right = _parse_partial(items[i + 2])
            prims.extend(_desugar_hyphen(left, right))
            i += 3
            continue
        op, rest = _COMPARATOR_RE.match(tok).groups()
        part = _parse_partial(rest)
        if op == "~":
            prims.extend(_desugar_tilde(part))
        elif op == "^":
            prims.extend(_desugar_caret(part))
        else:
            prims.extend(_desugar_primitive(op or "", part))
        i += 1
    return prims


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(part) for part in range_.split("||")]


def _match_prim(prim, key):
    op, bound, _ = prim
    if op == "none":
        return False
    if op == ">=":
        return key >= bound
    if op == "<=":
        return key <= bound
    if op == ">":
        return key > bound
    if op == "<":
        return key < bound
    return key == bound


def _match_set(prims, key):
    if not all(_match_prim(p, key) for p in prims):
        return False
    if key[3] != (1,):  # has prerelease
        triple = key[:3]
        return any(p[2] == triple for p in prims)
    return True


def _matches(sets, key):
    return any(_match_set(s, key) for s in sets)


def satisfies(version, range_):
    key = _parse_version(version)
    sets = _parse_range(range_)
    return _matches(sets, key)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for v in versions:
        try:
            key = _parse_version(v)
        except ValueError:
            continue
        if not _matches(sets, key):
            continue
        if best_key is None or key > best_key:
            best, best_key = v, key
    return best
