"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_VERSION_RE = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
_NUMBER_RE = re.compile(r"0|[1-9][0-9]*")
_WILDCARDS = ("*", "x", "X")
_OPERATORS = ("<=", ">=", "<", ">", "=", "~", "^")
_COMPARATOR_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.+)")
_CMP = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}
# No version sorts below (0.0.0, no prerelease), so this bound matches nothing.
_NOTHING = [("<", (0, 0, 0, 0, ()), None)]


def satisfies(version, range_):
    parsed = _parse_version(version)
    return _satisfies_range(parsed, _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = best_key = None
    for text in versions:
        try:
            parsed = _parse_version(text)
        except ValueError:
            continue
        if not _satisfies_range(parsed, sets):
            continue
        key = _key(*parsed)
        if best_key is None or key > best_key:
            best, best_key = text, key
    return best


def _key(major, minor, patch, pre=None):
    """SemVer precedence as a sortable tuple. Build metadata is never included."""
    if pre is None:
        return (major, minor, patch, 1, ())
    return (
        major,
        minor,
        patch,
        0,
        tuple((0, int(i)) if i.isdigit() else (1, i) for i in pre),
    )


def _zero(major, minor, patch):
    """Upper bound key for the desugared `-0` forms, which exclude prereleases of that version."""
    return _key(major, minor, patch, ["0"])


def _parse_full(text):
    """Return (major, minor, patch, prerelease ids or None), or None if not a full version."""
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        return None
    pre = match.group(4)
    ids = pre.split(".") if pre else None
    if ids and any(i.isdigit() and len(i) > 1 and i[0] == "0" for i in ids):
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), ids)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError(f"version must be a string: {text!r}")
    s = text.strip()
    if s[:1] in ("v", "="):
        s = s[1:]
    parsed = _parse_full(s)
    if parsed is None:
        raise ValueError(f"invalid version: {text!r}")
    return parsed


def _parse_operand(text):
    """Parse a comparator operand into (parts, prerelease).

    `parts` holds one int per numeric component, with None for each wildcard.
    Partial operands never carry a prerelease.
    """
    s = text[1:] if text.startswith("v") else text
    full = _parse_full(s)
    if full is not None:
        return list(full[:3]), full[3]
    parts = []
    for part in s.split("."):
        if part in _WILDCARDS:
            parts.append(None)
        elif _NUMBER_RE.fullmatch(part) and None not in parts:
            parts.append(int(part))
        else:
            raise ValueError(f"invalid version: {text!r}")
    if len(parts) > 3:
        raise ValueError(f"invalid version: {text!r}")
    return parts, None


def _pad(parts):
    return [x or 0 for x in parts] + [0] * (3 - len(parts))


def _bounds(op, parts, pre):
    """Desugar one comparator into (operator, bound key, anchor) triples.

    The anchor is the M.m.p of a version the user wrote with a prerelease tag, or None.
    It drives the prerelease rule; desugared `-0` bounds never set it.
    """
    known = sum(x is not None for x in parts)
    if known == 0:
        return _NOTHING if op in ("<", ">") else [(">=", _key(0, 0, 0), None)]
    major, minor, patch = _pad(parts)
    full = known == 3
    anchor = (major, minor, patch) if pre else None
    low = _key(major, minor, patch, pre)
    high = (major + 1, 0, 0) if known == 1 else (major, minor + 1, 0)

    if op in ("", "="):
        if full:
            return [("=", low, anchor)]
        return [(">=", low, None), ("<", _zero(*high), None)]
    if op == ">=":
        return [(">=", low, anchor)]
    if op == "<":
        if full:
            return [("<", low, anchor)]
        return [("<", _zero(major, minor, patch), None)]
    if op == "<=":
        if full:
            return [("<=", low, anchor)]
        return [("<", _zero(*high), None)]
    if op == ">":
        if full:
            return [(">", low, anchor)]
        return [(">=", _key(*high), None)]
    if op == "~":
        return [(">=", low, anchor), ("<", _zero(*high), None)]

    # Caret: keep the left-most non-zero part fixed.
    if major > 0 or known == 1:
        upper = (major + 1, 0, 0)
    elif minor > 0 or known == 2:
        upper = (0, minor + 1, 0)
    else:
        upper = (0, 0, patch + 1)
    return [(">=", low, anchor), ("<", _zero(*upper), None)]


def _hyphen(left, right):
    return _bounds(">=", *_parse_operand(left)) + _bounds("<=", *_parse_operand(right))


def _parse_set(text):
    tokens = text.split()
    # Operators may be followed by spaces, so glue them to the next token.
    merged = []
    i = 0
    while i < len(tokens):
        if tokens[i] in _OPERATORS and i + 1 < len(tokens):
            merged.append(tokens[i] + tokens[i + 1])
            i += 2
        else:
            merged.append(tokens[i])
            i += 1
    if not merged:
        merged = ["*"]
    if len(merged) == 3 and merged[1] == "-":
        return _hyphen(merged[0], merged[2])

    bounds = []
    for token in merged:
        match = _COMPARATOR_RE.fullmatch(token)
        if match is None:
            raise ValueError(f"invalid comparator: {token!r}")
        parts, pre = _parse_operand(match.group(2))
        bounds.extend(_bounds(match.group(1) or "", parts, pre))
    return bounds


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"range must be a string: {range_!r}")
    return [_parse_set(text) for text in range_.split("||")]


def _set_matches(version, bounds):
    key = _key(*version)
    if not all(_CMP[op](key, bound) for op, bound, _ in bounds):
        return False
    major, minor, patch, pre = version
    if pre is None:
        return True
    return any(anchor == (major, minor, patch) for _, _, anchor in bounds)


def _satisfies_range(version, sets):
    return any(_set_matches(version, bounds) for bounds in sets)
