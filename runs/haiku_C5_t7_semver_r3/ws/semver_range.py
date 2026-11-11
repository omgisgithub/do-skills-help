"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = r"(0|[1-9][0-9]*)"
_NUM_RE = re.compile(_NUM)
_FULL_RE = re.compile(
    _NUM + r"\." + _NUM + r"\." + _NUM
    + r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    + r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
_WILDCARDS = ("x", "X", "*")
_OP_TOKENS = ("<", "<=", ">", ">=", "=", "~", "^")
_CMP = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}
# Smaller than every real version, so `<` against it matches nothing.
_MIN_KEY = (0, 0, 0, 0, ())


def _key(mmp, ids):
    """Precedence key; BUILD is never part of it."""
    if ids is None:
        return tuple(mmp) + (1, ())
    return tuple(mmp) + (0, tuple((0, int(i)) if i.isdigit() else (1, i) for i in ids))


def _parse_body(body, partial):
    """Return (parts, prerelease_ids, is_full). Wildcards in partials are None."""
    match = _FULL_RE.fullmatch(body)
    if match:
        pre = match.group(4)
        ids = pre.split(".") if pre else None
        if ids and any(i.isdigit() and len(i) > 1 and i[0] == "0" for i in ids):
            raise ValueError("numeric prerelease identifier has leading zero: %r" % body)
        return [int(match.group(1)), int(match.group(2)), int(match.group(3))], ids, True
    if not partial:
        raise ValueError("invalid version: %r" % body)
    parts = body.split(".")
    if len(parts) > 3:
        raise ValueError("invalid version: %r" % body)
    vals = []
    for part in parts:
        if part in _WILDCARDS:
            vals.append(None)
        elif None in vals or not _NUM_RE.fullmatch(part):
            raise ValueError("invalid version: %r" % body)
        else:
            vals.append(int(part))
    vals += [None] * (3 - len(vals))
    return vals, None, False


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("version must be a string: %r" % (text,))
    body = text.strip()
    if body[:1] in ("v", "="):
        body = body[1:]
    parts, ids, _ = _parse_body(body, partial=False)
    return tuple(parts), ids


def _bump(parts, idx):
    """Increment parts[idx] and zero everything after it."""
    return tuple(parts[:idx]) + (parts[idx] + 1,) + (0,) * (2 - idx)


def _caret_upper(parts):
    """Bump the left-most non-zero part (or the last specified part if all are zero)."""
    for idx, value in enumerate(parts):
        if value is None:
            return _bump(parts, idx - 1)
        if value != 0:
            return _bump(parts, idx)
    return _bump(parts, 2)


def _comparators(token):
    """Desugar one comparator into a list of (operator, key, anchor) bounds.

    `anchor` is the MAJOR.MINOR.PATCH of a user-written prerelease version, else None.
    """
    match = re.fullmatch(r"(<=|>=|<|>|=|~|\^)?(.*)", token)
    op = match.group(1) or "="
    body = match.group(2)
    if body[:1] == "v":
        body = body[1:]
    parts, ids, full = _parse_body(body, partial=True)

    if full:
        mmp = tuple(parts)
        key = _key(mmp, ids)
        anchor = mmp if ids else None
        if op in _CMP:
            return [(op, key, anchor)]
        upper = _bump(mmp, 1) if op == "~" else _caret_upper(parts)
        return [(">=", key, anchor), ("<", _key(upper, ["0"]), None)]

    if op in ("~", "^") and parts[0] is None:
        raise ValueError("invalid range: %r" % token)
    i = parts.index(None)
    lo = tuple(0 if v is None else v for v in parts)
    lower = (">=", _key(lo, None), None)

    if op == "=":
        if i == 0:
            return [lower]
        return [lower, ("<", _key(_bump(parts, i - 1), ["0"]), None)]
    if op == ">=":
        return [lower]
    if op == "<":
        return [("<", _key(lo, ["0"]), None)] if i else [("<", _MIN_KEY, None)]
    if op == ">":
        return [(">=", _key(_bump(parts, i - 1), None), None)] if i else [("<", _MIN_KEY, None)]
    if op == "<=":
        return [("<", _key(_bump(parts, i - 1), ["0"]), None)] if i else [lower]
    upper = _bump(parts, i - 1) if op == "~" else _caret_upper(parts)
    return [lower, ("<", _key(upper, ["0"]), None)]


def _hyphen(left, right):
    left = left[1:] if left[:1] == "v" else left
    right = right[1:] if right[:1] == "v" else right
    lparts, lids, _ = _parse_body(left, partial=True)
    rparts, rids, rfull = _parse_body(right, partial=True)
    lo = tuple(0 if v is None else v for v in lparts)
    comps = [(">=", _key(lo, lids), tuple(lparts) if lids else None)]
    if rfull:
        comps.append(("<=", _key(tuple(rparts), rids), tuple(rparts) if rids else None))
    elif rparts[0] is not None:
        i = rparts.index(None)
        comps.append(("<", _key(_bump(rparts, i - 1), ["0"]), None))
    return comps


def _parse_set(text):
    tokens = text.split()
    if not tokens:
        return []
    if "-" in tokens:
        if len(tokens) != 3 or tokens[1] != "-":
            raise ValueError("invalid hyphen range: %r" % text)
        return _hyphen(tokens[0], tokens[2])
    comps = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in _OP_TOKENS:
            # An operator may be followed by whitespace before its version.
            if i + 1 >= len(tokens) or tokens[i + 1] in _OP_TOKENS:
                raise ValueError("invalid comparator: %r" % text)
            token += tokens[i + 1]
            i += 1
        comps.extend(_comparators(token))
        i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string: %r" % (range_,))
    return [_parse_set(text) for text in range_.split("||")]


def _match_set(comps, version):
    if not comps:
        return True
    mmp, ids = version
    key = _key(mmp, ids)
    if not all(_CMP[op](key, bound) for op, bound, _ in comps):
        return False
    # A prerelease only matches if a comparator names the same MAJOR.MINOR.PATCH with a prerelease.
    return ids is None or any(anchor == mmp for _, _, anchor in comps if anchor)


def satisfies(version, range_):
    ver = _parse_version(version)
    return any(_match_set(comps, ver) for comps in _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            ver = _parse_version(text)
        except ValueError:
            continue
        key = _key(*ver)
        if best_key is not None and key <= best_key:
            continue
        if any(_match_set(comps, ver) for comps in sets):
            best, best_key = text, key
    return best
