"""Match semantic versions against npm-style version ranges."""

import re

_IDENTIFIER = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    rf"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    rf"(?:-({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?"
    rf"(?:\+({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?\Z"
)
_PARTIAL_RE = re.compile(
    rf"(0|[1-9][0-9]*|[xX*])"
    rf"(?:\.(0|[1-9][0-9]*|[xX*]))?"
    rf"(?:\.(0|[1-9][0-9]*|[xX*]))?"
    rf"(?:-({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?"
    rf"(?:\+({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?\Z"
)


def _parse_version(value):
    value = value.strip()
    if value[:1] in ("v", "="):
        value = value[1:]
    match = _VERSION_RE.fullmatch(value)
    if match is None:
        raise ValueError("invalid version")
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    for identifier in prerelease:
        if identifier.isdigit() and len(identifier) > 1 and identifier[0] == "0":
            raise ValueError("invalid numeric prerelease identifier")
    return (major, minor, patch, prerelease)


def _compare(left, right):
    if left[:3] != right[:3]:
        return -1 if left[:3] < right[:3] else 1
    a, b = left[3], right[3]
    if not a or not b:
        return 0 if not a and not b else (1 if not a else -1)
    for x, y in zip(a, b):
        if x == y:
            continue
        xn, yn = x.isdigit(), y.isdigit()
        if xn and yn:
            return -1 if int(x) < int(y) else 1
        if xn != yn:
            return -1 if xn else 1
        return -1 if x < y else 1
    return (len(a) > len(b)) - (len(a) < len(b))


def _partial(value):
    value = value.strip()
    if value[:1] in ("v", "="):
        value = value[1:]
    match = _PARTIAL_RE.fullmatch(value)
    if match is None:
        raise ValueError("invalid range version")
    parts = [match.group(i) for i in (1, 2, 3)]
    if match.group(4) or match.group(5):
        if any(part is None or part in ("x", "X", "*") for part in parts):
            raise ValueError("partial versions cannot have prerelease or build")
    first_wild = next((i for i, part in enumerate(parts) if part is None or part in ("x", "X", "*")), 3)
    if any(part not in (None, "x", "X", "*") for part in parts[first_wild:]):
        raise ValueError("invalid partial version")
    nums = [int(part) if i < first_wild else 0 for i, part in enumerate(parts)]
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    for identifier in prerelease:
        if identifier.isdigit() and len(identifier) > 1 and identifier[0] == "0":
            raise ValueError("invalid numeric prerelease identifier")
    return tuple(nums) + (prerelease,), first_wild


def _upper(version, index):
    nums = list(version[:3])
    if index == 0:
        nums[0] += 1
        nums[1:] = [0, 0]
    elif index == 1:
        nums[1] += 1
        nums[2] = 0
    else:
        nums[2] += 1
    return tuple(nums) + (("0",),)


def _comparator_matches(version, op, bound):
    if op == "!":
        return False
    result = _compare(version, bound)
    return {"=": result == 0, ">": result > 0, ">=": result >= 0,
            "<": result < 0, "<=": result <= 0}[op]


def _make_set(text):
    text = text.strip()
    if not text:
        return [], []
    hyphen = re.fullmatch(r"\s*(\S+)\s+-\s+(\S+)\s*", text)
    comps, prerelease_anchors = [], []
    if hyphen:
        left, _ = _partial(hyphen.group(1))
        right, right_wild = _partial(hyphen.group(2))
        comps.append((">=", left))
        if right_wild == 3:
            comps.append(("<=", right))
        elif right_wild == 0:
            pass
        else:
            comps.append(("<", _upper(right, right_wild - 1)))
        if left[3]:
            prerelease_anchors.append(left[:3])
        if right[3]:
            prerelease_anchors.append(right[:3])
        return comps, prerelease_anchors
    token_pattern = re.compile(r"\s*(<=|>=|<|>|=|\^|~)?\s*([^\s]+)")
    tokens = []
    position = 0
    while position < len(text):
        match = token_pattern.match(text, position)
        if match is None or match.end() == position:
            raise ValueError("invalid range")
        tokens.append((match.group(1), match.group(2)))
        position = match.end()
    if text[position:].strip():
        raise ValueError("invalid range")
    for op, raw in tokens:
        parsed, wild = _partial(raw)
        if parsed[3]:
            prerelease_anchors.append(parsed[:3])
        if op in ("~", "^"):
            low = parsed[:3] + (parsed[3],)
            comps.append((">=", low))
            if op == "~":
                bump = 0 if wild == 1 else 1
            elif parsed[0] != 0:
                bump = 0
            elif wild == 1:
                bump = 0
            elif parsed[1] != 0:
                bump = 1
            else:
                bump = 2 if wild == 3 else 1
            comps.append(("<", _upper(parsed, bump)))
        elif wild < 3:
            if wild == 0 and op in (">", "<"):
                comps.append(("!", parsed))
                continue
            if wild == 0 and op in (">=", "<=" ):
                comps.append((">=", (0, 0, 0, ())))
                continue
            if op in (None, "="):
                if wild == 0:
                    comps.append((">=", (0, 0, 0, ())))
                else:
                    comps.extend(((">=", parsed[:3] + ((),)), ("<", _upper(parsed, wild - 1))))
            elif op == ">":
                comps.append((">=", _upper(parsed, wild - 1)) if wild else (">=", _upper(parsed, 0)))
            elif op == ">=":
                comps.append((">=", parsed[:3] + ((),)))
            elif op == "<":
                comps.append(("<", parsed[:3] + (("0",),)))
            elif op == "<=":
                comps.append(("<", _upper(parsed, wild - 1)))
        elif op in (None, "="):
            comps.append(("=", parsed))
        else:
            comps.append((op, parsed))
    return comps, prerelease_anchors


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("invalid range")
    return [_make_set(part) for part in range_.split("||")]


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version satisfies a range, validating both inputs."""
    parsed = _parse_version(version)
    sets = _parse_range(range_)
    for comparators, anchors in sets:
        if all(_comparator_matches(parsed, op, bound) for op, bound in comparators):
            if not parsed[3] or parsed[:3] in anchors:
                return True
    return False


def max_satisfying(versions: list, range_: str):
    """Return the first highest-precedence version satisfying a range."""
    sets = _parse_range(range_)
    best, best_parsed = None, None
    for version in versions:
        if not isinstance(version, str):
            continue
        try:
            parsed = _parse_version(version)
        except ValueError:
            continue
        matched = False
        for comparators, anchors in sets:
            if all(_comparator_matches(parsed, op, bound) for op, bound in comparators) and (
                not parsed[3] or parsed[:3] in anchors
            ):
                matched = True
                break
        if matched and (best_parsed is None or _compare(parsed, best_parsed) > 0):
            best, best_parsed = version, parsed
    return best
