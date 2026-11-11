"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_IDENT = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    rf"({_NUM})\.({_NUM})\.({_NUM})(?:-({_IDENT}(?:\.{_IDENT})*))?(?:\+{_IDENT}(?:\.{_IDENT})*)?"
)
_NUM_RE = re.compile(_NUM)
_TOKEN_RE = re.compile(r"(~|\^|<=|>=|<|>|=)?(.+)")
_OPS = ("<", "<=", ">", ">=", "=")
_OPERATORS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}
_ZERO_PRE = ("0",)
# Matches no version: nothing sorts below 0.0.0-0.
_NOTHING = [("<", (0, 0, 0, 0, ((0, 0, ""),)), None)]


def _ids(text):
    ids = tuple(text.split("."))
    for ident in ids:
        if ident.isdigit() and len(ident) > 1 and ident[0] == "0":
            raise ValueError(f"leading zero in prerelease identifier: {ident!r}")
    return ids


def _id_key(ident):
    return (0, int(ident), "") if ident.isdigit() else (1, 0, ident)


def _key(mmp, pre=None):
    """Sort key for a version. A prerelease sorts below the release."""
    if pre is None:
        return (*mmp, 1, ())
    return (*mmp, 0, tuple(_id_key(i) for i in pre))


def _pad(nums):
    return tuple(nums) + (0,) * (3 - len(nums))


def _next(nums):
    """First version past the X-range of a partial version with 1 or 2 numbers."""
    major, minor, _ = _pad(nums)
    if len(nums) == 1:
        return (major + 1, 0, 0)
    return (major, minor + 1, 0)


def _strip_v(text):
    return text[1:] if len(text) > 1 and text[0] == "v" and text[1] in "0123456789" else text


def _parse_version(text):
    """Return (sort key, has prerelease, MAJOR.MINOR.PATCH)."""
    if not isinstance(text, str):
        raise ValueError(f"invalid version: {text!r}")
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    m = _FULL_RE.fullmatch(s)
    if m is None:
        raise ValueError(f"invalid version: {text!r}")
    mmp = tuple(int(x) for x in m.group(1, 2, 3))
    pre = _ids(m.group(4)) if m.group(4) else None
    return _key(mmp, pre), pre is not None, mmp


def _parse_operand(text):
    """Return (numbers, prerelease) for a full or partial version. Numbers has 0-3 items."""
    m = _FULL_RE.fullmatch(text)
    if m is not None:
        pre = _ids(m.group(4)) if m.group(4) else None
        return [int(x) for x in m.group(1, 2, 3)], pre
    parts = text.split(".")
    if len(parts) > 3:
        raise ValueError(f"invalid version: {text!r}")
    nums = []
    wild = False
    for part in parts:
        if part in ("x", "X", "*"):
            wild = True
        elif wild or _NUM_RE.fullmatch(part) is None:
            raise ValueError(f"invalid version: {text!r}")
        else:
            nums.append(int(part))
    return nums, None


def _comparators(op, text):
    """Desugar one operator + operand into (op, bound key, anchor) triples.

    The anchor is the MAJOR.MINOR.PATCH of the written version when it has a
    prerelease tag, and None otherwise (including all synthetic bounds).
    """
    nums, pre = _parse_operand(text)
    n = len(nums)
    mmp = _pad(nums)
    exact = _key(mmp, pre)
    anchor = mmp if pre is not None else None

    if op in ("~", "^"):
        if n == 0:
            raise ValueError(f"invalid range: {op}{text}")
        if op == "~":
            upper = _next(nums) if n == 1 else (mmp[0], mmp[1] + 1, 0)
        elif n == 1 or mmp[0] > 0:
            upper = (mmp[0] + 1, 0, 0)
        elif n == 2 or mmp[1] > 0:
            upper = (0, mmp[1] + 1, 0)
        else:
            upper = (0, 0, mmp[2] + 1)
        return [(">=", exact, anchor), ("<", _key(upper, _ZERO_PRE), None)]

    if op in ("", "="):
        if n == 0:
            return [(">=", _key((0, 0, 0)), None)]
        if n == 3:
            return [(">=", exact, anchor), ("<=", exact, anchor)]
        return [(">=", exact, None), ("<", _key(_next(nums), _ZERO_PRE), None)]
    if op == ">":
        if n == 0:
            return _NOTHING
        if n == 3:
            return [(">", exact, anchor)]
        return [(">=", _key(_next(nums)), None)]
    if op == ">=":
        if n == 0:
            return [(">=", _key((0, 0, 0)), None)]
        return [(">=", exact, anchor)]
    if op == "<":
        if n == 0:
            return _NOTHING
        if n == 3:
            return [("<", exact, anchor)]
        return [("<", _key(mmp, _ZERO_PRE), None)]
    # op == "<="
    if n == 0:
        return [(">=", _key((0, 0, 0)), None)]
    if n == 3:
        return [("<=", exact, anchor)]
    return [("<", _key(_next(nums), _ZERO_PRE), None)]


def _hyphen(left, right):
    lnums, lpre = _parse_operand(_strip_v(left))
    rnums, rpre = _parse_operand(_strip_v(right))
    lmmp = _pad(lnums)
    comps = [(">=", _key(lmmp, lpre), lmmp if lpre is not None else None)]
    rmmp = _pad(rnums)
    if len(rnums) == 3:
        comps.append(("<=", _key(rmmp, rpre), rmmp if rpre is not None else None))
    elif rnums:
        comps.append(("<", _key(_next(rnums), _ZERO_PRE), None))
    return comps


def _token_comparators(token):
    m = _TOKEN_RE.fullmatch(token)
    if m is None:
        raise ValueError(f"invalid comparator: {token!r}")
    return _comparators(m.group(1) or "", _strip_v(m.group(2)))


def _tokens(text):
    """Split a comparator set, joining an operator to a following operand (`>= 1.2.3`)."""
    raw = text.split()
    tokens = []
    i = 0
    while i < len(raw):
        tok = raw[i]
        if tok in _OPS and i + 1 < len(raw) and raw[i + 1] not in _OPS and raw[i + 1] != "-":
            tok += raw[i + 1]
            i += 2
        else:
            i += 1
        tokens.append(tok)
    return tokens


def _parse_set(text):
    tokens = _tokens(text)
    comps = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError(f"invalid hyphen range: {text!r}")
            comps += _hyphen(tokens[i], tokens[i + 2])
            i += 3
        else:
            comps += _token_comparators(tokens[i])
            i += 1
    return comps


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_parse_set(part) for part in range_.split("||")]


def _set_matches(comps, key, is_pre, mmp):
    if not all(_OPERATORS[op](key, bound) for op, bound, _ in comps):
        return False
    # A prerelease version needs a comparator written with a prerelease on the same MAJOR.MINOR.PATCH.
    return not is_pre or any(anchor == mmp for _, _, anchor in comps)


def satisfies(version, range_):
    key, is_pre, mmp = _parse_version(version)
    return any(_set_matches(s, key, is_pre, mmp) for s in _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for candidate in versions:
        try:
            key, is_pre, mmp = _parse_version(candidate)
        except ValueError:
            continue
        if not any(_set_matches(s, key, is_pre, mmp) for s in sets):
            continue
        if best_key is None or key > best_key:
            best, best_key = candidate, key
    return best
