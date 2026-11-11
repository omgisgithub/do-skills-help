"""npm-style version range matching. See TASK.md for the exact spec."""

import re


_PARTIAL_RE = re.compile(
    r"^(?P<core>(?:[0-9]+|\*|[xX])(?:\.(?:[0-9]+|\*|[xX])){0,2})"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

_OPERATOR_RE = re.compile(r"^(<=|>=|<|>|=|~|\^)(.*)$")

_OPERATOR_ONLY = ("<", "<=", ">", ">=", "=", "~", "^")


class _Version(object):
    __slots__ = ("major", "minor", "patch", "prerelease")

    def __init__(self, major, minor, patch, prerelease=()):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease)


class _Partial(object):
    __slots__ = ("major", "minor", "patch", "prerelease", "build")

    def __init__(self, major, minor, patch, prerelease=(), build=()):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease)
        self.build = tuple(build)


def _validate_identifiers(text, prerelease):
    identifiers = text.split(".")
    for identifier in identifiers:
        if (
            prerelease
            and identifier.isdigit()
            and len(identifier) > 1
            and identifier[0] == "0"
        ):
            raise ValueError("invalid prerelease identifier")
    return tuple(identifiers)


def _parse_partial(text, allow_v=True):
    if not isinstance(text, str):
        raise ValueError("version must be a string")

    value = text
    if allow_v and len(value) > 1 and value[0] == "v" and value[1].isdigit():
        value = value[1:]

    match = _PARTIAL_RE.fullmatch(value)
    if match is None:
        raise ValueError("invalid version")

    core = match.group("core")
    prerelease_text = match.group("pre")
    build_text = match.group("build")

    parts = core.split(".")
    numbers = []
    wildcard_seen = False

    for index, part in enumerate(parts):
        if part in ("*", "x", "X"):
            if index == 0 and len(parts) > 1:
                raise ValueError("invalid wildcard version")
            wildcard_seen = True
            numbers.append(None)
        else:
            if wildcard_seen:
                raise ValueError("invalid wildcard version")
            if len(part) > 1 and part[0] == "0":
                raise ValueError("leading zero in version")
            numbers.append(int(part))

    while len(numbers) < 3:
        numbers.append(None)

    major, minor, patch = numbers

    if prerelease_text is not None or build_text is not None:
        if major is None or minor is None or patch is None:
            raise ValueError("partial version cannot have prerelease or build")

    prerelease = (
        _validate_identifiers(prerelease_text, True)
        if prerelease_text is not None
        else ()
    )
    build = (
        _validate_identifiers(build_text, False)
        if build_text is not None
        else ()
    )

    return _Partial(major, minor, patch, prerelease, build)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("version must be a string")

    value = text.strip()
    if value[:1] in ("v", "="):
        value = value[1:]

    partial = _parse_partial(value, allow_v=False)
    if partial.major is None or partial.minor is None or partial.patch is None:
        raise ValueError("not a complete version")

    return _Version(
        partial.major, partial.minor, partial.patch, partial.prerelease
    )


def _compare_prerelease(left, right):
    for left_id, right_id in zip(left, right):
        if left_id == right_id:
            continue

        left_numeric = left_id.isdigit()
        right_numeric = right_id.isdigit()

        if left_numeric and right_numeric:
            left_number = int(left_id)
            right_number = int(right_id)
            if left_number < right_number:
                return -1
            if left_number > right_number:
                return 1
            continue

        if left_numeric:
            return -1
        if right_numeric:
            return 1

        if left_id < right_id:
            return -1
        if left_id > right_id:
            return 1

    if len(left) < len(right):
        return -1
    if len(left) > len(right):
        return 1
    return 0


def _compare_versions(left, right):
    if left.major != right.major:
        return -1 if left.major < right.major else 1
    if left.minor != right.minor:
        return -1 if left.minor < right.minor else 1
    if left.patch != right.patch:
        return -1 if left.patch < right.patch else 1

    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1
    return _compare_prerelease(left.prerelease, right.prerelease)


def _version(major, minor, patch, prerelease=()):
    return _Version(major, minor, patch, prerelease)


def _lower_from_partial(partial):
    major = 0 if partial.major is None else partial.major
    minor = 0 if partial.minor is None else partial.minor
    patch = 0 if partial.patch is None else partial.patch

    if (
        partial.major is not None
        and partial.minor is not None
        and partial.patch is not None
    ):
        prerelease = partial.prerelease
    else:
        prerelease = ()

    return _version(major, minor, patch, prerelease)


def _anchor_for(partial):
    if (
        partial.major is not None
        and partial.minor is not None
        and partial.patch is not None
        and partial.prerelease
    ):
        return (partial.major, partial.minor, partial.patch)
    return None


def _desugar(operator, partial):
    comparators = []
    anchors = set()
    impossible = False

    def add(op, version):
        comparators.append((op, version))

    def add_anchor():
        anchor = _anchor_for(partial)
        if anchor is not None:
            anchors.add(anchor)

    if operator in ("", "="):
        if partial.major is None:
            add(">=", _version(0, 0, 0))
        elif partial.minor is None:
            add(">=", _lower_from_partial(partial))
            add("<", _version(partial.major + 1, 0, 0, ("0",)))
        elif partial.patch is None:
            add(">=", _lower_from_partial(partial))
            add("<", _version(partial.major, partial.minor + 1, 0, ("0",)))
        else:
            add("=", _lower_from_partial(partial))
            add_anchor()

    elif operator == ">":
        if partial.major is None:
            impossible = True
        elif partial.minor is None:
            add(">=", _version(partial.major + 1, 0, 0))
        elif partial.patch is None:
            add(">=", _version(partial.major, partial.minor + 1, 0))
        else:
            add(">", _lower_from_partial(partial))
            add_anchor()

    elif operator == ">=":
        if partial.major is None:
            add(">=", _version(0, 0, 0))
        else:
            add(">=", _lower_from_partial(partial))
            add_anchor()

    elif operator == "<":
        if partial.major is None:
            impossible = True
        elif partial.minor is None:
            add("<", _version(partial.major, 0, 0, ("0",)))
        elif partial.patch is None:
            add("<", _version(partial.major, partial.minor, 0, ("0",)))
        else:
            add("<", _lower_from_partial(partial))
            add_anchor()

    elif operator == "<=":
        if partial.major is None:
            add(">=", _version(0, 0, 0))
        elif partial.minor is None:
            add("<", _version(partial.major + 1, 0, 0, ("0",)))
        elif partial.patch is None:
            add("<", _version(partial.major, partial.minor + 1, 0, ("0",)))
        else:
            add("<=", _lower_from_partial(partial))
            add_anchor()

    elif operator == "~":
        if partial.major is None:
            add(">=", _version(0, 0, 0))
        else:
            add(">=", _lower_from_partial(partial))
            add_anchor()
            if partial.minor is None:
                add("<", _version(partial.major + 1, 0, 0, ("0",)))
            else:
                add("<", _version(partial.major, partial.minor + 1, 0, ("0",)))

    elif operator == "^":
        if partial.major is None:
            add(">=", _version(0, 0, 0))
        else:
            add(">=", _lower_from_partial(partial))
            add_anchor()

            if partial.major > 0:
                upper = _version(partial.major + 1, 0, 0, ("0",))
            elif partial.minor is None:
                upper = _version(1, 0, 0, ("0",))
            elif partial.minor > 0:
                upper = _version(0, partial.minor + 1, 0, ("0",))
            elif partial.patch is None:
                upper = _version(0, 1, 0, ("0",))
            else:
                upper = _version(0, 0, partial.patch + 1, ("0",))

            add("<", upper)

    else:
        raise ValueError("invalid operator")

    return comparators, anchors, impossible


def _desugar_hyphen(left, right):
    comparators = []
    anchors = set()

    if left.major is not None:
        comparators.append((">=", _lower_from_partial(left)))
        anchor = _anchor_for(left)
        if anchor is not None:
            anchors.add(anchor)

    if right.major is not None:
        if right.minor is None:
            comparators.append(("<", _version(right.major + 1, 0, 0, ("0",))))
        elif right.patch is None:
            comparators.append(
                ("<", _version(right.major, right.minor + 1, 0, ("0",)))
            )
        else:
            comparators.append(("<=", _lower_from_partial(right)))
            anchor = _anchor_for(right)
            if anchor is not None:
                anchors.add(anchor)

    return comparators, anchors, False


def _parse_comparator_token(token):
    match = _OPERATOR_RE.match(token)
    if match is not None:
        operator = match.group(1)
        rest = match.group(2)
        if not rest:
            raise ValueError("missing version after operator")
    else:
        operator = ""
        rest = token

    return operator, _parse_partial(rest)


def _parse_set(text):
    tokens = text.split()
    comparators = []
    anchors = set()
    impossible = False
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token == "-":
            raise ValueError("unexpected hyphen")

        if token in _OPERATOR_ONLY:
            if index + 1 >= len(tokens) or tokens[index + 1] == "-":
                raise ValueError("missing version after operator")
            token = token + tokens[index + 1]
            index += 2

            operator, partial = _parse_comparator_token(token)
            found, found_anchors, bad = _desugar(operator, partial)
            comparators.extend(found)
            anchors.update(found_anchors)
            impossible = impossible or bad
            continue

        operator, partial = _parse_comparator_token(token)

        if (
            operator == ""
            and index + 1 < len(tokens)
            and tokens[index + 1] == "-"
        ):
            if index + 2 >= len(tokens):
                raise ValueError("incomplete hyphen range")

            right_token = tokens[index + 2]
            if right_token == "-" or right_token in _OPERATOR_ONLY:
                raise ValueError("invalid hyphen range")

            right_operator, right_partial = _parse_comparator_token(right_token)
            if right_operator != "":
                raise ValueError("invalid hyphen range")

            found, found_anchors, bad = _desugar_hyphen(partial, right_partial)
            comparators.extend(found)
            anchors.update(found_anchors)
            impossible = impossible or bad
            index += 3
            continue

        found, found_anchors, bad = _desugar(operator, partial)
        comparators.extend(found)
        anchors.update(found_anchors)
        impossible = impossible or bad
        index += 1

    return comparators, anchors, impossible


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("range must be a string")

    sets = []
    for set_text in range_.split("||"):
        sets.append(_parse_set(set_text))
    return sets


def _matches_comparator(version, operator, target):
    comparison = _compare_versions(version, target)

    if operator == "<":
        return comparison < 0
    if operator == "<=":
        return comparison <= 0
    if operator == ">":
        return comparison > 0
    if operator == ">=":
        return comparison >= 0
    if operator == "=":
        return comparison == 0

    raise ValueError("invalid comparator")


def _satisfies_parsed(version, parsed_range):
    for comparators, anchors, impossible in parsed_range:
        if impossible:
            continue

        if not all(
            _matches_comparator(version, operator, target)
            for operator, target in comparators
        ):
            continue

        if version.prerelease:
            version_key = (version.major, version.minor, version.patch)
            if version_key not in anchors:
                continue

        return True

    return False


def satisfies(version, range_):
    parsed_version = _parse_version(version)
    parsed_range = _parse_range(range_)
    return _satisfies_parsed(parsed_version, parsed_range)


def max_satisfying(versions, range_):
    parsed_range = _parse_range(range_)

    best = None
    best_version = None

    for item in versions:
        if not isinstance(item, str):
            continue

        try:
            candidate = _parse_version(item)
        except ValueError:
            continue

        if not _satisfies_parsed(candidate, parsed_range):
            continue

        if best_version is None or _compare_versions(candidate, best_version) > 0:
            best = item
            best_version = candidate

    return best
