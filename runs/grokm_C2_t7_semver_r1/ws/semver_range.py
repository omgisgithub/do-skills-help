"""npm-style version range matching. See TASK.md for the exact spec."""
import re

_NUM = r"0|[1-9]\d*"
_VER = re.compile(
    rf"^({_NUM})\.({_NUM})\.({_NUM})"
    rf"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    rf"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_PART = re.compile(
    rf"^([xX*]|{_NUM})(?:\.([xX*]|{_NUM}))?(?:\.([xX*]|{_NUM}))?$"
)
_TOK = re.compile(
    r"(?:v|=)?"
    rf"(?:[xX*]|{_NUM})"
    rf"(?:\.(?:[xX*]|{_NUM})){{0,2}}"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
_OP = re.compile(r"(>=|<=|>|<|=|~|\^)")


def _ids(text, zero_ok_leading=False):
    out = []
    for part in text.split("."):
        if not part or not re.fullmatch(r"[0-9A-Za-z-]+", part):
            raise ValueError("invalid version")
        if part.isdigit():
            if not zero_ok_leading and len(part) > 1 and part[0] == "0":
                raise ValueError("invalid version")
            out.append((0, int(part)))
        else:
            out.append((1, part))
    return tuple(out)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("invalid version")
    s = text.strip()
    if s[:1] in "v=":
        s = s[1:]
    m = _VER.fullmatch(s)
    if not m:
        raise ValueError("invalid version")
    if m.group(5) is not None:
        _ids(m.group(5), zero_ok_leading=True)
    pre = _ids(m.group(4)) if m.group(4) is not None else None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)


def _key(v):
    major, minor, patch, pre = v
    if pre is None:
        return (major, minor, patch, 1)
    return (major, minor, patch, 0, pre)


def _rel(major, minor, patch):
    return (major, minor, patch, None)


def _below(major, minor, patch):
    # -0 sorts under every real prerelease, so `<M.m.p-0` keeps those out.
    return (major, minor, patch, ((0, 0),))


def _endpoint(tok):
    """Return ('exact', version) or ('partial', (major, minor, patch))."""
    s = tok.strip()
    if s[:1] in "v=":
        s = s[1:]
        if not s or s[0] in "v=":
            raise ValueError("invalid range")
    if "-" in s or "+" in s:
        return ("exact", _parse_version(tok))
    m = _PART.fullmatch(s)
    if not m:
        raise ValueError("invalid range")
    parts = []
    wild = False
    for g in m.groups():
        if g is None:
            parts.append(None)
        elif g in "xX*":
            wild = True
            parts.append(None)
        elif wild:
            raise ValueError("invalid range")
        else:
            parts.append(int(g))
    if m.group(3) is not None and all(p is not None for p in parts):
        return ("exact", (parts[0], parts[1], parts[2], None))
    return ("partial", tuple(parts))


def _partial_comps(op, parts):
    major, minor, patch = parts
    if major is None:
        if op in (">", "<"):
            return [("<", _below(0, 0, 0))]
        return [(">=", _rel(0, 0, 0))]
    if op in ("", "="):
        if minor is None:
            return [(">=", _rel(major, 0, 0)), ("<", _below(major + 1, 0, 0))]
        return [(">=", _rel(major, minor, 0)), ("<", _below(major, minor + 1, 0))]
    if op == ">":
        if minor is None:
            return [(">=", _rel(major + 1, 0, 0))]
        return [(">=", _rel(major, minor + 1, 0))]
    if op == ">=":
        if minor is None:
            return [(">=", _rel(major, 0, 0))]
        return [(">=", _rel(major, minor, 0))]
    if op == "<":
        if minor is None:
            return [("<", _below(major, 0, 0))]
        return [("<", _below(major, minor, 0))]
    if op == "<=":
        if minor is None:
            return [("<", _below(major + 1, 0, 0))]
        return [("<", _below(major, minor + 1, 0))]
    raise ValueError("invalid range")


def _tilde(kind, data):
    if kind == "partial":
        major, minor, patch = data
        if major is None:
            raise ValueError("invalid range")
        if minor is None:
            return [(">=", _rel(major, 0, 0)), ("<", _below(major + 1, 0, 0))]
        return [(">=", _rel(major, minor, 0)), ("<", _below(major, minor + 1, 0))]
    major, minor, patch, pre = data
    return [(">=", data), ("<", _below(major, minor + 1, 0))]


def _caret(kind, data):
    if kind == "partial":
        major, minor, patch = data
        if major is None:
            raise ValueError("invalid range")
        if minor is None:
            return [(">=", _rel(major, 0, 0)), ("<", _below(major + 1, 0, 0))]
        if major == 0:
            return [(">=", _rel(0, minor, 0)), ("<", _below(0, minor + 1, 0))]
        return [(">=", _rel(major, minor, 0)), ("<", _below(major + 1, 0, 0))]
    major, minor, patch, pre = data
    if major > 0:
        upper = _below(major + 1, 0, 0)
    elif minor > 0:
        upper = _below(major, minor + 1, 0)
    else:
        upper = _below(0, 0, patch + 1)
    return [(">=", data), ("<", upper)]


def _hyphen(lk, left, rk, right):
    comps = []
    if lk == "partial":
        major, minor, patch = left
        if major is None:
            comps.append((">=", _rel(0, 0, 0)))
        elif minor is None:
            comps.append((">=", _rel(major, 0, 0)))
        else:
            comps.append((">=", _rel(major, minor, 0)))
    else:
        comps.append((">=", left))
    if rk == "partial":
        major, minor, patch = right
        if major is None:
            pass
        elif minor is None:
            comps.append(("<", _below(major + 1, 0, 0)))
        else:
            comps.append(("<", _below(major, minor + 1, 0)))
    else:
        comps.append(("<=", right))
    return comps


def _written_pre(kind, data, into):
    if kind == "exact" and data[3] is not None:
        into.add(data[:3])


def _token_at(s, i):
    m = _TOK.match(s, i)
    if not m:
        raise ValueError("invalid range")
    end = m.end()
    if end < len(s) and not s[end].isspace():
        raise ValueError("invalid range")
    return m.group(0), end


def _parse_set(s):
    s = s.strip()
    if not s:
        return None
    comps = []
    pres = set()
    i, n = 0, len(s)
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        op = ""
        m = _OP.match(s, i)
        if m:
            op = m.group(1)
            i = m.end()
            while i < n and s[i].isspace():
                i += 1
            if i >= n:
                raise ValueError("invalid range")
        tok, i = _token_at(s, i)
        if op == "":
            h = re.match(r"\s+-\s+", s[i:])
            if h:
                tok2, j = _token_at(s, i + h.end())
                lk, left = _endpoint(tok)
                rk, right = _endpoint(tok2)
                _written_pre(lk, left, pres)
                _written_pre(rk, right, pres)
                comps.extend(_hyphen(lk, left, rk, right))
                i = j
                continue
        kind, data = _endpoint(tok)
        if op == "~":
            _written_pre(kind, data, pres)
            comps.extend(_tilde(kind, data))
        elif op == "^":
            _written_pre(kind, data, pres)
            comps.extend(_caret(kind, data))
        elif kind == "partial":
            comps.extend(_partial_comps(op, data))
        else:
            _written_pre(kind, data, pres)
            comps.append(("=" if op in ("", "=") else op, data))
    return (comps, pres)


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range")
    return [_parse_set(part) for part in range_.split("||")]


def _comp_ok(v, op, target):
    kv, kt = _key(v), _key(target)
    if op == "=":
        return kv == kt
    if op == "<":
        return kv < kt
    if op == "<=":
        return kv <= kt
    if op == ">":
        return kv > kt
    if op == ">=":
        return kv >= kt
    raise ValueError("invalid range")


def _set_ok(v, parsed):
    if parsed is None:
        return True
    comps, pres = parsed
    for op, target in comps:
        if not _comp_ok(v, op, target):
            return False
    if v[3] is not None and v[:3] not in pres:
        return False
    return True


def _in_range(v, sets):
    return any(_set_ok(v, s) for s in sets)


def satisfies(version, range_):
    return _in_range(_parse_version(version), _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for raw in versions:
        try:
            v = _parse_version(raw)
        except ValueError:
            continue
        if _in_range(v, sets) and (best_key is None or _key(v) > best_key):
            best, best_key = raw, _key(v)
    return best


if __name__ == "__main__":
    assert satisfies("1.2.4-alpha", "^1.2.3") is False
    assert satisfies("1.2.3-beta.4", "^1.2.3-beta.2") is True
    assert satisfies("1.0.0-rc.1", "*") is False
    assert satisfies("1.2.3", "1.2.3 - 2.3.4") is True
    assert satisfies("2.3.5", "1.2.3 - 2") is True
    assert satisfies("3.0.0", "1.2.3 - 2") is False
    assert satisfies("1.2.9", ">1.2") is False
    assert satisfies("1.3.0", ">1.2") is True
    assert max_satisfying(["1.0.0+b", "1.0.0+a", "0.9.0"], "*") == "1.0.0+b"
    assert max_satisfying(["nope", "1.0.0", "1.10.0", "2.0.0"], "^1") == "1.10.0"
    chain = ["1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-alpha", "1.0.0-rc.1", "1.0.0"]
    assert max_satisfying(chain, ">=1.0.0-0 <1.0.0") == "1.0.0-rc.1"
