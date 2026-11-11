"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_PRE = _PRE_ID + r"(?:\." + _PRE_ID + r")*"
_BUILD = _BUILD_ID + r"(?:\." + _BUILD_ID + r")*"

_VERSION_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s))?(?:\+(%s))?" % (_NUM, _NUM, _NUM, _PRE, _BUILD)
)
_WILD = r"(?:[xX*]|%s)" % _NUM
_PARTIAL_RE = re.compile(
    r"(%s)(?:\.(%s))?(?:\.(%s))?(?:-(%s))?(?:\+(%s))?" % (_WILD, _WILD, _WILD, _PRE, _BUILD)
)
_OP_SPACE_RE = re.compile(r"(<=|>=|<|>|=|~|\^)\s+")
_OP_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.*)", re.S)

_RELEASE = (1,)  # sorts above any prerelease key (which starts with 0)
_ZERO_PRE = (0, (0, 0))  # the "-0" lower-than-everything prerelease


def _pre_key(pre):
    ids = []
    for ident in pre.split("."):
        ids.append((0, int(ident)) if ident.isdigit() else (1, ident))
    return (0,) + tuple(ids)


def _parse_version(s):
    if not isinstance(s, str):
        raise ValueError("invalid version: %r" % (s,))
    t = s.strip()
    if t[:1] in ("v", "="):
        t = t[1:]
    m = _VERSION_RE.fullmatch(t)
    if not m:
        raise ValueError("invalid version: %r" % (s,))
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    pre = _pre_key(m.group(4)) if m.group(4) else _RELEASE
    return (major, minor, patch, pre)


def _is_wild(x):
    return x is None or x in ("x", "X", "*")


def _parse_partial(tok):
    """Returns (major, minor, patch, pre_key_or_None); None parts are wildcards."""
    if tok[:1] == "v":
        tok = tok[1:]
    m = _PARTIAL_RE.fullmatch(tok)
    if not m:
        raise ValueError("invalid version: %r" % (tok,))
    parts = [m.group(1), m.group(2), m.group(3)]
    seen_wild = False
    vals = []
    for p in parts:
        if _is_wild(p):
            seen_wild = True
            vals.append(None)
        else:
            if seen_wild:
                raise ValueError("invalid version: %r" % (tok,))
            vals.append(int(p))
    pre = None
    if m.group(4) is not None or m.group(5) is not None:
        if vals[2] is None:
            raise ValueError("invalid version: %r" % (tok,))
        if m.group(4) is not None:
            pre = _pre_key(m.group(4))
    return vals[0], vals[1], vals[2], pre


# A comparator is (op, key, tagged). key is (M, m, p, prekey); tagged is True when
# written with a prerelease version. op "never" matches nothing.
def _cmp(op, M, m, p, pre=_RELEASE, tagged=False):
    return (op, (M, m, p, pre), tagged)


def _upper(M, m, p):
    return _cmp("<", M, m, p, _ZERO_PRE)


def _lower_fill(v):
    M, m, p, pre = v
    if M is None:
        return _cmp(">=", 0, 0, 0)
    tagged = pre is not None
    return _cmp(">=", M, m or 0, p or 0, pre if tagged else _RELEASE, tagged)


def _upper_for_partial(v):
    """Exclusive upper bound comparators covering everything matched by partial v."""
    M, m, p, pre = v
    if M is None:
        return []
    if m is None:
        return [_upper(M + 1, 0, 0)]
    if p is None:
        return [_upper(M, m + 1, 0)]
    return []


def _desugar_op(op, v):
    M, m, p, pre = v
    full = p is not None
    tagged = pre is not None
    if full:
        return [(op, (M, m, p, pre if tagged else _RELEASE), tagged)]
    if op in ("", "="):
        return [_lower_fill(v)] + _upper_for_partial(v)
    if op == ">":
        if M is None:
            return [("never", None, False)]
        if m is None:
            return [_cmp(">=", M + 1, 0, 0)]
        return [_cmp(">=", M, m + 1, 0)]
    if op == ">=":
        return [_lower_fill(v)]
    if op == "<":
        if M is None:
            return [("never", None, False)]
        return [_upper(M, m or 0, 0)]
    if op == "<=":
        if M is None:
            return [_cmp(">=", 0, 0, 0)]
        return _upper_for_partial(v)
    raise ValueError("invalid comparator")


def _desugar_tilde(v):
    M, m, p, pre = v
    if M is None:
        return [_cmp(">=", 0, 0, 0)]
    lo = _lower_fill(v)
    if m is None:
        return [lo, _upper(M + 1, 0, 0)]
    return [lo, _upper(M, m + 1, 0)]


def _desugar_caret(v):
    M, m, p, pre = v
    if M is None:
        return [_cmp(">=", 0, 0, 0)]
    lo = _lower_fill(v)
    if M > 0:
        hi = _upper(M + 1, 0, 0)
    elif m is None:
        hi = _upper(1, 0, 0)
    elif m > 0:
        hi = _upper(0, m + 1, 0)
    elif p is None:
        hi = _upper(0, 1, 0)
    else:
        hi = _upper(0, 0, p + 1)
    return [lo, hi]


def _parse_set(text):
    text = _OP_SPACE_RE.sub(r"\1", text)
    tokens = text.split()
    comps = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError("invalid range")
            left = _parse_partial(tokens[i])
            right = _parse_partial(tokens[i + 2])
            comps.append(_lower_fill(left))
            if right[2] is not None:
                comps.append(_desugar_op("<=", right)[0])
            else:
                comps.extend(_upper_for_partial(right))
            i += 3
            continue
        tok = tokens[i]
        i += 1
        if tok == "-":
            raise ValueError("invalid range")
        m = _OP_RE.fullmatch(tok)
        op, rest = m.group(1) or "", m.group(2)
        v = _parse_partial(rest)
        if op == "~":
            comps.extend(_desugar_tilde(v))
        elif op == "^":
            comps.extend(_desugar_caret(v))
        else:
            comps.extend(_desugar_op(op, v))
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range: %r" % (range_,))
    return [_parse_set(part) for part in range_.split("||")]


def _match(comp, v):
    op, key, _ = comp
    if op == "never":
        return False
    if op == "<":
        return v < key
    if op == "<=":
        return v <= key
    if op == ">":
        return v > key
    if op == ">=":
        return v >= key
    return v == key


def _set_matches(comps, v):
    if not all(_match(c, v) for c in comps):
        return False
    if v[3] is _RELEASE or v[3] == _RELEASE:
        return True
    return any(c[2] and c[1][:3] == v[:3] for c in comps)


def _satisfies_parsed(v, sets):
    return any(_set_matches(s, v) for s in sets)


def satisfies(version, range_):
    v = _parse_version(version)
    return _satisfies_parsed(v, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best, best_v = None, None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if _satisfies_parsed(v, sets) and (best_v is None or v > best_v):
            best, best_v = s, v
    return best
