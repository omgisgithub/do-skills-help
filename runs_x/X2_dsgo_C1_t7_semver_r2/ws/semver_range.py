"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_NUM = r"(?:0|[1-9][0-9]*)"
_WILD = r"(?:[xX*])"
_IDENT = r"[0-9A-Za-z-]+"

_FULL_RE = re.compile(
    r"^(?P<major>" + _NUM + r")\.(?P<minor>" + _NUM + r")\.(?P<patch>" + _NUM + r")"
    r"(?:-(?P<pre>" + _IDENT + r"(?:\." + _IDENT + r")*))?"
    r"(?:\+(?P<build>" + _IDENT + r"(?:\." + _IDENT + r")*))?$"
)

_PART_RE = re.compile(
    r"^(?P<major>" + _NUM + r"|" + _WILD + r")"
    r"(?:\.(?P<minor>" + _NUM + r"|" + _WILD + r"))?"
    r"(?:\.(?P<patch>" + _NUM + r"|" + _WILD + r"))?$"
)

_OPS = ("<=", ">=", "<", ">", "=")

# A version is (major, minor, patch, pre) where pre is a tuple of
# (0, int) for numeric identifiers and (1, str) for alphanumeric ones.
# A comparator is (op, version, prerelease_source).  op may also be "never".


def _bad(text):
    raise ValueError("invalid version or range: %r" % (text,))


def _parse_prerelease(text):
    identifiers = text.split(".")
    parsed = []
    for ident in identifiers:
        if not ident:
            _bad(text)
        if re.fullmatch(r"[0-9]+", ident):
            if len(ident) > 1 and ident[0] == "0":
                _bad(text)
            parsed.append((0, int(ident)))
        else:
            parsed.append((1, ident))
    return tuple(parsed)


def _parse_full(text):
    """Parse a complete MAJOR.MINOR.PATCH[-PRE][+BUILD] version."""
    match = _FULL_RE.fullmatch(text)
    if match is None:
        return None
    pre = ()
    if match.group("pre") is not None:
        pre = _parse_prerelease(match.group("pre"))
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        pre,
    )


def _parse_partial(text):
    """Parse an X-range form, returning (major, minor, patch), None = wildcard."""
    match = _PART_RE.fullmatch(text)
    if match is None:
        return None

    groups = [match.group("major"), match.group("minor"), match.group("patch")]
    values = []
    seen_wildcard = False
    for group in groups:
        if group is None:
            values.append(None)
            continue
        if group in ("x", "X", "*"):
            seen_wildcard = True
            values.append(None)
        else:
            if seen_wildcard:
                _bad(text)
            values.append(int(group))
    return tuple(values)


def _strip_v(text):
    if text.startswith("v"):
        return text[1:]
    return text


def _parse_range_version(text):
    """Parse the version portion of a range token (v prefix allowed)."""
    text = _strip_v(text)
    full = _parse_full(text)
    if full is not None:
        return full
    partial = _parse_partial(text)
    if partial is None:
        _bad(text)
    return (partial[0], partial[1], partial[2], ())


def _c(op, version, prerelease_source=False):
    return (op, version, prerelease_source)


def _never():
    return _c("never", (0, 0, 0, ()))


_ZERO_PRE = ((0, 0),)


def _compare_versions(left, right):
    for index in range(3):
        if left[index] < right[index]:
            return -1
        if left[index] > right[index]:
            return 1

    left_pre = left[3]
    right_pre = right[3]
    if not left_pre and not right_pre:
        return 0
    if not left_pre:
        return 1
    if not right_pre:
        return -1
    if left_pre == right_pre:
        return 0
    return -1 if left_pre < right_pre else 1


def _comparator_matches(comparator, version):
    op, target, _ = comparator
    if op == "never":
        return False
    order = _compare_versions(version, target)
    if op == "<":
        return order < 0
    if op == "<=":
        return order <= 0
    if op == ">":
        return order > 0
    if op == ">=":
        return order >= 0
    return order == 0  # "="


def _desugar_full(op, version):
    if op == "":
        op = "="
    return [_c(op, version, bool(version[3]))]


def _desugar_partial(op, components):
    major, minor, patch = components

    if major is None:
        # The whole partial version is a wildcard (possibly "*.*.*").
        if op in ("", "=", ">=", "<="):
            return [_c(">=", (0, 0, 0, ()))]
        return [_never()]

    if minor is None:
        if op in ("", "="):
            return [
                _c(">=", (major, 0, 0, ())),
                _c("<", (major + 1, 0, 0, _ZERO_PRE)),
            ]
        if op == ">":
            return [_c(">=", (major + 1, 0, 0, ()))]
        if op == ">=":
            return [_c(">=", (major, 0, 0, ()))]
        if op == "<":
            return [_c("<", (major, 0, 0, _ZERO_PRE))]
        return [_c("<", (major + 1, 0, 0, _ZERO_PRE))]  # "<="

    if patch is None:
        if op in ("", "="):
            return [
                _c(">=", (major, minor, 0, ())),
                _c("<", (major, minor + 1, 0, _ZERO_PRE)),
            ]
        if op == ">":
            return [_c(">=", (major, minor + 1, 0, ()))]
        if op == ">=":
            return [_c(">=", (major, minor, 0, ()))]
        if op == "<":
            return [_c("<", (major, minor, 0, _ZERO_PRE))]
        return [_c("<", (major, minor + 1, 0, _ZERO_PRE))]  # "<="

    # All three components are numeric; normally handled as a full version.
    return _desugar_full(op, (major, minor, patch, ()))


def _desugar_tilde(text):
    version = _parse_range_version(text)
    major, minor, patch, pre = version

    if major is None:
        return [_c(">=", (0, 0, 0, ()))]

    lower = _c(">=", (major, minor or 0, patch or 0, pre), bool(pre))
    if minor is None:
        upper = (major + 1, 0, 0, _ZERO_PRE)
    else:
        upper = (major, minor + 1, 0, _ZERO_PRE)
    return [lower, _c("<", upper)]


def _desugar_caret(text):
    version = _parse_range_version(text)
    major, minor, patch, pre = version

    if major is None:
        return [_c(">=", (0, 0, 0, ()))]

    lower = _c(">=", (major, minor or 0, patch or 0, pre), bool(pre))

    if major > 0:
        upper = (major + 1, 0, 0, _ZERO_PRE)
    elif minor is None:
        upper = (1, 0, 0, _ZERO_PRE)
    elif minor > 0:
        upper = (0, minor + 1, 0, _ZERO_PRE)
    elif patch is None:
        upper = (0, 1, 0, _ZERO_PRE)
    elif patch > 0:
        upper = (0, 0, patch + 1, _ZERO_PRE)
    else:
        upper = (0, 0, 1, _ZERO_PRE)
    return [lower, _c("<", upper)]


def _desugar_hyphen(left_text, right_text):
    left = _parse_range_version(left_text)
    upper_side_right = _parse_full(_strip_v(right_text))

    if upper_side_right is not None:
        right = upper_side_right
        right_comparator = _c("<=", right, bool(right[3]))
        result = [
            _c(">=", (left[0] or 0, left[1] or 0, left[2] or 0, left[3]), bool(left[3])),
            right_comparator,
        ]
        return result

    right = _parse_partial(_strip_v(right_text))
    if right is None:
        _bad(right_text)
    major, minor, patch = right

    result = [
        _c(">=", (left[0] or 0, left[1] or 0, left[2] or 0, left[3]), bool(left[3]))
    ]
    if major is None:
        return result
    if minor is None:
        result.append(_c("<", (major + 1, 0, 0, _ZERO_PRE)))
    elif patch is None:
        result.append(_c("<", (major, minor + 1, 0, _ZERO_PRE)))
    else:
        result.append(_c("<=", (major, minor, patch, ())))
    return result


def _parse_comparator(token):
    if token.startswith("~"):
        return _desugar_tilde(token[1:])
    if token.startswith("^"):
        return _desugar_caret(token[1:])

    operator = ""
    rest = token
    for candidate in _OPS:
        if token.startswith(candidate):
            operator = candidate
            rest = token[len(candidate):]
            break

    if rest == "":
        _bad(token)

    rest = _strip_v(rest)
    full = _parse_full(rest)
    if full is not None:
        return _desugar_full(operator, full)

    partial = _parse_partial(rest)
    if partial is None:
        _bad(token)
    return _desugar_partial(operator, partial)


def _parse_set(text):
    tokens = text.split()
    comparators = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "-":
            _bad(text)

        if index + 2 < len(tokens) and tokens[index + 1] == "-":
            comparators.extend(_desugar_hyphen(token, tokens[index + 2]))
            index += 3
            continue

        if token in ("<", "<=", ">", ">=", "=", "~", "^"):
            if index + 1 >= len(tokens):
                _bad(text)
            token = token + tokens[index + 1]
            index += 2
        else:
            index += 1

        comparators.extend(_parse_comparator(token))
    return comparators


def _parse_range(range_):
    if not isinstance(range_, str):
        _bad(range_)
    sets = []
    for part in range_.split("||"):
        sets.append(_parse_set(part))
    return sets


def _set_satisfied(comparators, version):
    for comparator in comparators:
        if not _comparator_matches(comparator, version):
            return False

    if version[3]:
        for _, target, prerelease_source in comparators:
            if (
                prerelease_source
                and target[0] == version[0]
                and target[1] == version[1]
                and target[2] == version[2]
            ):
                return True
        return False
    return True


def _parse_version(version):
    if not isinstance(version, str):
        _bad(version)
    text = version.strip()
    if text.startswith("v") or text.startswith("="):
        text = text[1:]
    parsed = _parse_full(text)
    if parsed is None:
        _bad(version)
    return parsed


def satisfies(version, range_):
    """Return True when *version* satisfies *range_*.

    Raises ValueError if the version or the range is invalid.
    """
    parsed_version = _parse_version(version)
    parsed_range = _parse_range(range_)
    for comparators in parsed_range:
        if _set_satisfied(comparators, parsed_version):
            return True
    return False


def max_satisfying(versions, range_):
    """Return the highest original version string satisfying *range_*, or None."""
    parsed_range = _parse_range(range_)

    best_version = None
    best_text = None
    for text in versions:
        try:
            parsed = _parse_version(text)
        except (ValueError, TypeError):
            continue
        if not any(_set_satisfied(comparators, parsed) for comparators in parsed_range):
            continue
        if best_version is None or _compare_versions(parsed, best_version) > 0:
            best_version = parsed
            best_text = text
    return best_text
