"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_ID = r"[0-9A-Za-z-]+"
_NUM = r"(?:0|[1-9][0-9]*)"
_VERSION_RE = re.compile(
    r"(%s)\.(%s)\.(%s)(?:-(%s(?:\.%s)*))?(?:\+(%s(?:\.%s)*))?" % (_NUM, _NUM, _NUM, _ID, _ID, _ID, _ID)
)
_WILD = ("*", "x", "X")
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")


def _pre_key(pre):
    ids = []
    for ident in pre.split("."):
        if ident.isdigit() and ident.isascii():
            if len(ident) > 1 and ident[0] == "0":
                raise ValueError("leading zero in prerelease: %r" % pre)
            ids.append((0, int(ident), ""))
        else:
            ids.append((1, 0, ident))
    return tuple(ids)


def _key(major, minor, patch, pre=None):
    if pre is None:
        return (major, minor, patch, 1, ())
    return (major, minor, patch, 0, _pre_key(pre))


def _strip_prefix(text, chars):
    if text and text[0] in chars:
        text = text[1:]
    return text


def _parse_version(version):
    if not isinstance(version, str):
        raise ValueError("version must be a string")
    text = _strip_prefix(version.strip(), "v=")
    m = _VERSION_RE.fullmatch(text)
    if not m:
        raise ValueError("invalid version: %r" % (version,))
    return _key(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))


def _parse_partial(text):
    """Return (parts, pre): parts is a list of 0-3 ints (wildcards dropped)."""
    text = _strip_prefix(text, "v")
    if not text:
        raise ValueError("empty version")
    m = _VERSION_RE.fullmatch(text)
    if m:
        return [int(m.group(i)) for i in (1, 2, 3)], m.group(4)
    if "-" in text or "+" in text:
        raise ValueError("invalid version: %r" % text)
    pieces = text.split(".")
    if len(pieces) > 3:
        raise ValueError("invalid version: %r" % text)
    parts = []
    wild = False
    for p in pieces:
        if p in _WILD:
            wild = True
        elif wild or not re.fullmatch(_NUM, p):
            raise ValueError("invalid version: %r" % text)
        else:
            parts.append(int(p))
    return parts, None


def _zero(parts):
    return (parts + [0, 0, 0])[:3]


def _upper_excl(parts):
    """Exclusive upper bound covering all versions matching a 1- or 2-part partial."""
    if len(parts) == 1:
        return _key(parts[0] + 1, 0, 0, "0")
    return _key(parts[0], parts[1] + 1, 0, "0")


# A comparator is (test, written) where test(key) -> bool and written is a
# (major, minor, patch) tuple if it was written with a prerelease tag, else None.
def _cmp(op, bound):
    if op == ">=":
        return lambda k: k >= bound
    if op == ">":
        return lambda k: k > bound
    if op == "<=":
        return lambda k: k <= bound
    if op == "<":
        return lambda k: k < bound
    return lambda k: k == bound


_NOTHING = lambda k: False  # noqa: E731


def _bound(op, parts, pre):
    """Desugar a comparator into a list of simple tests."""
    n = len(parts)
    full = _key(*_zero(parts), pre=pre) if n == 3 else None
    if n == 0:
        if op in (">", "<"):
            return [_NOTHING]
        return [_cmp(">=", _key(0, 0, 0))]
    if op in ("", "="):
        if n == 3:
            return [_cmp("=", full)]
        return [_cmp(">=", _key(*_zero(parts))), _cmp("<", _upper_excl(parts))]
    if op == ">":
        if n == 3:
            return [_cmp(">", full)]
        return [_cmp(">=", _upper_excl(parts))]
    if op == ">=":
        return [_cmp(">=", full if n == 3 else _key(*_zero(parts)))]
    if op == "<":
        return [_cmp("<", full if n == 3 else _key(*_zero(parts), pre="0"))]
    if op == "<=":
        if n == 3:
            return [_cmp("<=", full)]
        return [_cmp("<", _upper_excl(parts))]
    lower = _cmp(">=", full if n == 3 else _key(*_zero(parts)))
    if op == "~":
        upper = _upper_excl(parts[:2])
    else:  # caret
        p = _zero(parts)
        if p[0] > 0 or n == 1:
            upper = _key(p[0] + 1, 0, 0, "0") if p[0] > 0 else _key(1, 0, 0, "0")
        elif p[1] > 0 or n == 2:
            upper = _key(0, p[1] + 1, 0, "0") if p[1] > 0 else _key(0, 1, 0, "0")
        else:
            upper = _key(0, 0, p[2] + 1, "0")
    return [lower, _cmp("<", upper)]


def _written(parts, pre):
    return tuple(parts) if pre is not None and len(parts) == 3 else None


def _parse_set(text):
    raw = text.split()
    tokens = []
    i = 0
    while i < len(raw):
        tok = raw[i]
        if tok in _OPS:
            if i + 1 >= len(raw):
                raise ValueError("dangling operator in range")
            tok += raw[i + 1]
            i += 1
        tokens.append(tok)
        i += 1

    tests = []
    written = []

    def add(tlist, parts, pre):
        tests.extend(tlist)
        w = _written(parts, pre)
        if w is not None:
            written.append(w)

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError("incomplete hyphen range")
            right = tokens[i + 2]
            for t in (tok, right):
                if t[0] in "<>=~^" or t == "-":
                    raise ValueError("invalid hyphen range")
            lp, lpre = _parse_partial(tok)
            rp, rpre = _parse_partial(right)
            add(_bound(">=", lp, lpre), lp, lpre)
            add(_bound("<=", rp, rpre), rp, rpre)
            i += 3
            continue
        if tok == "-":
            raise ValueError("invalid hyphen range")
        op = ""
        for candidate in _OPS:
            if tok.startswith(candidate):
                op = candidate
                break
        parts, pre = _parse_partial(tok[len(op):])
        add(_bound(op, parts, pre), parts, pre)
        i += 1
    return tests, written


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(s) for s in range_.split("||")]


def _match(key, parsed):
    for tests, written in parsed:
        if not all(t(key) for t in tests):
            continue
        if key[3] == 0 and key[:3] not in written:
            continue
        return True
    return False


def satisfies(version, range_):
    key = _parse_version(version)
    return _match(key, _parse_range(range_))


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
