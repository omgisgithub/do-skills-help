"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    rf"({_NUM})\.({_NUM})\.({_NUM})"
    rf"(?:-({_PRE_ID}(?:\.{_PRE_ID})*))?"
    rf"(?:\+{_BUILD_ID}(?:\.{_BUILD_ID})*)?"
)
_NUM_RE = re.compile(_NUM)
_OP_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.*)")
_OPERATORS = ("<=", ">=", "<", ">", "=", "~", "^")
_WILDCARDS = ("x", "X", "*")
_NEVER = "never"
_COMPARE = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}


def _strip_prefix(text):
    if not isinstance(text, str):
        raise ValueError(f"not a string: {text!r}")
    text = text.strip()
    if text[:1] in ("v", "="):
        text = text[1:]
    return text


def _version_parts(m):
    pre = m.group(4)
    return (
        int(m.group(1)),
        int(m.group(2)),
        int(m.group(3)),
        None if pre is None else tuple(pre.split(".")),
    )


def _ident_key(ident):
    if ident.isdigit():
        return (0, int(ident), "")
    return (1, 0, ident)


def _precedence(major, minor, patch, pre):
    if pre is None:
        return (major, minor, patch, 1, ())
    return (major, minor, patch, 0, tuple(_ident_key(i) for i in pre))


def _bound(major, minor, patch):
    """The `-0` upper bound: sorts below every prerelease of major.minor.patch."""
    return _precedence(major, minor, patch, ("0",))


def _parse_version(text):
    m = _VERSION_RE.fullmatch(_strip_prefix(text))
    if m is None:
        raise ValueError(f"invalid version: {text!r}")
    return _version_parts(m)


def _parse_spec(text):
    """Return (nums, pre). A full version gives three nums; a partial gives fewer."""
    text = _strip_prefix(text)
    m = _VERSION_RE.fullmatch(text)
    if m is not None:
        major, minor, patch, pre = _version_parts(m)
        return [major, minor, patch], pre
    parts = text.split(".")
    if len(parts) > 3:
        raise ValueError(f"invalid version: {text!r}")
    nums = []
    wild = False
    for part in parts:
        if part in _WILDCARDS:
            wild = True
        elif wild or _NUM_RE.fullmatch(part) is None:
            raise ValueError(f"invalid version: {text!r}")
        else:
            nums.append(int(part))
    return nums, None


def _caret_upper(major, minor, patch, k):
    if major > 0 or k == 1:
        return (major + 1, 0, 0)
    if minor > 0 or k == 2:
        return (0, minor + 1, 0)
    return (0, 0, patch + 1)


def _compile_comparator(op, text):
    """Desugar one comparator into (op, bound, marker) triples.

    The marker is the MAJOR.MINOR.PATCH of the written version when that version
    has a prerelease tag, else None.
    """
    nums, pre = _parse_spec(text)
    op = op or "="
    k = len(nums)
    major, minor, patch = (nums + [0, 0, 0])[:3]

    if k == 3:
        marker = (major, minor, patch) if pre is not None else None
        key = _precedence(major, minor, patch, pre)
        if op == "~":
            return [(">=", key, marker), ("<", _bound(major, minor + 1, 0), None)]
        if op == "^":
            upper = _caret_upper(major, minor, patch, k)
            return [(">=", key, marker), ("<", _bound(*upper), None)]
        return [(op, key, marker)]

    if op in ("~", "^") and k == 0:
        raise ValueError(f"invalid range comparator: {op}{text!r}")
    lo = _precedence(major, minor, 0, None)
    if k == 0:
        if op in ("<", ">"):
            return [(_NEVER, None, None)]
        return [(">=", lo, None)]
    if op == "^":
        upper = _caret_upper(major, minor, patch, k)
        return [(">=", lo, None), ("<", _bound(*upper), None)]
    hi = _bound(major + 1, 0, 0) if k == 1 else _bound(major, minor + 1, 0)
    if op in ("=", "~"):
        return [(">=", lo, None), ("<", hi, None)]
    if op == ">":
        nxt = (major + 1, 0, 0) if k == 1 else (major, minor + 1, 0)
        return [(">=", _precedence(*nxt, None), None)]
    if op == ">=":
        return [(">=", lo, None)]
    if op == "<":
        return [("<", _bound(major, minor, 0), None)]
    return [("<", hi, None)]


def _compile_set(text):
    tokens = text.split()
    comps = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError(f"invalid hyphen range: {text!r}")
            comps += _compile_comparator(">=", tokens[i])
            comps += _compile_comparator("<=", tokens[i + 2])
            i += 3
        elif tokens[i] in _OPERATORS:
            if i + 1 >= len(tokens):
                raise ValueError(f"missing version after {tokens[i]!r}")
            comps += _compile_comparator(tokens[i], tokens[i + 1])
            i += 2
        else:
            op, rest = _OP_RE.fullmatch(tokens[i]).groups()
            comps += _compile_comparator(op, rest)
            i += 1
    return comps


def _compile_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"not a string: {range_!r}")
    return [_compile_set(s) for s in range_.split("||")]


def _set_matches(version, comps):
    major, minor, patch, pre = version
    key = _precedence(major, minor, patch, pre)
    for op, bound, _ in comps:
        if op == _NEVER or not _COMPARE[op](key, bound):
            return False
    if pre is None:
        return True
    return any(marker == (major, minor, patch) for _, _, marker in comps if marker)


def satisfies(version, range_):
    parsed = _parse_version(version)
    sets = _compile_range(range_)
    return any(_set_matches(parsed, comps) for comps in sets)


def max_satisfying(versions, range_):
    sets = _compile_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            parsed = _parse_version(text)
        except ValueError:
            continue
        if not any(_set_matches(parsed, comps) for comps in sets):
            continue
        key = _precedence(*parsed)
        if best_key is None or key > best_key:
            best, best_key = text, key
    return best
