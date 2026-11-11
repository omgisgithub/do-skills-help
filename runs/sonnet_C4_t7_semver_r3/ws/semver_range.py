"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    rf"^({_NUM})\.({_NUM})\.({_NUM})"
    rf"(?:-({_PRE_ID}(?:\.{_PRE_ID})*))?"
    rf"(?:\+({_BUILD_ID}(?:\.{_BUILD_ID})*))?$"
)
_WILD = ("*", "x", "X")
_OPERATORS = ("<", "<=", ">", ">=", "=", "~", "^")
_COMPARATOR_RE = re.compile(r"^(>=|<=|>|<|=|~|\^)?(.*)$", re.S)
_PART_RE = re.compile(rf"^(?:{_NUM}|[xX*])$")

# A parsed version: (major, minor, patch, prerelease tuple of str/int identifiers).
# A comparator: (operator, version) where operator is one of <, <=, >, >=, = or "none".


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError(f"invalid version: {text!r}")
    text = text.strip()
    if text[:1] in ("v", "="):
        text = text[1:]
    match = _VERSION_RE.match(text)
    if not match:
        raise ValueError(f"invalid version: {text!r}")
    major, minor, patch, pre = match.group(1, 2, 3, 4)
    return (int(major), int(minor), int(patch), _pre_ids(pre))


def _pre_ids(pre):
    if pre is None:
        return ()
    return tuple(int(i) if i.isdigit() else i for i in pre.split("."))


def _cmp_pre(a, b):
    if not a and not b:
        return 0
    if not a:
        return 1
    if not b:
        return -1
    for x, y in zip(a, b):
        if x == y:
            continue
        x_num, y_num = isinstance(x, int), isinstance(y, int)
        if x_num and y_num:
            return -1 if x < y else 1
        if x_num:
            return -1
        if y_num:
            return 1
        return -1 if x < y else 1
    return (len(a) > len(b)) - (len(a) < len(b))


def _cmp(a, b):
    if a[:3] != b[:3]:
        return -1 if a[:3] < b[:3] else 1
    return _cmp_pre(a[3], b[3])


def _parse_partial(text):
    """Return (major, minor, patch, prerelease); wildcard/missing parts are None."""
    if text[:1] == "v":
        text = text[1:]
    full = _VERSION_RE.match(text)
    if full:
        major, minor, patch, pre = full.group(1, 2, 3, 4)
        return (int(major), int(minor), int(patch), _pre_ids(pre))
    parts = text.split(".")
    if not 1 <= len(parts) <= 3 or not all(_PART_RE.match(p) for p in parts):
        raise ValueError(f"invalid version in range: {text!r}")
    nums = [None if p in _WILD else int(p) for p in parts]
    nums += [None] * (3 - len(nums))
    for earlier, later in zip(nums, nums[1:]):
        if earlier is None and later is not None:
            raise ValueError(f"invalid version in range: {text!r}")
    return (nums[0], nums[1], nums[2], ())


def _lower(major, minor, patch):
    return (major or 0, minor or 0, patch or 0, ())


def _upper_next(major, minor, patch):
    """Exclusive upper bound `<major.minor.patch-0` (not written by the user)."""
    return ("<", (major, minor, patch, (0,)), False)


def _fill(partial):
    major, minor, patch, pre = partial
    return (major or 0, minor or 0, patch or 0, pre)


def _bump(partial):
    """Exclusive upper bound that covers everything matched by the partial version."""
    major, minor, _, _ = partial
    if minor is None:
        return _upper_next(major + 1, 0, 0)
    return _upper_next(major, minor + 1, 0)


def _desugar(op, partial):
    """Return a list of (operator, version, is_written_prerelease)."""
    major, minor, patch, pre = partial
    has_pre = bool(pre)
    any_version = [(">=", (0, 0, 0, ()), False)]
    is_full = patch is not None
    if op in ("", "="):
        if major is None:
            return any_version
        if is_full:
            return [("=", partial, has_pre)]
        return [(">=", _lower(major, minor, patch), False), _bump(partial)]
    if op == ">":
        if major is None:
            return [("none", (0, 0, 0, ()), False)]
        if is_full:
            return [(">", partial, has_pre)]
        bumped = _bump(partial)[1]
        return [(">=", (bumped[0], bumped[1], 0, ()), False)]
    if op == ">=":
        if major is None:
            return any_version
        return [(">=", _fill(partial), has_pre)]
    if op == "<":
        if major is None:
            return [("none", (0, 0, 0, ()), False)]
        if is_full:
            return [("<", partial, has_pre)]
        return [_upper_next(major, minor or 0, 0)]
    if op == "<=":
        if major is None:
            return any_version
        if is_full:
            return [("<=", partial, has_pre)]
        return [_bump(partial)]
    if op == "~":
        if major is None:
            return any_version
        return [(">=", _fill(partial), has_pre), _bump(partial)]
    return _desugar_caret(partial)


def _desugar_caret(partial):
    major, minor, patch, pre = partial
    if major is None:
        return [(">=", (0, 0, 0, ()), False)]
    lower = (">=", _fill(partial), bool(pre))
    if major > 0 or minor is None:
        return [lower, _upper_next(major + 1, 0, 0)]
    if minor > 0 or patch is None:
        return [lower, _upper_next(0, minor + 1, 0)]
    return [lower, _upper_next(0, 0, patch + 1)]


def _hyphen(left_text, right_text):
    left = _parse_partial(left_text)
    right = _parse_partial(right_text)
    result = [(">=", _fill(left), bool(left[3]))] if left[0] is not None else []
    if right[0] is None:
        return result
    if right[2] is not None:
        result.append(("<=", right, bool(right[3])))
    else:
        result.append(_bump(right))
    return result


def _merge_operators(tokens):
    merged = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in _OPERATORS:
            if i + 1 >= len(tokens):
                raise ValueError(f"dangling operator in range: {token!r}")
            token += tokens[i + 1]
            i += 1
        merged.append(token)
        i += 1
    return merged


def _is_plain(token):
    return token != "-" and token[0] not in "<>=~^"


def _parse_set(segment):
    tokens = _merge_operators(segment.split())
    comparators = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError("incomplete hyphen range")
            left, right = tokens[i], tokens[i + 2]
            if not (_is_plain(left) and _is_plain(right)):
                raise ValueError("invalid hyphen range")
            comparators.extend(_hyphen(left, right))
            i += 3
            continue
        if tokens[i] == "-":
            raise ValueError("invalid hyphen range")
        match = _COMPARATOR_RE.match(tokens[i])
        comparators.extend(_desugar(match.group(1) or "", _parse_partial(match.group(2))))
        i += 1
    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_parse_set(segment) for segment in range_.split("||")]


def _matches(version, comparator):
    op, bound, _ = comparator
    if op == "none":
        return False
    order = _cmp(version, bound)
    return {
        "<": order < 0,
        "<=": order <= 0,
        ">": order > 0,
        ">=": order >= 0,
        "=": order == 0,
    }[op]


def _set_matches(version, comparators):
    if not all(_matches(version, c) for c in comparators):
        return False
    if not version[3]:
        return True
    return any(
        written_pre and bound[:3] == version[:3] for _, bound, written_pre in comparators
    )


def _satisfies_parsed(version, parsed_range):
    return any(_set_matches(version, comparators) for comparators in parsed_range)


def satisfies(version, range_):
    """Return whether the version satisfies the range; raise ValueError if either is invalid."""
    parsed_version = _parse_version(version)
    return _satisfies_parsed(parsed_version, _parse_range(range_))


def max_satisfying(versions, range_):
    """Return the highest version string satisfying the range, or None."""
    parsed_range = _parse_range(range_)
    best, best_parsed = None, None
    for candidate in versions:
        try:
            parsed = _parse_version(candidate)
        except ValueError:
            continue
        if not _satisfies_parsed(parsed, parsed_range):
            continue
        if best_parsed is None or _cmp(parsed, best_parsed) > 0:
            best, best_parsed = candidate, parsed
    return best
