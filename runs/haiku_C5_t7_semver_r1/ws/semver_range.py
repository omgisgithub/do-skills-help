"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = r"(0|[1-9][0-9]*)"
_IDENT = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    _NUM + r"\." + _NUM + r"\." + _NUM
    + r"(?:-(" + _IDENT + r"(?:\." + _IDENT + r")*))?"
    + r"(?:\+(" + _IDENT + r"(?:\." + _IDENT + r")*))?"
)
_NUM_RE = re.compile(_NUM)
_WILDCARDS = ("*", "x", "X")
_OPS = ("<=", ">=", "<", ">", "=", "~", "^")
_CMP = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "=": operator.eq}
_NEVER = "never"


def _ident_key(ident):
    # Numeric identifiers sort below alphanumeric ones.
    if ident.isdigit():
        return (0, int(ident), "")
    return (1, 0, ident)


def _key(major, minor, patch, pre):
    # A release sorts above any prerelease of the same MAJOR.MINOR.PATCH.
    if pre is None:
        return (major, minor, patch, 1, ())
    return (major, minor, patch, 0, tuple(_ident_key(i) for i in pre))


def _parse_full(text):
    """Return (major, minor, patch, pre_idents_or_None) or None if not a full version."""
    match = _FULL_RE.fullmatch(text)
    if match is None:
        return None
    pre = match.group(4)
    if pre is not None:
        for ident in pre.split("."):
            if ident.isdigit() and len(ident) > 1 and ident[0] == "0":
                raise ValueError("leading zero in numeric prerelease identifier")
        pre = pre.split(".")
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), pre


def _parse_partial(text):
    """Return a list of 3 ints (None for wildcards) or None if not a partial version."""
    parts = text.split(".")
    if len(parts) > 3:
        return None
    nums = []
    for part in parts:
        if part in _WILDCARDS:
            nums.append(None)
        elif None in nums or not _NUM_RE.fullmatch(part):
            return None
        else:
            nums.append(int(part))
    return nums + [None] * (3 - len(nums))


def _parse_version(text):
    """Return (key, prerelease_flag). prerelease_flag is MAJOR.MINOR.PATCH if it has a prerelease."""
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    parsed = _parse_full(s)
    if parsed is None:
        raise ValueError("invalid version: %r" % (text,))
    major, minor, patch, pre = parsed
    flag = (major, minor, patch) if pre is not None else None
    return _key(major, minor, patch, pre), flag


def _parse_operand(text):
    """Return (full, None) or (None, partial_nums) for a range operand."""
    s = text[1:] if text[:1] == "v" else text
    full = _parse_full(s)
    if full is not None:
        return full, None
    nums = _parse_partial(s)
    if nums is None:
        raise ValueError("invalid range operand: %r" % (text,))
    return None, nums


def _partial_upper(count, major, minor):
    # Base (no prerelease) of the version a partial's upper bound stops at.
    if count == 1:
        return (major + 1, 0, 0)
    return (major, minor + 1, 0)


def _partial_caret_upper(count, major, minor):
    if count == 1 or major > 0:
        return (major + 1, 0, 0)
    return (0, minor + 1, 0)


def _full_caret_upper(major, minor, patch):
    if major > 0:
        return (major + 1, 0, 0)
    if minor > 0:
        return (0, minor + 1, 0)
    return (0, 0, patch + 1)


def _comparator(op, text):
    """Desugar one comparator into a list of (op, key, prerelease_flag) primitives."""
    full, nums = _parse_operand(text)
    if full is not None:
        major, minor, patch, pre = full
        key = _key(major, minor, patch, pre)
        flag = (major, minor, patch) if pre is not None else None
        if op in (None, "=", "<", "<=", ">", ">="):
            return [(op or "=", key, flag)]
        if op == "~":
            return [(">=", key, flag), ("<", _key(major, minor + 1, 0, ["0"]), None)]
        # op == "^"
        upper = _full_caret_upper(major, minor, patch)
        return [(">=", key, flag), ("<", _key(*upper, pre=["0"]), None)]

    count = sum(n is not None for n in nums)
    major, minor, patch = [n or 0 for n in nums]
    zero = _key(0, 0, 0, None)
    lower = _key(major, minor, patch, None)
    if count == 0:
        if op in ("<", ">"):
            return [(_NEVER, None, None)]
        if op in (None, "=", ">=", "<="):
            return [(">=", zero, None)]
        raise ValueError("invalid range operand: %r" % (text,))

    upper_base = _partial_upper(count, major, minor)
    if op in (None, "="):
        return [(">=", lower, None), ("<", _key(*upper_base, pre=["0"]), None)]
    if op == ">":
        return [(">=", _key(*upper_base, pre=None), None)]
    if op == ">=":
        return [(">=", lower, None)]
    if op == "<":
        return [("<", _key(major, minor, patch, ["0"]), None)]
    if op == "<=":
        return [("<", _key(*upper_base, pre=["0"]), None)]
    if op == "~":
        return [(">=", lower, None), ("<", _key(*upper_base, pre=["0"]), None)]
    # op == "^"
    upper = _partial_caret_upper(count, major, minor)
    return [(">=", lower, None), ("<", _key(*upper, pre=["0"]), None)]


def _hyphen(left, right):
    left_full, left_nums = _parse_operand(left)
    right_full, right_nums = _parse_operand(right)
    prims = []
    if left_full is not None:
        major, minor, patch, pre = left_full
        flag = (major, minor, patch) if pre is not None else None
        prims.append((">=", _key(major, minor, patch, pre), flag))
    else:
        major, minor, patch = [n or 0 for n in left_nums]
        prims.append((">=", _key(major, minor, patch, None), None))
    if right_full is not None:
        major, minor, patch, pre = right_full
        flag = (major, minor, patch) if pre is not None else None
        prims.append(("<=", _key(major, minor, patch, pre), flag))
    else:
        count = sum(n is not None for n in right_nums)
        if count > 0:
            major, minor, _ = [n or 0 for n in right_nums]
            upper = _partial_upper(count, major, minor)
            prims.append(("<", _key(*upper, pre=["0"]), None))
    return prims


def _parse_set(text):
    tokens = text.split()
    prims = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if i + 1 < len(tokens) and tokens[i + 1] == "-" and tok[:1] not in "<>=~^":
            if i + 2 >= len(tokens):
                raise ValueError("incomplete hyphen range: %r" % (text,))
            prims += _hyphen(tok, tokens[i + 2])
            i += 3
            continue
        op = None
        if tok in _OPS:
            # Operator separated from its operand by whitespace.
            if i + 1 >= len(tokens):
                raise ValueError("operator without operand: %r" % (text,))
            op = tok
            i += 1
            tok = tokens[i]
        else:
            for candidate in _OPS:
                if tok.startswith(candidate):
                    op = candidate
                    tok = tok[len(candidate):]
                    break
        prims += _comparator(op, tok)
        i += 1
    return prims


def _parse_range(range_):
    return [_parse_set(part) for part in range_.split("||")]


def _set_matches(prims, key, flag):
    for op, bound, _ in prims:
        if op == _NEVER or not _CMP[op](key, bound):
            return False
    if flag is None:
        return True
    # A prerelease only matches if a comparator was written with a prerelease on the same MAJOR.MINOR.PATCH.
    return any(f == flag for _, _, f in prims if f is not None)


def satisfies(version, range_):
    key, flag = _parse_version(version)
    return any(_set_matches(prims, key, flag) for prims in _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            key, flag = _parse_version(text)
        except ValueError:
            continue
        if best_key is not None and key <= best_key:
            continue
        if any(_set_matches(prims, key, flag) for prims in sets):
            best = text
            best_key = key
    return best
