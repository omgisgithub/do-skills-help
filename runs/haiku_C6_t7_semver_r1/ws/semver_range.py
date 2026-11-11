"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_FULL_RE = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
_PARTIAL_RE = re.compile(r"(?:0|[1-9][0-9]*|[xX*])(?:\.(?:0|[1-9][0-9]*|[xX*])){0,2}")
_OP_PREFIXES = ("<=", ">=", "<", ">", "=", "~", "^")
_OP_CHARS = "<>=~^"
_OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}
_ZERO_PRE = ("0",)


def _from_match(m):
    mmp = tuple(int(m.group(i)) for i in (1, 2, 3))
    pre = m.group(4)
    if pre is not None:
        pre = tuple(pre.split("."))
        if any(i.isdigit() and len(i) > 1 and i[0] == "0" for i in pre):
            raise ValueError("leading zero in numeric prerelease identifier")
    return mmp, pre


def _id_key(ident):
    if ident.isdigit():
        return (0, int(ident), "")
    return (1, 0, ident)


def _key(mmp, pre):
    # A release sorts above every prerelease with the same MAJOR.MINOR.PATCH.
    if pre is None:
        return mmp + (1, ())
    return mmp + (0, tuple(_id_key(i) for i in pre))


def _parse_version(version):
    if not isinstance(version, str):
        raise ValueError("version must be a string")
    s = version.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = _FULL_RE.fullmatch(s)
    if not m:
        raise ValueError("invalid version: %r" % (version,))
    mmp, pre = _from_match(m)
    return mmp, pre, _key(mmp, pre)


def _parse_target(text):
    """Parse a comparator body. Returns (parts, pre, is_full); wildcards are None."""
    s = text[1:] if text.startswith("v") else text
    m = _FULL_RE.fullmatch(s)
    if m:
        mmp, pre = _from_match(m)
        return list(mmp), pre, True
    if not _PARTIAL_RE.fullmatch(s):
        raise ValueError("invalid version: %r" % (text,))
    parts = []
    for piece in s.split("."):
        if piece in ("*", "x", "X"):
            parts.append(None)
        elif None in parts:
            raise ValueError("wildcard must be followed only by wildcards: %r" % (text,))
        else:
            parts.append(int(piece))
    return parts + [None] * (3 - len(parts)), None, False


def _x_hi(parts):
    # Exclusive-ish upper bound of an X-range, as a bare MAJOR.MINOR.PATCH.
    w = parts.index(None)
    if w == 0:
        return None
    head = list(parts[:w])
    head[-1] += 1
    return tuple(head + [0] * (3 - w))


def _caret_hi(parts):
    major, minor, patch = parts
    if major is None:
        return None
    if major > 0:
        return (major + 1, 0, 0)
    if minor is None:
        return (1, 0, 0)
    if minor > 0:
        return (0, minor + 1, 0)
    if patch is None:
        return (0, 1, 0)
    return (0, 0, patch + 1)


def _tilde_hi(parts):
    major, minor, _ = parts
    if major is None:
        return None
    if minor is None:
        return (major + 1, 0, 0)
    return (major, minor + 1, 0)


def _comparators(op, body):
    """Desugar one operator + version into (op, bound_key, anchor) triples.

    anchor is the MAJOR.MINOR.PATCH of the written version when that version
    carries a prerelease tag; otherwise None.
    """
    parts, pre, full = _parse_target(body)
    lo = tuple(0 if x is None else x for x in parts)
    anchor = lo if pre is not None else None
    if op in ("^", "~"):
        hi = _caret_hi(parts) if op == "^" else _tilde_hi(parts)
        out = [(">=", _key(lo, pre), anchor)]
        if hi is not None:
            out.append(("<", _key(hi, _ZERO_PRE), None))
        return out
    if full:
        return [(op or "=", _key(lo, pre), anchor)]
    if parts[0] is None:
        if op in ("<", ">"):
            return [("none", None, None)]
        return [(">=", _key(lo, None), None)]
    hi = _x_hi(parts)
    if op == "<":
        return [("<", _key(lo, _ZERO_PRE), None)]
    if op == "<=":
        return [("<", _key(hi, _ZERO_PRE), None)]
    if op == ">":
        return [(">=", _key(hi, None), None)]
    if op == ">=":
        return [(">=", _key(lo, None), None)]
    return [(">=", _key(lo, None), None), ("<", _key(hi, _ZERO_PRE), None)]


def _hyphen(left, right):
    out = _comparators(">=", left)
    right_parts, _, _ = _parse_target(right)
    if right_parts[0] is not None:
        out += _comparators("<=", right)
    return out


def _set_comparators(tokens):
    if len(tokens) == 3 and tokens[1] == "-":
        return _hyphen(tokens[0], tokens[2])
    if "-" in tokens:
        raise ValueError("invalid hyphen range")
    out = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if tok in _OP_PREFIXES:
            if i == len(tokens) or tokens[i][0] in _OP_CHARS:
                raise ValueError("operator without a version")
            tok += tokens[i]
            i += 1
        op = next((p for p in _OP_PREFIXES if tok.startswith(p)), "")
        out.extend(_comparators(op, tok[len(op):]))
    return out


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_set_comparators(chunk.split()) for chunk in range_.split("||")]


def _set_matches(info, comps):
    mmp, pre, key = info
    if not all(op != "none" and _OPERATORS[op](key, bound) for op, bound, _ in comps):
        return False
    if pre is None:
        return True
    return any(anchor == mmp for _, _, anchor in comps)


def _any_set(info, sets):
    return any(_set_matches(info, comps) for comps in sets)


def satisfies(version, range_):
    info = _parse_version(version)
    return _any_set(info, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            info = _parse_version(text)
        except ValueError:
            continue
        if _any_set(info, sets) and (best_key is None or info[2] > best_key):
            best, best_key = text, info[2]
    return best
