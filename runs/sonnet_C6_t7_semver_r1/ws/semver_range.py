"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    r"(?P<M>%s)\.(?P<m>%s)\.(?P<p>%s)"
    r"(?:-(?P<pre>%s(?:\.%s)*))?(?:\+(?P<build>%s(?:\.%s)*))?"
    % (_NUM, _NUM, _NUM, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_WILD = r"[xX*]"
_PART = r"(?:%s|%s)" % (_NUM, _WILD)
_PARTIAL_RE = re.compile(
    r"v?(?P<M>%s)(?:\.(?P<m>%s)(?:\.(?P<p>%s)"
    r"(?:-(?P<pre>%s(?:\.%s)*))?(?:\+(?P<build>%s(?:\.%s)*))?)?)?"
    % (_PART, _PART, _PART, _PRE_ID, _PRE_ID, _BUILD_ID, _BUILD_ID)
)
_COMP_RE = re.compile(r"(?P<op><=|>=|<|>|=|~|\^)?(?P<v>.+)", re.S)
_OPS = {"<", "<=", ">", ">=", "="}
_WS = " \t\n\r\f\v"


def _pre_key(pre):
    return tuple((0, int(i)) if i.isdigit() else (1, i) for i in pre.split("."))


def _key(M, m, p, pre):
    if pre is None:
        return (M, m, p, 1, ())
    return (M, m, p, 0, _pre_key(pre))


def _parse_version(s):
    if not isinstance(s, str):
        raise ValueError("invalid version")
    s = s.strip(_WS)
    if s[:1] in ("v", "="):
        s = s[1:]
    mt = _VERSION_RE.fullmatch(s)
    if not mt:
        raise ValueError("invalid version: %r" % (s,))
    return (int(mt["M"]), int(mt["m"]), int(mt["p"]), mt["pre"])


def _parse_partial(s):
    """Return (parts, pre) where parts is the list of leading numeric parts."""
    mt = _PARTIAL_RE.fullmatch(s)
    if not mt:
        raise ValueError("invalid version: %r" % (s,))
    parts = []
    wild = False
    for name in ("M", "m", "p"):
        g = mt[name]
        if g is None:
            wild = True
        elif re.fullmatch(_WILD, g):
            wild = True
        elif wild:
            raise ValueError("invalid version: %r" % (s,))
        else:
            parts.append(int(g))
    if len(parts) != 3 and (mt["pre"] is not None or mt["build"] is not None):
        raise ValueError("invalid version: %r" % (s,))
    return parts, mt["pre"]


def _zero(M, m, p):
    return _key(M, m, p, "0")


def _next(parts):
    """Exclusive upper bound key (with -0) for a partial of 1 or 2 parts."""
    if len(parts) == 1:
        return _zero(parts[0] + 1, 0, 0)
    return _zero(parts[0], parts[1] + 1, 0)


def _fill(parts):
    return tuple(parts) + (0,) * (3 - len(parts))


_FALSE = ("false", None)


class _Set:
    def __init__(self):
        self.comps = []
        self.pre_tuples = set()

    def add(self, op, key):
        self.comps.append((op, key))

    def note(self, parts, pre):
        if pre is not None and len(parts) == 3:
            self.pre_tuples.add(tuple(parts))

    def matches(self, v):
        M, m, p, pre = v
        k = _key(M, m, p, pre)
        for op, ck in self.comps:
            if op == "false":
                return False
            if op == "<" and not k < ck:
                return False
            if op == "<=" and not k <= ck:
                return False
            if op == ">" and not k > ck:
                return False
            if op == ">=" and not k >= ck:
                return False
            if op == "=" and not k == ck:
                return False
        if pre is not None and (M, m, p) not in self.pre_tuples:
            return False
        return True


def _add_comparator(st, op, tok):
    parts, pre = _parse_partial(tok)
    n = len(parts)
    st.note(parts, pre)
    if op in ("~", "^"):
        if n == 0:
            st.add(">=", _key(0, 0, 0, None))
            return
        lo = _fill(parts)
        st.add(">=", _key(*lo, pre))
        if op == "~":
            hi = _zero(parts[0] + 1, 0, 0) if n == 1 else _zero(parts[0], parts[1] + 1, 0)
        else:
            idx = None
            for i, x in enumerate(parts):
                if x != 0:
                    idx = i
                    break
            if idx is None:
                idx = n - 1
            bumped = list(lo)
            bumped[idx] += 1
            for j in range(idx + 1, 3):
                bumped[j] = 0
            hi = _zero(*bumped)
        st.add("<", hi)
        return
    if n == 3:
        st.add(op, _key(*parts, pre))
        return
    if n == 0:
        if op in (">", "<"):
            st.comps.append(_FALSE)
        else:
            st.add(">=", _key(0, 0, 0, None))
        return
    lo = _key(*_fill(parts), None)
    if op == "=":
        st.add(">=", lo)
        st.add("<", _next(parts))
    elif op == ">":
        st.add(">=", _next(parts))
    elif op == ">=":
        st.add(">=", lo)
    elif op == "<":
        st.add("<", _zero(*_fill(parts)))
    elif op == "<=":
        st.add("<", _next(parts))


def _plain_partial(tok):
    return bool(_PARTIAL_RE.fullmatch(tok))


def _parse_set(text):
    st = _Set()
    raw = text.split()
    toks = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t in _OPS:
            if i + 1 >= len(raw):
                raise ValueError("dangling operator")
            t = t + raw[i + 1]
            i += 1
        toks.append(t)
        i += 1
    i = 0
    while i < len(toks):
        t = toks[i]
        if i + 1 < len(toks) and toks[i + 1] == "-":
            if i + 2 >= len(toks):
                raise ValueError("dangling hyphen")
            left, right = t, toks[i + 2]
            if not (_plain_partial(left) and _plain_partial(right)):
                raise ValueError("invalid hyphen range")
            _add_comparator(st, ">=", left)
            _add_comparator(st, "<=", right)
            i += 3
            continue
        if t == "-":
            raise ValueError("invalid hyphen")
        mt = _COMP_RE.fullmatch(t)
        if not mt:
            raise ValueError("invalid comparator")
        _add_comparator(st, mt["op"] or "=", mt["v"])
        i += 1
    return st


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range")
    return [_parse_set(part) for part in range_.split("||")]


def satisfies(version, range_):
    v = _parse_version(version)
    sets = _parse_range(range_)
    return any(s.matches(v) for s in sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for s in versions:
        try:
            v = _parse_version(s)
        except ValueError:
            continue
        if not any(st.matches(v) for st in sets):
            continue
        k = _key(*v)
        if best_key is None or k > best_key:
            best, best_key = s, k
    return best
