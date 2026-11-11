"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_PRE_ID = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_BUILD_ID = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    rf"({_NUM})\.({_NUM})\.({_NUM})"
    rf"(?:-({_PRE_ID}(?:\.{_PRE_ID})*))?"
    rf"(?:\+({_BUILD_ID}(?:\.{_BUILD_ID})*))?"
)
_NUM_RE = re.compile(_NUM)
_WILDCARDS = ("*", "x", "X")
_OPERATORS = ("<=", ">=", "<", ">", "=", "^", "~")

# A parsed version: (major, minor, patch, prerelease identifiers).
# A comparator: (operator, version, counts_for_prerelease).
_ZERO_PRE = ("0",)


def _pre_key(pre):
    if not pre:
        return (1,)
    return (0, tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre))


def _key(version):
    major, minor, patch, pre = version
    return (major, minor, patch, _pre_key(pre))


def _parse_version(text):
    """Parse a strict full version (leading ``v``/``=`` allowed); raise ValueError."""
    if not isinstance(text, str):
        raise ValueError(f"invalid version: {text!r}")
    text = text.strip()
    if text[:1] in ("v", "="):
        text = text[1:]
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid version: {text!r}")
    major, minor, patch, pre, _build = match.groups()
    return (int(major), int(minor), int(patch), tuple(pre.split(".")) if pre else ())


def _parse_partial(text):
    """Parse a version or partial. Return (major, minor, patch, pre, is_full).

    Wildcard / missing parts are None.
    """
    if text[:1] == "v":
        text = text[1:]
    if _VERSION_RE.fullmatch(text):
        major, minor, patch, pre = _parse_version(text)
        return (major, minor, patch, pre, True)
    parts = text.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"invalid range version: {text!r}")
    values = []
    seen_wildcard = False
    for part in parts:
        if part in _WILDCARDS:
            seen_wildcard = True
            values.append(None)
        elif seen_wildcard or not _NUM_RE.fullmatch(part):
            raise ValueError(f"invalid range version: {text!r}")
        else:
            values.append(int(part))
    values += [None] * (3 - len(values))
    return (values[0], values[1], values[2], (), False)


def _lower(major, minor, patch, pre=()):
    return (">=", (major, minor, patch, pre), bool(pre))


def _upper(major, minor, patch):
    return ("<", (major, minor, patch, _ZERO_PRE), False)


def _bump_upper(major, minor):
    """Exclusive upper bound for a partial with the given defined parts."""
    if minor is None:
        return _upper(major + 1, 0, 0)
    return _upper(major, minor + 1, 0)


_NOTHING = [("<", (0, 0, 0, _ZERO_PRE), False)]


def _desugar_primitive(op, text):
    major, minor, patch, pre, is_full = _parse_partial(text)
    if is_full:
        return [(op, (major, minor, patch, pre), bool(pre))]
    if major is None:
        if op in ("<", ">"):
            return list(_NOTHING)
        return [_lower(0, 0, 0)]
    if op == "=":
        return [_lower(major, minor or 0, 0), _bump_upper(major, minor)]
    if op == ">=":
        return [_lower(major, minor or 0, 0)]
    if op == "<":
        return [_upper(major, minor or 0, 0)]
    if op == ">":
        bound = _bump_upper(major, minor)[1]
        return [_lower(bound[0], bound[1], bound[2])]
    return [_bump_upper(major, minor)]  # "<="


def _desugar_tilde(text):
    major, minor, patch, pre, _ = _parse_partial(text)
    if major is None:
        return [_lower(0, 0, 0)]
    return [_lower(major, minor or 0, patch or 0, pre), _bump_upper(major, minor)]


def _desugar_caret(text):
    major, minor, patch, pre, _ = _parse_partial(text)
    if major is None:
        return [_lower(0, 0, 0)]
    lower = _lower(major, minor or 0, patch or 0, pre)
    if major > 0 or minor is None:
        return [lower, _upper(major + 1, 0, 0)]
    if minor > 0 or patch is None:
        return [lower, _upper(0, minor + 1, 0)]
    return [lower, _upper(0, 0, patch + 1)]


def _desugar_hyphen(left, right):
    major, minor, patch, pre, is_full = _parse_partial(left)
    if major is None:
        result = [_lower(0, 0, 0)]
    else:
        result = [_lower(major, minor or 0, patch or 0, pre)]
    major, minor, patch, pre, is_full = _parse_partial(right)
    if is_full:
        result.append(("<=", (major, minor, patch, pre), bool(pre)))
    elif major is not None:
        result.append(_bump_upper(major, minor))
    return result


def _split_operator(token):
    for op in _OPERATORS:
        if token.startswith(op):
            return op, token[len(op):]
    return "", token


def _parse_set(text):
    tokens = text.split()
    comparators = []
    merged = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "-":
            if not merged or index + 1 >= len(tokens) or merged[-1][0] == "done":
                raise ValueError(f"invalid hyphen range: {text!r}")
            kind, left = merged.pop()
            if kind != "plain":
                raise ValueError(f"invalid hyphen range: {text!r}")
            merged.append(("done", _desugar_hyphen(left, tokens[index + 1])))
            index += 2
            continue
        op, operand = _split_operator(token)
        if op and not operand:
            index += 1
            if index >= len(tokens):
                raise ValueError(f"operator without version: {text!r}")
            operand = tokens[index]
        if op:
            merged.append(("done", _desugar_operator(op, operand)))
        else:
            merged.append(("plain", token))
        index += 1
    for kind, value in merged:
        if kind == "plain":
            comparators.extend(_desugar_primitive("=", value))
        else:
            comparators.extend(value)
    return comparators


def _desugar_operator(op, operand):
    if op == "~":
        return _desugar_tilde(operand)
    if op == "^":
        return _desugar_caret(operand)
    return _desugar_primitive(op, operand)


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_parse_set(part) for part in range_.split("||")]


def _compare_ok(op, candidate, bound):
    left, right = _key(candidate), _key(bound)
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    return left == right


def _matches_set(version, comparators):
    if not all(_compare_ok(op, version, bound) for op, bound, _ in comparators):
        return False
    if not version[3]:
        return True
    return any(
        counts and bound[:3] == version[:3] and bound[3]
        for _, bound, counts in comparators
    )


def satisfies(version, range_):
    """Return True if ``version`` satisfies ``range_``; raise ValueError if either is invalid."""
    parsed = _parse_version(version)
    sets = _parse_range(range_)
    return any(_matches_set(parsed, comparators) for comparators in sets)


def max_satisfying(versions, range_):
    """Return the highest satisfying version string (as given), or None.

    Invalid entries are skipped; an invalid range raises ValueError. Ties go to the
    earliest entry.
    """
    sets = _parse_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            parsed = _parse_version(text)
        except ValueError:
            continue
        if not any(_matches_set(parsed, comparators) for comparators in sets):
            continue
        key = _key(parsed)
        if best_key is None or key > best_key:
            best, best_key = text, key
    return best
