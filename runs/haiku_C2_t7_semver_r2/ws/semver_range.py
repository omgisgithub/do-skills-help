"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = re.compile(r"0|[1-9][0-9]*")
_ID = re.compile(r"[0-9A-Za-z-]+")
_WILD = ("x", "X", "*")
_OPS = ("<", "<=", ">", ">=", "=")
_CMP = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "=": operator.eq}


def _ids(text, strict):
    """Split dot-separated identifiers; strict forbids leading zeros on numeric ones."""
    ids = text.split(".")
    for i in ids:
        if not _ID.fullmatch(i) or (strict and i.isdigit() and len(i) > 1 and i[0] == "0"):
            raise ValueError(f"invalid identifier: {text!r}")
    return ids


def _parse(text):
    """Full version without v/= prefix -> ((major, minor, patch), prerelease ids or None)."""
    text, plus, build = text.partition("+")
    core, dash, pre = text.partition("-")
    nums = core.split(".")
    if len(nums) != 3 or not all(_NUM.fullmatch(n) for n in nums):
        raise ValueError(f"invalid version: {core!r}")
    if plus:
        _ids(build, strict=False)
    return tuple(map(int, nums)), (_ids(pre, strict=True) if dash else None)


def _key(core, pre):
    """Sort key: a prerelease sorts below its release; numeric ids sort below alphanumeric ones."""
    if pre is None:
        return (*core, 1, ())
    return (*core, 0, tuple((0, int(i)) if i.isdigit() else (1, i) for i in pre))


def _version(text):
    """Candidate version -> (sort key, core if it has a prerelease else None)."""
    text = text.strip()
    if text[:1] in ("v", "="):
        text = text[1:]
    core, pre = _parse(text)
    return _key(core, pre), (core if pre is not None else None)


def _partial(body):
    """[major, minor, patch] with None for wildcards, or None if body is not a plain (X-range) version."""
    parts = body.split(".")
    if len(parts) > 3:
        return None
    out = []
    for p in parts:
        if p in _WILD:
            out.append(None)
        elif _NUM.fullmatch(p) and None not in out:
            out.append(int(p))
        else:
            return None
    return out + [None] * (3 - len(out))


def _split(body):
    """Range version -> (major, minor, patch, prerelease); wildcard parts are None."""
    if body[:1] == "v":
        body = body[1:]
    parts = _partial(body)
    if parts is None or None not in parts:
        core, pre = _parse(body)
        return (*core, pre)
    return (*parts, None)


def _nxt(major, minor):
    """First version past the X-range that fixes major and maybe minor."""
    return (major + 1, 0, 0) if minor is None else (major, minor + 1, 0)


def _caret_upper(major, minor, patch):
    """Upper bound (exclusive, as a core) for ^ ; the left-most non-zero part stays fixed."""
    if major:
        return (major + 1, 0, 0)
    if minor is None:
        return (1, 0, 0)
    if minor:
        return (0, minor + 1, 0)
    if patch is None:
        return (0, 1, 0)
    return (0, 0, patch + 1)


def _comparators(prefix, body):
    """One range token -> [(operator, bound key, anchor)]; anchor is the core when written with a prerelease."""
    major, minor, patch, pre = _split(body)
    core = (major or 0, minor or 0, patch or 0)
    tag = core if pre is not None else None
    if prefix in ("~", "^"):
        upper = None
        if major is not None:
            upper = _nxt(major, minor) if prefix == "~" else _caret_upper(major, minor, patch)
        return [(">=", _key(core, pre), tag)] + ([("<", _key(upper, ["0"]), None)] if upper else [])
    if None not in (major, minor, patch):
        return [(prefix or "=", _key(core, pre), tag)]
    nxt = _nxt(major, minor) if major is not None else None
    lo = _key(core, None)
    if prefix in ("", "="):
        return [(">=", lo, None)] + ([("<", _key(nxt, ["0"]), None)] if nxt else [])
    if prefix == ">":
        return [(">=", _key(nxt, None), None)] if nxt else [_NOTHING]
    if prefix == ">=":
        return [(">=", lo, None)]
    if prefix == "<":
        return [("<", _key(core, ["0"]), None)]
    return [("<", _key(nxt, ["0"]), None)] if nxt else [(">=", lo, None)]


_NOTHING = ("<", _key((0, 0, 0), ["0"]), None)  # nothing is below 0.0.0-0


def _parse_range(range_):
    sets = []
    for text in range_.split("||"):
        tokens = text.split()
        if len(tokens) == 3 and tokens[1] == "-":
            sets.append(_comparators(">=", tokens[0]) + _comparators("<=", tokens[2]))
            continue
        comps = []
        it = iter(tokens)
        for tok in it:
            if tok in _OPS:  # an operator may be followed by spaces
                tok += next(it, "")
            prefix, body = re.match(r"(<=|>=|<|>|=|~|\^)?(.*)", tok).groups("")
            comps += _comparators(prefix, body)
        sets.append(comps)
    return sets


def _in_set(comps, key, tag):
    if not all(_CMP[op](key, bound) for op, bound, _ in comps):
        return False
    # a prerelease only matches if a comparator names the same MAJOR.MINOR.PATCH with a prerelease
    return tag is None or any(anchor == tag for _, _, anchor in comps)


def satisfies(version, range_):
    key, tag = _version(version)
    return any(_in_set(comps, key, tag) for comps in _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = best_key = None
    for text in versions:
        try:
            key, tag = _version(text)
        except (AttributeError, ValueError):
            continue
        # strict > keeps the first of two equal-precedence entries
        if (best_key is None or key > best_key) and any(_in_set(c, key, tag) for c in sets):
            best, best_key = text, key
    return best
