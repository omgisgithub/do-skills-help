"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM_RE = re.compile(r"0|[1-9][0-9]*")
_ID = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_VERSION_RE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(%s))?(?:\+(%s))?" % (_ID, _ID))
_OP_SPACE_RE = re.compile(r"(<=|>=|<|>|=|~|\^)\s+")
_OPERATORS = ("<=", ">=", "<", ">", "=", "~", "^")
_CMP = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "=": operator.eq}

# The "-0" prerelease, used for exclusive upper bounds such as <1.3.0-0.
_ZERO = ("0",)


def _id_key(identifier):
    if identifier.isdigit():
        return (0, int(identifier), "")
    return (1, 0, identifier)


def _key(version):
    """Sort key for (major, minor, patch, prerelease) where a release sorts above its prereleases."""
    major, minor, patch, pre = version
    if pre:
        return (major, minor, patch, (0, tuple(_id_key(i) for i in pre)))
    return (major, minor, patch, (1,))


def _parse_version(text):
    """Parse a strict version into (major, minor, patch, prerelease identifiers)."""
    if not isinstance(text, str):
        raise ValueError("version must be a string: %r" % (text,))
    text = text.strip()
    if text[:1] in ("v", "="):
        text = text[1:]
    match = _VERSION_RE.fullmatch(text)
    if not match:
        raise ValueError("invalid version: %r" % (text,))
    major, minor, patch, pre, _build = match.groups()
    pre_ids = tuple(pre.split(".")) if pre else ()
    for identifier in pre_ids:
        if identifier.isdigit() and len(identifier) > 1 and identifier[0] == "0":
            raise ValueError("leading zero in prerelease: %r" % (text,))
    return int(major), int(minor), int(patch), pre_ids


def _parse_xrange(body):
    """Parse a version or partial version. Returns (parts, prerelease); None marks a wildcard."""
    if body[:1] == "=":
        raise ValueError("invalid comparator: %r" % (body,))
    if "-" in body or "+" in body:
        major, minor, patch, pre = _parse_version(body)
        return [major, minor, patch], pre
    if body[:1] == "v":
        body = body[1:]
    segments = body.split(".")
    if len(segments) > 3:
        raise ValueError("invalid version: %r" % (body,))
    parts = []
    for segment in segments:
        if segment in ("x", "X", "*"):
            parts.append(None)
        elif None not in parts and _NUM_RE.fullmatch(segment):
            parts.append(int(segment))
        else:
            raise ValueError("invalid version: %r" % (body,))
    return parts, ()


def _expand(op, parts, pre):
    """Turn one comparator into (operator, key, tag) triples with desugared bounds.

    tag is (major, minor, patch) only for a user-written version that has a prerelease;
    it is what lets a prerelease version match the set. Generated bounds have no tag.
    """
    numeric = parts[: parts.index(None)] if None in parts else parts

    if len(numeric) == 3:
        major, minor, patch = numeric
        version = (major, minor, patch, pre)
        tag = tuple(numeric) if pre else None
        if op in ("", "="):
            return [("=", _key(version), tag)]
        if op in ("<", "<=", ">", ">="):
            return [(op, _key(version), tag)]
        if op == "~":
            upper = (major, minor + 1, 0)
            return [(">=", _key(version), tag), ("<", _key(upper + (_ZERO,)), None)]
        # caret: keep the left-most non-zero part fixed
        if major > 0:
            upper = (major + 1, 0, 0)
        elif minor > 0:
            upper = (0, minor + 1, 0)
        else:
            upper = (0, 0, patch + 1)
        return [(">=", _key(version), tag), ("<", _key(upper + (_ZERO,)), None)]

    if not numeric:
        # bare wildcard: *, x, X
        if op in (">", "<"):
            return [("!", None, None)]
        return [(">=", _key((0, 0, 0, ())), None)]

    major = numeric[0]
    minor = numeric[1] if len(numeric) == 2 else 0
    floor = (major, minor, 0)
    # For ^, a partial with a zero major (^0.0) bounds the minor, not the patch.
    if len(numeric) == 1 or (op == "^" and major > 0):
        ceiling = (major + 1, 0, 0)
    else:
        ceiling = (major, minor + 1, 0)

    if op in ("", "=", "~", "^"):
        return [(">=", _key(floor + ((),)), None), ("<", _key(ceiling + (_ZERO,)), None)]
    if op == ">":
        return [(">=", _key(ceiling + ((),)), None)]
    if op == ">=":
        return [(">=", _key(floor + ((),)), None)]
    if op == "<":
        return [("<", _key(floor + (_ZERO,)), None)]
    return [("<", _key(ceiling + (_ZERO,)), None)]  # <=


def _comparator(token):
    op = next((o for o in _OPERATORS if token.startswith(o)), "")
    parts, pre = _parse_xrange(token[len(op):])
    return _expand(op, parts, pre)


def _hyphen(low_text, high_text):
    low_parts, low_pre = _parse_xrange(low_text)
    high_parts, high_pre = _parse_xrange(high_text)
    return _expand(">=", low_parts, low_pre) + _expand("<=", high_parts, high_pre)


def _parse_set(text):
    tokens = _OP_SPACE_RE.sub(r"\1", text.strip()).split()
    comparators = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i + 1] == "-":
            if i + 2 >= len(tokens):
                raise ValueError("incomplete hyphen range: %r" % (text,))
            comparators += _hyphen(tokens[i], tokens[i + 2])
            i += 3
        else:
            comparators += _comparator(tokens[i])
            i += 1
    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string: %r" % (range_,))
    return [_parse_set(text) for text in range_.split("||")]


def _set_matches(comparators, version):
    key = _key(version)
    for op, bound, _tag in comparators:
        if op not in _CMP or not _CMP[op](key, bound):
            return False
    if not version[3]:
        return True
    # A prerelease only matches if a comparator names the same major.minor.patch with a prerelease.
    return any(tag == version[:3] for _op, _bound, tag in comparators if tag)


def satisfies(version, range_):
    sets = _parse_range(range_)
    version = _parse_version(version)
    return any(_set_matches(comparators, version) for comparators in sets)


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            version = _parse_version(text)
        except ValueError:
            continue
        if not any(_set_matches(comparators, version) for comparators in sets):
            continue
        key = _key(version)
        if best_key is None or key > best_key:
            best, best_key = text, key
    return best
