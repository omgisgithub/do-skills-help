"""npm-style version range matching. See TASK.md for the exact spec."""

import re

_NUM = r"(?:0|[1-9][0-9]*)"
_IDENT = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    rf"({_NUM})\.({_NUM})\.({_NUM})(?:-({_IDENT}(?:\.{_IDENT})*))?(?:\+({_IDENT}(?:\.{_IDENT})*))?"
)
_NUM_RE = re.compile(_NUM)
_NUMERIC_IDENT_RE = re.compile(r"[0-9]+")
_WILDCARDS = ("x", "X", "*")
_OPERATORS = ("<=", ">=", "<", ">", "=", "~", "^")

_MIN_PRE = (0, ((0, 0),))  # prerelease "-0", lower than any other prerelease


def _parse_pre(text):
    ids = []
    for ident in text.split("."):
        if _NUMERIC_IDENT_RE.fullmatch(ident):
            if len(ident) > 1 and ident[0] == "0":
                raise ValueError(f"invalid prerelease identifier: {ident!r}")
            ids.append((0, int(ident)))
        else:
            ids.append((1, ident))
    return tuple(ids)


def _key(major, minor, patch, pre=None):
    """Build a totally ordered key; no prerelease sorts above any prerelease."""
    return (major, minor, patch, (1,) if not pre else (0, pre))


def _parse_full(text):
    """Parse a strict full version into (major, minor, patch, pre tuple)."""
    match = _FULL_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid version: {text!r}")
    major, minor, patch, pre, _build = match.groups()
    return int(major), int(minor), int(patch), _parse_pre(pre) if pre else ()


def _parse_partial(text):
    """Parse a possibly partial version; missing/wildcard parts are None."""
    if text.startswith("v"):
        text = text[1:]
    if "-" in text or "+" in text:
        return _parse_full(text)
    parts = text.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"invalid version: {text!r}")
    values = []
    seen_wildcard = False
    for part in parts:
        if part in _WILDCARDS:
            seen_wildcard = True
            values.append(None)
        elif seen_wildcard or not _NUM_RE.fullmatch(part):
            raise ValueError(f"invalid version: {text!r}")
        else:
            values.append(int(part))
    values.extend([None] * (3 - len(values)))
    return (*values, ())


def _parse_version(version):
    if not isinstance(version, str):
        raise ValueError(f"invalid version: {version!r}")
    text = version.strip()
    if text[:1] in ("v", "="):
        text = text[1:]
    major, minor, patch, pre = _parse_full(text)
    return _key(major, minor, patch, pre), bool(pre), (major, minor, patch)


def _bump(major, minor, patch):
    """Upper bound (exclusive) of a partial version: the next unit, prerelease-free."""
    if minor is None:
        return _key(major + 1, 0, 0, _MIN_PRE[1])
    if patch is None:
        return _key(major, minor + 1, 0, _MIN_PRE[1])
    raise ValueError("full version has no bump")


def _lower(major, minor, patch):
    return _key(major or 0, minor or 0, patch or 0)


def _desugar_partial(op, parsed):
    """Return (comparators, tag) for an operator applied to a (partial) version."""
    major, minor, patch, pre = parsed
    tag = (major, minor, patch) if pre else None
    if major is None:
        if op in (">", "<"):
            return [("never", None)], None
        return [(">=", _lower(0, 0, 0))], None
    if patch is not None:
        key = _key(major, minor, patch, pre)
        return [("=" if op == "" else op, key)], tag
    low = _lower(major, minor, patch)
    high = _bump(major, minor, patch)
    if op in ("", "="):
        return [(">=", low), ("<", high)], None
    if op == ">":
        return [(">=", high)], None
    if op == ">=":
        return [(">=", low)], None
    if op == "<":
        return [("<", low)], None
    return [("<", high)], None  # "<="


def _desugar_tilde(parsed):
    major, minor, patch, pre = parsed
    if major is None:
        return [(">=", _lower(0, 0, 0))], None
    tag = (major, minor, patch) if pre else None
    low = _key(major, minor or 0, patch or 0, pre)
    high = _bump(major, minor, None) if minor is not None else _bump(major, None, None)
    return [(">=", low), ("<", high)], tag


def _desugar_caret(parsed):
    major, minor, patch, pre = parsed
    if major is None:
        return [(">=", _lower(0, 0, 0))], None
    tag = (major, minor, patch) if pre else None
    low = _key(major, minor or 0, patch or 0, pre)
    if major > 0:
        high = _bump(major, None, None)
    elif minor is None:
        high = _bump(major, None, None)
    elif minor > 0 or patch is None:
        high = _bump(major, minor, None)
    else:
        high = _key(0, 0, patch + 1, _MIN_PRE[1])
    return [(">=", low), ("<", high)], tag


def _desugar_hyphen(left, right):
    low_major, low_minor, low_patch, low_pre = left
    result = [(">=", _key(low_major or 0, low_minor or 0, low_patch or 0, low_pre))]
    tags = []
    if low_pre:
        tags.append((low_major, low_minor, low_patch))
    major, minor, patch, pre = right
    if major is None:
        pass
    elif patch is None:
        result.append(("<", _bump(major, minor, None)))
    else:
        result.append(("<=", _key(major, minor, patch, pre)))
        if pre:
            tags.append((major, minor, patch))
    return result, tags


def _tokenize(text):
    """Split a comparator set into tokens, gluing lone operators to what follows."""
    raw = text.split()
    tokens = []
    i = 0
    while i < len(raw):
        token = raw[i]
        if token in _OPERATORS:
            if i + 1 >= len(raw):
                raise ValueError(f"dangling operator in {text!r}")
            token += raw[i + 1]
            i += 1
        tokens.append(token)
        i += 1
    return tokens


def _split_operator(token):
    for op in _OPERATORS:
        if token.startswith(op):
            return op, token[len(op):]
    return "", token


def _compile_set(text):
    """Compile one comparator set into (comparators, tags)."""
    tokens = _tokenize(text)
    comparators = []
    tags = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError(f"invalid hyphen range in {text!r}")
            left = _parse_partial(token)
            right = _parse_partial(tokens[i + 2])
            comps, new_tags = _desugar_hyphen(left, right)
            comparators.extend(comps)
            tags.extend(new_tags)
            i += 3
            continue
        op, rest = _split_operator(token)
        parsed = _parse_partial(rest)
        if op == "~":
            comps, tag = _desugar_tilde(parsed)
        elif op == "^":
            comps, tag = _desugar_caret(parsed)
        else:
            comps, tag = _desugar_partial(op, parsed)
        comparators.extend(comps)
        if tag is not None:
            tags.append(tag)
        i += 1
    return comparators, tags


def _compile_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_compile_set(part) for part in range_.split("||")]


def _holds(op, key, target):
    if op == "never":
        return False
    if op == "=":
        return key == target
    if op == ">":
        return key > target
    if op == ">=":
        return key >= target
    if op == "<":
        return key < target
    return key <= target


def _matches(parsed_version, compiled):
    key, has_pre, triple = parsed_version
    for comparators, tags in compiled:
        if not all(_holds(op, key, target) for op, target in comparators):
            continue
        if has_pre and triple not in tags:
            continue
        return True
    return False


def satisfies(version, range_):
    """Return whether ``version`` satisfies ``range_``.

    Raises:
        ValueError: If the version or the range is invalid.
    """
    parsed = _parse_version(version)
    return _matches(parsed, _compile_range(range_))


def max_satisfying(versions, range_):
    """Return the highest version string satisfying ``range_``, or None.

    Invalid entries are skipped; ties keep the earliest entry.

    Raises:
        ValueError: If the range is invalid.
    """
    compiled = _compile_range(range_)
    best = None
    best_key = None
    for version in versions:
        try:
            parsed = _parse_version(version)
        except ValueError:
            continue
        if not _matches(parsed, compiled):
            continue
        if best_key is None or parsed[0] > best_key:
            best, best_key = version, parsed[0]
    return best
