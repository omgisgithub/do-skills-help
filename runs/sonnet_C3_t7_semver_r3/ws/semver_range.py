"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_IDENT = r"[0-9A-Za-z-]+"
_CORE_RE = re.compile(r"(%s)\.(%s)\.(%s)" % (_NUM, _NUM, _NUM))
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")
_WILD = ("*", "x", "X")


def _parse_pre(text):
    ids = text.split(".")
    out = []
    for i in ids:
        if not re.fullmatch(_IDENT, i, re.ASCII):
            raise ValueError("invalid prerelease")
        if i.isdigit():
            if len(i) > 1 and i[0] == "0":
                raise ValueError("leading zero in prerelease")
            out.append((0, int(i), ""))
        else:
            out.append((1, 0, i))
    return tuple(out)


def _parse_full(text):
    """Parse a full version (no v/= prefix) -> (major, minor, patch, pre)."""
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    rest = text
    if "+" in rest:
        rest, build = rest.split("+", 1)
        for i in build.split("."):
            if not re.fullmatch(_IDENT, i, re.ASCII):
                raise ValueError("invalid build")
    pre = None
    if "-" in rest:
        rest, pre_text = rest.split("-", 1)
        pre = _parse_pre(pre_text)
    m = _CORE_RE.fullmatch(rest)
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _key(v):
    major, minor, patch, pre = v
    if pre is None:
        return (major, minor, patch, 1, ())
    return (major, minor, patch, 0, pre)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    t = text.strip()
    if t[:1] in ("v", "="):
        t = t[1:]
    return _parse_full(t)


_ZERO_PRE = ((0, 0, ""),)  # the "-0" of desugared upper bounds


def _parse_partial(text):
    """-> (major, minor, patch, pre); wildcards/missing parts are None."""
    if text[:1] == "v":
        text = text[1:]
    if not text:
        raise ValueError("empty version")
    if "-" in text or "+" in text:
        return _parse_full(text)
    parts = text.split(".")
    if len(parts) > 3:
        raise ValueError("invalid version")
    if len(parts) == 3 and not any(p in _WILD for p in parts):
        return _parse_full(text)
    nums = []
    wild = False
    for p in parts:
        if p in _WILD:
            wild = True
            nums.append(None)
        elif wild or not re.fullmatch(_NUM, p, re.ASCII):
            raise ValueError("invalid partial version: %r" % (text,))
        else:
            nums.append(int(p))
    nums += [None] * (3 - len(nums))
    return (nums[0], nums[1], nums[2], None)


# A comparator is (op, version_tuple_or_None, counts_for_prerelease).
# op None means "matches nothing".
def _cmp(op, v, counts=False):
    return (op, v, counts)


def _lower(v, counts=False):
    return _cmp(">=", v, counts)


def _upper(v):
    return _cmp("<", v + (_ZERO_PRE,), False) if len(v) == 3 else _cmp("<", v, False)


def _lt0(major, minor, patch):
    return _cmp("<", (major, minor, patch, _ZERO_PRE), False)


def _zero_filled(p):
    return (p[0] or 0, p[1] or 0, p[2] or 0, p[3])


def _is_full(p):
    return p[0] is not None and p[1] is not None and p[2] is not None


def _upper_of_partial(p):
    """Exclusive upper bound covering all of partial p, or None if unbounded."""
    if p[0] is None:
        return None
    if p[1] is None:
        return _lt0(p[0] + 1, 0, 0)
    return _lt0(p[0], p[1] + 1, 0)


def _desugar(op, text):
    p = _parse_partial(text)
    written_pre = p[3] is not None
    if op in ("", "="):
        if _is_full(p):
            return [_cmp("=", p, written_pre)]
        if p[0] is None:
            return [_lower((0, 0, 0, None))]
        return [_lower(_zero_filled(p)), _upper_of_partial(p)]
    if op == ">":
        if _is_full(p):
            return [_cmp(">", p, written_pre)]
        if p[0] is None:
            return [_cmp(None, None)]
        if p[1] is None:
            return [_lower((p[0] + 1, 0, 0, None))]
        return [_lower((p[0], p[1] + 1, 0, None))]
    if op == ">=":
        return [_lower(_zero_filled(p), written_pre)]
    if op == "<":
        if _is_full(p):
            return [_cmp("<", p, written_pre)]
        if p[0] is None:
            return [_cmp(None, None)]
        return [_lt0(p[0], p[1] or 0, 0)]
    if op == "<=":
        if _is_full(p):
            return [_cmp("<=", p, written_pre)]
        up = _upper_of_partial(p)
        return [up] if up else [_lower((0, 0, 0, None))]
    if op == "~":
        if p[0] is None:
            return [_lower((0, 0, 0, None))]
        return [_lower(_zero_filled(p), written_pre), _upper_of_partial(p)]
    if op == "^":
        if p[0] is None:
            return [_lower((0, 0, 0, None))]
        lo = _lower(_zero_filled(p), written_pre)
        major, minor, patch = p[0], p[1], p[2]
        if major > 0:
            hi = _lt0(major + 1, 0, 0)
        elif minor is None:
            hi = _lt0(1, 0, 0)
        elif patch is None or minor > 0:
            hi = _lt0(0, minor + 1, 0)
        else:
            hi = _lt0(0, 0, patch + 1)
        return [lo, hi]
    raise ValueError("bad operator")


def _split_op(tok):
    for op in _OPS:
        if tok.startswith(op):
            return op, tok[len(op):]
    return "", tok


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
            left, right = t, tokens[i + 2]
            for side in (left, right):
                if _split_op(side)[0]:
                    raise ValueError("operator in hyphen range")
            lp, rp = _parse_partial(left), _parse_partial(right)
            comps.append(_lower(_zero_filled(lp), lp[3] is not None))
            if _is_full(rp):
                comps.append(_cmp("<=", rp, rp[3] is not None))
            else:
                up = _upper_of_partial(rp)
                if up:
                    comps.append(up)
            i += 3
            continue
        if t == "-":
            raise ValueError("unexpected hyphen")
        op, rest = _split_op(t)
        comps.extend(_desugar(op, rest))
        i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(s) for s in range_.split("||")]


def _match_comp(comp, key):
    op, v, _ = comp
    if op is None:
        return False
    k = _key(v)
    if op == "=":
        return key == k
    if op == ">":
        return key > k
    if op == ">=":
        return key >= k
    if op == "<":
        return key < k
    return key <= k


def _match_set(comps, v):
    key = _key(v)
    if not all(_match_comp(c, key) for c in comps):
        return False
    if v[3] is None:
        return True
    return any(
        c[2] and c[1][:3] == v[:3] and c[1][3] is not None for c in comps
    )


def _match(v, sets):
    return any(_match_set(s, v) for s in sets)


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
        if not _match(v, sets):
            continue
        k = _key(v)
        if best_key is None or k > best_key:
            best, best_key = s, k
    return best
