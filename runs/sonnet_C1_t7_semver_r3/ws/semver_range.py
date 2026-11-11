"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_NUM_RE = re.compile(_NUM)
_WILD = ("x", "X", "*")
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")


def _pre_key(pre):
    if not pre:
        return ()
    return tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split("."))


def _key(major, minor, patch, pre=""):
    # A version without prerelease sorts above any with one.
    return (major, minor, patch, 0 if pre else 1, _pre_key(pre))


def _parse_version(text):
    """Strict full version (leading v/= and whitespace allowed) -> (maj, min, pat, pre)."""
    if not isinstance(text, str):
        raise ValueError("invalid version")
    text = text.strip()
    if text[:1] in ("v", "="):
        text = text[1:]
    m = _VERSION_RE.fullmatch(text)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or ""


def _parse_partial(text):
    """-> (major, minor, patch, pre); missing/wildcard parts are None."""
    if text[:1] == "v":
        text = text[1:]
    if not text:
        raise ValueError("empty version")
    parts = text.split(".")
    if _VERSION_RE.fullmatch(text):
        return _parse_version(text)
    if len(parts) > 3:
        raise ValueError("invalid version: %r" % (text,))
    vals = []
    wild = False
    for p in parts:
        if p in _WILD:
            wild = True
            vals.append(None)
        elif wild or not _NUM_RE.fullmatch(p):
            raise ValueError("invalid version: %r" % (text,))
        else:
            vals.append(int(p))
    vals += [None] * (3 - len(vals))
    return vals[0], vals[1], vals[2], ""


# A comparator is (op, key, counts_for_prerelease, tuple3); op in <,<=,>,>=,=,none
def _cmp(op, v, pre="", written=False):
    return (op, _key(v[0], v[1], v[2], pre), written and bool(pre), (v[0], v[1], v[2]))


def _lo(p):
    return (p[0] or 0, p[1] or 0, p[2] or 0)


def _upper(p):
    """Exclusive upper bound (as version tuple) for a partial with at least major set."""
    if p[1] is None:
        return (p[0] + 1, 0, 0)
    if p[2] is None:
        return (p[0], p[1] + 1, 0)
    return (p[0], p[1], p[2] + 1)


def _lt0(v):
    return _cmp("<", v, "0")


def _any():
    return _cmp(">=", (0, 0, 0))


def _desugar(op, p):
    maj, mi, pa, pre = p
    if maj is None:
        if op in (">", "<"):
            return [("none", None, False, None)]
        return [_any()]
    full = pa is not None
    if op in ("", "="):
        if full:
            return [_cmp("=", p, pre, True)]
        return [_cmp(">=", _lo(p)), _lt0(_upper(p))]
    if full:
        return [_cmp(op, p, pre, True)]
    if op == ">":
        return [_cmp(">=", _upper(p))]
    if op == ">=":
        return [_cmp(">=", _lo(p))]
    if op == "<":
        return [_lt0(_lo(p))]
    if op == "<=":
        return [_lt0(_upper(p))]
    raise ValueError("bad operator")


def _tilde(p):
    maj, mi, pa, pre = p
    if maj is None:
        return [_any()]
    hi = (maj + 1, 0, 0) if mi is None else (maj, mi + 1, 0)
    return [_cmp(">=", _lo(p), pre, True), _lt0(hi)]


def _caret(p):
    maj, mi, pa, pre = p
    if maj is None:
        return [_any()]
    if maj > 0 or mi is None:
        hi = (maj + 1, 0, 0)
    elif mi > 0 or pa is None:
        hi = (0, mi + 1, 0)
    else:
        hi = (0, 0, pa + 1)
    return [_cmp(">=", _lo(p), pre, True), _lt0(hi)]


def _hyphen(left, right):
    comps = []
    if left[0] is None:
        comps.append(_any())
    else:
        comps.append(_cmp(">=", _lo(left), left[3], True))
    if right[0] is None:
        pass
    elif right[2] is None:
        comps.append(_lt0(_upper(right)))
    else:
        comps.append(_cmp("<=", right, right[3], True))
    return comps


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
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError("dangling hyphen")
            right = tokens[i + 2]
            if t.startswith(_OPS) or right.startswith(_OPS) or right == "-":
                raise ValueError("invalid hyphen range")
            comps += _hyphen(_parse_partial(t), _parse_partial(right))
            i += 3
            continue
        if t == "-":
            raise ValueError("invalid hyphen")
        op = ""
        for o in _OPS:
            if t.startswith(o):
                op = o
                break
        p = _parse_partial(t[len(op):])
        if op == "~":
            comps += _tilde(p)
        elif op == "^":
            comps += _caret(p)
        else:
            comps += _desugar(op, p)
        i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(s) for s in range_.split("||")]


def _test(comp, k):
    op, ck = comp[0], comp[1]
    if op == "none":
        return False
    if op == "=":
        return k == ck
    if op == "<":
        return k < ck
    if op == "<=":
        return k <= ck
    if op == ">":
        return k > ck
    return k >= ck


def _match(parsed, v):
    k = _key(*v)
    t3 = v[:3]
    for comps in parsed:
        if not all(_test(c, k) for c in comps):
            continue
        if v[3] and not any(c[2] and c[3] == t3 for c in comps):
            continue
        return True
    return False


def satisfies(version, range_):
    v = _parse_version(version)
    return _match(_parse_range(range_), v)


def max_satisfying(versions, range_):
    parsed = _parse_range(range_)
    best, best_key = None, None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if not _match(parsed, v):
            continue
        k = _key(*v)
        if best_key is None or k > best_key:
            best, best_key = s, k
    return best
