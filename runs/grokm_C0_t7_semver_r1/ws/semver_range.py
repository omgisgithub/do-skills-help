"""npm-style version range matching. See TASK.md for the exact spec."""

import re

# Concrete version: major, minor, patch, prerelease identifiers (None if release).
# Build metadata is parsed and ignored.

_FULL = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_NUM = re.compile(r"0|[1-9][0-9]*")
_WILDCARD = ("*", "x", "X")
# Lowest prerelease of a version. Used only as an exclusive upper bound so the
# next release's prereleases do not match. It is not a written prerelease anchor.
_ZERO = ("0",)


class _Ver:
    __slots__ = ("major", "minor", "patch", "pre")

    def __init__(self, major, minor, patch, pre):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.pre = pre  # None or tuple[str, ...]


class _PV:
    """A version as written in a range. None means omitted or wildcard."""

    __slots__ = ("major", "minor", "patch", "pre")

    def __init__(self, major, minor, patch, pre):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.pre = pre


def _numeric_ident(ident):
    return ident.isdigit()


def _cmp_pre(a, b):
    n = len(a) if len(a) < len(b) else len(b)
    for i in range(n):
        ai, bi = a[i], b[i]
        a_num = _numeric_ident(ai)
        b_num = _numeric_ident(bi)
        if a_num and b_num:
            av, bv = int(ai), int(bi)
            if av != bv:
                return -1 if av < bv else 1
        elif a_num:
            return -1
        elif b_num:
            return 1
        elif ai != bi:
            return -1 if ai < bi else 1
    if len(a) == len(b):
        return 0
    return -1 if len(a) < len(b) else 1


def _cmp(a, b):
    if a.major != b.major:
        return -1 if a.major < b.major else 1
    if a.minor != b.minor:
        return -1 if a.minor < b.minor else 1
    if a.patch != b.patch:
        return -1 if a.patch < b.patch else 1
    if a.pre is None and b.pre is None:
        return 0
    if a.pre is None:
        return 1
    if b.pre is None:
        return -1
    return _cmp_pre(a.pre, b.pre)


def _check_pre(parts):
    for ident in parts:
        if _numeric_ident(ident) and len(ident) > 1 and ident[0] == "0":
            raise ValueError("invalid version")
    return parts


def _full_version(text):
    match = _FULL.fullmatch(text)
    if not match:
        raise ValueError("invalid version")
    pre = None
    if match.group(4) is not None:
        pre = _check_pre(tuple(match.group(4).split(".")))
    return _Ver(int(match.group(1)), int(match.group(2)), int(match.group(3)), pre)


def _parse_version_string(text):
    if not isinstance(text, str):
        raise ValueError("invalid version")
    text = text.strip()
    if not text:
        raise ValueError("invalid version")
    # A single leading "v" or "=" is ignored. Both at once is not allowed.
    if text[0] in "v=":
        text = text[1:]
        if not text or text[0] in "v=":
            raise ValueError("invalid version")
    return _full_version(text)


def _parse_partial(token):
    if token.startswith("v"):
        if len(token) < 2 or not token[1].isdigit():
            raise ValueError("invalid range")
        token = token[1:]
    if token in _WILDCARD:
        return _PV(None, None, None, None)
    if not token:
        raise ValueError("invalid range")
    if "-" in token or "+" in token:
        ver = _full_version(token)
        return _PV(ver.major, ver.minor, ver.patch, ver.pre)
    parts = token.split(".")
    if len(parts) > 3 or parts[0] in _WILDCARD:
        raise ValueError("invalid range")
    vals = []
    seen_wild = False
    for part in parts:
        if part in _WILDCARD:
            seen_wild = True
            vals.append(None)
        else:
            if seen_wild or _NUM.fullmatch(part) is None:
                raise ValueError("invalid range")
            vals.append(int(part))
    while len(vals) < 3:
        vals.append(None)
    return _PV(vals[0], vals[1], vals[2], None)


def _concrete(pv):
    return pv.minor is not None and pv.patch is not None


def _lower(pv):
    minor = 0 if pv.minor is None else pv.minor
    patch = 0 if pv.patch is None else pv.patch
    return _Ver(pv.major, minor, patch, None)


def _bump(pv):
    """Increment the right-most specified component and zero the rest."""
    if pv.minor is None:
        return _Ver(pv.major + 1, 0, 0, None)
    if pv.patch is None:
        return _Ver(pv.major, pv.minor + 1, 0, None)
    return _Ver(pv.major, pv.minor, pv.patch + 1, None)


def _pre0(ver):
    return _Ver(ver.major, ver.minor, ver.patch, _ZERO)


def _anchor(pv):
    if pv.pre is None or pv.major is None or not _concrete(pv):
        return set()
    return {(pv.major, pv.minor, pv.patch)}


def _desugar_partial_op(op, pv):
    """Operators applied to X-ranges / partial versions. See TASK.md."""
    if pv.major is None:
        # >* and <* match nothing; >=* , <=* , =* and * match >=0.0.0.
        if op in (">", "<"):
            return [("none", None)], set()
        return [(">=", _Ver(0, 0, 0, None))], set()
    if _concrete(pv):
        ver = _Ver(pv.major, pv.minor, pv.patch, pv.pre)
        return [(op, ver)], _anchor(pv)
    if op == "=":
        return [(">=", _lower(pv)), ("<", _pre0(_bump(pv)))], set()
    if op == ">":
        return [(">=", _bump(pv))], set()
    if op == ">=":
        return [(">=", _lower(pv))], set()
    if op == "<":
        return [("<", _pre0(_lower(pv)))], set()
    if op == "<=":
        return [("<", _pre0(_bump(pv)))], set()
    raise ValueError("invalid range")


def _desugar_tilde(pv):
    # Tilde on a bare wildcard is not part of the spec.
    if pv.major is None:
        raise ValueError("invalid range")
    if pv.minor is None:
        lo = _Ver(pv.major, 0, 0, None)
        hi = _Ver(pv.major + 1, 0, 0, _ZERO)
        return [(">=", lo), ("<", hi)], set()
    if pv.patch is None:
        lo = _Ver(pv.major, pv.minor, 0, None)
        hi = _Ver(pv.major, pv.minor + 1, 0, _ZERO)
        return [(">=", lo), ("<", hi)], set()
    lo = _Ver(pv.major, pv.minor, pv.patch, pv.pre)
    hi = _Ver(pv.major, pv.minor + 1, 0, _ZERO)
    return [(">=", lo), ("<", hi)], _anchor(pv)


def _desugar_caret(pv):
    if pv.major is None:
        raise ValueError("invalid range")
    if pv.minor is None:
        lo = _Ver(pv.major, 0, 0, None)
        hi = _Ver(pv.major + 1, 0, 0, _ZERO)
        return [(">=", lo), ("<", hi)], set()
    if pv.patch is None:
        lo = _Ver(pv.major, pv.minor, 0, None)
        # ^0.0 / ^0.0.x stay inside 0.1; ^0.1 inside 0.2; ^1.2 inside 2.0.
        if pv.major == 0:
            hi = _Ver(0, pv.minor + 1, 0, _ZERO)
        else:
            hi = _Ver(pv.major + 1, 0, 0, _ZERO)
        return [(">=", lo), ("<", hi)], set()
    lo = _Ver(pv.major, pv.minor, pv.patch, pv.pre)
    if pv.major > 0:
        hi = _Ver(pv.major + 1, 0, 0, _ZERO)
    elif pv.minor > 0:
        hi = _Ver(0, pv.minor + 1, 0, _ZERO)
    else:
        hi = _Ver(0, 0, pv.patch + 1, _ZERO)
    return [(">=", lo), ("<", hi)], _anchor(pv)


def _desugar_hyphen(left, right):
    comps = []
    anchors = set()
    if left.major is not None:
        if _concrete(left):
            comps.append((">=", _Ver(left.major, left.minor, left.patch, left.pre)))
            anchors |= _anchor(left)
        else:
            comps.append((">=", _lower(left)))
    if right.major is not None:
        if _concrete(right):
            comps.append(("<=", _Ver(right.major, right.minor, right.patch, right.pre)))
            anchors |= _anchor(right)
        else:
            comps.append(("<", _pre0(_bump(right))))
    return comps, anchors


def _split_op(token):
    for op in ("<=", ">=", "~", "^", "<", ">", "="):
        if token.startswith(op):
            return op, token[len(op):]
    return "bare", token


def _parse_set(text):
    tokens = text.split()
    # Empty or whitespace-only set means any version, including prereleases.
    # (A "*" comparator is different: it is ">=0.0.0" and the prerelease rule applies.)
    if not tokens:
        return [], set(), True
    comps = []
    anchors = set()
    i = 0
    n = len(tokens)
    while i < n:
        op, rest = _split_op(tokens[i])
        if (
            op == "bare"
            and rest != "-"
            and i + 2 < n
            and tokens[i + 1] == "-"
        ):
            rop, rrest = _split_op(tokens[i + 2])
            if rop != "bare" or rrest in ("", "-"):
                raise ValueError("invalid range")
            left = _parse_partial(rest)
            right = _parse_partial(rrest)
            extra, extra_anchors = _desugar_hyphen(left, right)
            comps.extend(extra)
            anchors |= extra_anchors
            i += 3
            continue
        if rest == "":
            if op == "bare":
                raise ValueError("invalid range")
            i += 1
            if i >= n:
                raise ValueError("invalid range")
            rop, rrest = _split_op(tokens[i])
            if rop != "bare" or rrest in ("", "-"):
                raise ValueError("invalid range")
            rest = rrest
        if rest == "-" or op == "bare" and rest == "-":
            raise ValueError("invalid range")
        pv = _parse_partial(rest)
        if op == "~":
            extra, extra_anchors = _desugar_tilde(pv)
        elif op == "^":
            extra, extra_anchors = _desugar_caret(pv)
        elif op in ("bare", "="):
            extra, extra_anchors = _desugar_partial_op("=", pv)
        elif op in ("<", ">", "<=", ">="):
            extra, extra_anchors = _desugar_partial_op(op, pv)
        else:
            raise ValueError("invalid range")
        comps.extend(extra)
        anchors |= extra_anchors
        i += 1
    return comps, anchors, False


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range")
    return [_parse_set(part) for part in range_.split("||")]


def _set_matches(ver, comps, anchors, match_any):
    if match_any:
        return True
    for op, bound in comps:
        if op == "none":
            return False
        order = _cmp(ver, bound)
        if op == "<":
            ok = order < 0
        elif op == "<=":
            ok = order <= 0
        elif op == ">":
            ok = order > 0
        elif op == ">=":
            ok = order >= 0
        elif op == "=":
            ok = order == 0
        else:
            raise ValueError("invalid range")
        if not ok:
            return False
    if ver.pre is not None and (ver.major, ver.minor, ver.patch) not in anchors:
        return False
    return True


def _matches(ver, sets):
    for comps, anchors, match_any in sets:
        if _set_matches(ver, comps, anchors, match_any):
            return True
    return False


def satisfies(version, range_):
    ver = _parse_version_string(version)
    sets = _parse_range(range_)
    return _matches(ver, sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best_text = None
    best_ver = None
    for raw in versions:
        try:
            ver = _parse_version_string(raw)
        except ValueError:
            continue
        if not _matches(ver, sets):
            continue
        if best_ver is None or _cmp(ver, best_ver) > 0:
            best_text = raw
            best_ver = ver
    return best_text
