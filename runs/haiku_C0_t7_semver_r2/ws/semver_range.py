"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUMERIC = re.compile(r"[0-9]+")
_CORE_NUM = re.compile(r"0|[1-9][0-9]*")
_IDENT = re.compile(r"[0-9A-Za-z-]+")
_ZERO_PRE = ((0, 0),)  # the prerelease "0" used by desugared "-0" upper bounds
_OP_PREFIXES = (">=", "<=", ">", "<", "=", "~", "^")
_SPACED_OPS = ("<", "<=", ">", ">=", "=")  # these may be followed by spaces
_COMPARE = {
    "=": operator.eq,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


def _vkey(major, minor, patch, pre=None):
    # A release sorts above any prerelease of the same MAJOR.MINOR.PATCH.
    if pre is None:
        return (major, minor, patch, 1, ())
    return (major, minor, patch, 0, pre)


def _prerelease_id(text, original):
    if not _IDENT.fullmatch(text):
        raise ValueError(f"invalid version: {original!r}")
    if _NUMERIC.fullmatch(text):
        if len(text) > 1 and text[0] == "0":
            raise ValueError(f"invalid version: {original!r}")
        return (0, int(text))
    return (1, text)


def _parse_partial(text):
    """Parse a version or partial version into (major, minor, patch, pre).

    Wildcard or missing parts are None. Partial versions never carry a prerelease.
    """
    s = text
    if s[:1] in ("v", "="):
        s = s[1:]
    build = None
    if "+" in s:
        s, build = s.split("+", 1)
        if not all(_IDENT.fullmatch(ident) for ident in build.split(".")):
            raise ValueError(f"invalid version: {text!r}")
    pre = None
    if "-" in s:
        s, pre_text = s.split("-", 1)
        pre = tuple(_prerelease_id(ident, text) for ident in pre_text.split("."))
    parts = s.split(".")
    if len(parts) > 3:
        raise ValueError(f"invalid version: {text!r}")
    nums = []
    wild = False
    for i in range(3):
        part = parts[i] if i < len(parts) else "*"
        if part in ("*", "x", "X"):
            wild = True
            nums.append(None)
        elif wild or not _CORE_NUM.fullmatch(part):
            raise ValueError(f"invalid version: {text!r}")
        else:
            nums.append(int(part))
    if None in nums and (pre is not None or build is not None):
        raise ValueError(f"invalid version: {text!r}")
    return (*nums, pre)


def _parse_version(version):
    if not isinstance(version, str):
        raise ValueError(f"invalid version: {version!r}")
    major, minor, patch, pre = _parse_partial(version.strip())
    if None in (major, minor, patch):
        raise ValueError(f"invalid version: {version!r}")
    return _vkey(major, minor, patch, pre), (major, minor, patch), pre is not None


def _next_partial(major, minor):
    # The first version past a partial such as "1.2" (1.3.0) or "1" (2.0.0).
    return (major + 1, 0) if minor is None else (major, minor + 1)


def _desugar(op, major, minor, patch, pre):
    """Turn one comparator into (operator, key) bounds, or None if it matches nothing."""
    if major is None:  # "*", "x", "X"
        if op in ("", "=", ">=", "<=", "~", "^"):
            return [(">=", _vkey(0, 0, 0))]
        return None  # ">*" and "<*"
    full = patch is not None
    lo = _vkey(major, minor or 0, patch or 0, pre)
    next_a, next_b = _next_partial(major, minor)
    if op in ("", "="):
        if full:
            return [("=", _vkey(major, minor, patch, pre))]
        return [(">=", lo), ("<", _vkey(next_a, next_b, 0, _ZERO_PRE))]
    if op == ">":
        if full:
            return [(">", _vkey(major, minor, patch, pre))]
        return [(">=", _vkey(next_a, next_b, 0))]
    if op == ">=":
        return [(">=", lo)]
    if op == "<":
        return [("<", _vkey(major, minor or 0, patch or 0, _ZERO_PRE if not full else pre))]
    if op == "<=":
        if full:
            return [("<=", _vkey(major, minor, patch, pre))]
        return [("<", _vkey(next_a, next_b, 0, _ZERO_PRE))]
    if op == "~":
        return [(">=", lo), ("<", _vkey(next_a, next_b, 0, _ZERO_PRE))]
    if op == "^":
        if major > 0:
            up = (major + 1, 0, 0)
        elif minor is None:
            up = (1, 0, 0)
        elif patch is None or minor > 0:
            up = (0, minor + 1, 0)
        else:
            up = (0, 0, patch + 1)
        return [(">=", lo), ("<", _vkey(*up, _ZERO_PRE))]
    return None


def _comparator(token):
    op = next((prefix for prefix in _OP_PREFIXES if token.startswith(prefix)), "")
    major, minor, patch, pre = _parse_partial(token[len(op):])
    allow = {(major, minor, patch)} if pre is not None else set()
    return _desugar(op, major, minor, patch, pre), allow


def _hyphen(left, right):
    lo_major, lo_minor, lo_patch, lo_pre = _parse_partial(left)
    hi_major, hi_minor, hi_patch, hi_pre = _parse_partial(right)
    bounds = [(">=", _vkey(lo_major or 0, lo_minor or 0, lo_patch or 0, lo_pre))]
    if hi_major is not None:
        if hi_patch is None:
            next_a, next_b = _next_partial(hi_major, hi_minor)
            bounds.append(("<", _vkey(next_a, next_b, 0, _ZERO_PRE)))
        else:
            bounds.append(("<=", _vkey(hi_major, hi_minor, hi_patch, hi_pre)))
    allow = set()
    for major, minor, patch, pre in ((lo_major, lo_minor, lo_patch, lo_pre),
                                     (hi_major, hi_minor, hi_patch, hi_pre)):
        if pre is not None:
            allow.add((major, minor, patch))
    return bounds, allow


def _parse_set(text):
    """Parse one comparator set into (bounds or None if unsatisfiable, allowed prerelease cores)."""
    tokens = text.split() or ["*"]
    merged = []
    i = 0
    while i < len(tokens):
        if tokens[i] in _SPACED_OPS and i + 1 < len(tokens):
            merged.append(tokens[i] + tokens[i + 1])
            i += 2
        else:
            merged.append(tokens[i])
            i += 1
    bounds = []
    allow = set()
    unsatisfiable = False
    i = 0
    while i < len(merged):
        if i + 1 < len(merged) and merged[i + 1] == "-":
            if i + 2 >= len(merged):
                raise ValueError(f"invalid range: {text!r}")
            part_bounds, part_allow = _hyphen(merged[i], merged[i + 2])
            i += 3
        else:
            part_bounds, part_allow = _comparator(merged[i])
            i += 1
        if part_bounds is None:
            unsatisfiable = True
        else:
            bounds.extend(part_bounds)
        allow.update(part_allow)
    return (None if unsatisfiable else bounds), allow


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_parse_set(text) for text in range_.split("||")]


def _satisfied(key, core, has_pre, sets):
    for bounds, allow in sets:
        if bounds is None:
            continue
        if has_pre and core not in allow:
            continue
        if all(_COMPARE[op](key, bound) for op, bound in bounds):
            return True
    return False


def satisfies(version, range_):
    key, core, has_pre = _parse_version(version)
    return _satisfied(key, core, has_pre, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for candidate in versions:
        try:
            key, core, has_pre = _parse_version(candidate)
        except ValueError:
            continue
        if _satisfied(key, core, has_pre, sets) and (best_key is None or key > best_key):
            best = candidate
            best_key = key
    return best
