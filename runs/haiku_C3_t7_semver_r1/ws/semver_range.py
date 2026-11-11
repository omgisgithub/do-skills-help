"""npm-style version range matching. See TASK.md for the exact spec."""

import operator
import re

_NUM = r"(?:0|[1-9][0-9]*)"
_IDENT = r"[0-9A-Za-z-]+"
_FULL_RE = re.compile(
    rf"({_NUM})\.({_NUM})\.({_NUM})(?:-({_IDENT}(?:\.{_IDENT})*))?(?:\+{_IDENT}(?:\.{_IDENT})*)?"
)
_OPERATOR_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.+)")
# Operators may be followed by spaces, but only when an operand follows.
_OPERATOR_SPACE_RE = re.compile(r"(<=|>=|<|>|=|~|\^)\s+(?=[0-9xXv*])")
_WILDCARDS = ("x", "X", "*")
_OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}
# Matches nothing: no version key sorts below the empty tuple.
_NOTHING = ("<", (), None, False)
_ZERO = ("0",)


def _key(major, minor, patch, pre):
    # A release sorts above its own prereleases; numeric identifiers sort below alphanumeric.
    if not pre:
        return (major, minor, patch, 1, ())
    ids = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre)
    return (major, minor, patch, 0, ids)


def _parse_full(text):
    """Return (major, minor, patch, pre) for a complete version, or None."""
    match = _FULL_RE.fullmatch(text)
    if match is None:
        return None
    pre = tuple(match.group(4).split(".")) if match.group(4) else ()
    if any(i.isdigit() and len(i) > 1 and i[0] == "0" for i in pre):
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), pre


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError(f"invalid version: {text!r}")
    stripped = text.strip()
    if stripped[:1] in ("v", "="):
        stripped = stripped[1:]
    parsed = _parse_full(stripped)
    if parsed is None:
        raise ValueError(f"invalid version: {text!r}")
    return parsed


def _parse_operand(text):
    """Parse a comparator operand; missing or wildcard parts come back as None."""
    if text[:1] == "v":
        text = text[1:]
    parsed = _parse_full(text)
    if parsed is not None:
        return parsed
    parts = text.split(".")
    if len(parts) > 3:
        raise ValueError(f"invalid version: {text!r}")
    values = []
    for part in parts:
        if part in _WILDCARDS:
            values.append(None)
        elif re.fullmatch(_NUM, part) and None not in values:
            values.append(int(part))
        else:
            raise ValueError(f"invalid version: {text!r}")
    values += [None] * (3 - len(values))
    return (*values, ())


def _term(op, major, minor, patch, pre=(), written=False):
    # `written` marks a term whose user-supplied version has a prerelease tag;
    # synthesized bounds such as `<1.3.0-0` are never written.
    return (op, _key(major, minor, patch, pre), (major, minor, patch), written)


def _terms(op, major, minor, patch, pre):
    if major is None:
        if op in ("~", "^"):
            raise ValueError(f"{op} needs a version")
        if op in ("<", ">"):
            return [_NOTHING]
        return [_term(">=", 0, 0, 0)]
    if minor is None or patch is None:
        return _partial_terms(op, major, minor)
    written = bool(pre)
    if op in ("", "=", ">", ">=", "<", "<="):
        return [_term("=" if op == "" else op, major, minor, patch, pre, written)]
    if op == "~":
        return [
            _term(">=", major, minor, patch, pre, written),
            _term("<", major, minor + 1, 0, _ZERO),
        ]
    # Caret: the left-most non-zero part may not change.
    if major > 0:
        upper = (major + 1, 0, 0)
    elif minor > 0:
        upper = (0, minor + 1, 0)
    else:
        upper = (0, 0, patch + 1)
    return [
        _term(">=", major, minor, patch, pre, written),
        _term("<", *upper, _ZERO),
    ]


def _partial_terms(op, major, minor):
    low = (major, minor or 0, 0)
    high = (major + 1, 0, 0) if minor is None else (major, minor + 1, 0)
    if op in ("", "="):
        return [_term(">=", *low), _term("<", *high, _ZERO)]
    if op == ">":
        return [_term(">=", *high)]
    if op == ">=":
        return [_term(">=", *low)]
    if op == "<":
        return [_term("<", major, minor or 0, 0, _ZERO)]
    if op == "<=":
        return [_term("<", *high, _ZERO)]
    if op == "~":
        return [_term(">=", *low), _term("<", *high, _ZERO)]
    # Caret on a partial version.
    if major > 0:
        upper = (major + 1, 0, 0)
    elif minor is None:
        upper = (1, 0, 0)
    elif minor > 0:
        upper = (0, minor + 1, 0)
    else:
        upper = (0, 1, 0)
    return [_term(">=", *low), _term("<", *upper, _ZERO)]


def _comparator_terms(token):
    match = _OPERATOR_RE.fullmatch(token)
    if match is None:
        raise ValueError(f"invalid comparator: {token!r}")
    op, text = match.group(1) or "", match.group(2)
    return _terms(op, *_parse_operand(text))


def _hyphen_terms(low_text, high_text):
    low = _parse_operand(low_text)
    high = _parse_operand(high_text)
    if low[0] is None or high[0] is None:
        raise ValueError("wildcards are not allowed in hyphen ranges")
    return _terms(">=", *low) + _terms("<=", *high)


def _parse_set(text):
    tokens = _OPERATOR_SPACE_RE.sub(r"\1", text).split()
    terms = []
    i = 0
    while i < len(tokens):
        if tokens[i + 1 : i + 2] == ["-"]:
            if i + 2 >= len(tokens):
                raise ValueError(f"incomplete hyphen range: {text!r}")
            terms += _hyphen_terms(tokens[i], tokens[i + 2])
            i += 3
        else:
            terms += _comparator_terms(tokens[i])
            i += 1
    return terms


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError(f"invalid range: {range_!r}")
    return [_parse_set(part) for part in range_.split("||")]


def _set_matches(terms, version):
    major, minor, patch, pre = version
    key = _key(major, minor, patch, pre)
    if not all(_OPS[op](key, term_key) for op, term_key, _, _ in terms):
        return False
    # A prerelease only matches if some comparator names that same
    # major.minor.patch with a prerelease of its own.
    if not pre:
        return True
    mmp = (major, minor, patch)
    return any(written and term_mmp == mmp for _, _, term_mmp, written in terms)


def satisfies(version, range_):
    parsed = _parse_version(version)
    return any(_set_matches(terms, parsed) for terms in _parse_range(range_))


def max_satisfying(versions, range_):
    sets = _parse_range(range_)
    best = None
    best_key = None
    for text in versions:
        try:
            parsed = _parse_version(text)
        except ValueError:
            continue
        if not any(_set_matches(terms, parsed) for terms in sets):
            continue
        key = _key(*parsed)
        # Strict comparison keeps the first of several equal-precedence entries.
        if best_key is None or key > best_key:
            best, best_key = text, key
    return best
