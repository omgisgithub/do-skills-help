"""npm-style version range matching. See TASK.md for the exact spec."""

import re
from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Sequence, Set, Tuple

_NUMERIC_RE = re.compile(r"(?:0|[1-9][0-9]*)")
_IDENTIFIER_RE = re.compile(r"[0-9A-Za-z-]+")

# Operators, longest first so that ``<=`` is preferred over ``<``.
_OPERATORS = ("<=", ">=", "<", ">", "=", "~", "^")

_WILDCARDS = frozenset(("*", "x", "X"))

_Core = Tuple[int, int, int]


@dataclass(frozen=True)
class _Version:
    """A fully specified semantic version."""

    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @property
    def core(self) -> _Core:
        """Return the numeric major/minor/patch tuple."""
        return (self.major, self.minor, self.patch)


@dataclass(frozen=True)
class _PartialVersion:
    """A version operand from a range, which may have wildcard components."""

    major: Optional[int]
    minor: Optional[int]
    patch: Optional[int]
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()


@dataclass(frozen=True)
class _ComparatorSet:
    """One whitespace-separated comparator set from a range."""

    comparators: Tuple[Tuple[str, _Version], ...]
    prerelease_cores: FrozenSet[_Core]


def _invalid(message: str) -> ValueError:
    return ValueError(message)


def _parse_number(text: str) -> int:
    """Parse a non-negative integer without leading zeros."""
    if not _NUMERIC_RE.fullmatch(text):
        raise _invalid("invalid numeric version component: {0!r}".format(text))
    return int(text)


def _parse_identifiers(text: str, *, prerelease: bool) -> Tuple[str, ...]:
    """Parse dot-separated prerelease or build identifiers."""
    if not text:
        raise _invalid("empty identifier list")

    identifiers: List[str] = []
    for identifier in text.split("."):
        if not identifier or not _IDENTIFIER_RE.fullmatch(identifier):
            raise _invalid("invalid version identifier: {0!r}".format(identifier))
        if (
            prerelease
            and identifier.isdigit()
            and len(identifier) > 1
            and identifier[0] == "0"
        ):
            raise _invalid(
                "numeric prerelease identifier has a leading zero: {0!r}".format(
                    identifier
                )
            )
        identifiers.append(identifier)
    return tuple(identifiers)


def _split_version_text(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Split version text into core, prerelease, and build parts."""
    core_with_prerelease, plus, build = text.partition("+")
    if plus and not build:
        raise _invalid("empty build metadata")

    core, minus, prerelease = core_with_prerelease.partition("-")
    if minus and not prerelease:
        raise _invalid("empty prerelease")

    return core, (prerelease if minus else None), (build if plus else None)


def _parse_version(text: str) -> _Version:
    """Parse and validate a complete version string."""
    if not isinstance(text, str):
        raise _invalid("version must be a string")

    value = text.strip()
    if value[:1] in ("v", "="):
        value = value[1:]
    if not value:
        raise _invalid("empty version")

    core, prerelease, build = _split_version_text(value)
    core_parts = core.split(".")
    if len(core_parts) != 3:
        raise _invalid("version must have MAJOR.MINOR.PATCH: {0!r}".format(text))

    major = _parse_number(core_parts[0])
    minor = _parse_number(core_parts[1])
    patch = _parse_number(core_parts[2])

    parsed_prerelease = (
        _parse_identifiers(prerelease, prerelease=True)
        if prerelease is not None
        else ()
    )
    parsed_build = (
        _parse_identifiers(build, prerelease=False) if build is not None else ()
    )

    return _Version(major, minor, patch, parsed_prerelease, parsed_build)


def _parse_range_operand(text: str) -> _PartialVersion:
    """Parse a range operand, allowing partial and wildcard components."""
    value = text.strip()
    if value.startswith("v"):
        value = value[1:]
    if not value:
        raise _invalid("empty version in range")

    core, prerelease, build = _split_version_text(value)
    core_parts = core.split(".")
    if not 1 <= len(core_parts) <= 3:
        raise _invalid("invalid version in range: {0!r}".format(text))

    components: List[Optional[int]] = []
    wildcard_seen = False
    for part in core_parts:
        if part in _WILDCARDS:
            wildcard_seen = True
            components.append(None)
        else:
            if wildcard_seen:
                raise _invalid(
                    "numeric component after wildcard in range: {0!r}".format(text)
                )
            components.append(_parse_number(part))

    if components[0] is None and len(components) > 1:
        raise _invalid(
            "wildcard must be alone or follow a numeric component: {0!r}".format(text)
        )

    while len(components) < 3:
        components.append(None)

    if (prerelease is not None or build is not None) and any(
        component is None for component in components
    ):
        raise _invalid(
            "partial versions cannot have prerelease or build: {0!r}".format(text)
        )

    parsed_prerelease = (
        _parse_identifiers(prerelease, prerelease=True)
        if prerelease is not None
        else ()
    )
    parsed_build = (
        _parse_identifiers(build, prerelease=False) if build is not None else ()
    )

    return _PartialVersion(
        components[0],
        components[1],
        components[2],
        parsed_prerelease,
        parsed_build,
    )


def _compare_identifiers(left: str, right: str) -> int:
    """Compare two prerelease identifiers according to SemVer 2.0."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()

    if left_numeric and right_numeric:
        left_value = int(left)
        right_value = int(right)
        return (left_value > right_value) - (left_value < right_value)
    if left_numeric:
        return -1
    if right_numeric:
        return 1
    return (left > right) - (left < right)


def _compare_versions(left: _Version, right: _Version) -> int:
    """Compare two versions, ignoring build metadata."""
    if left.core != right.core:
        return (left.core > right.core) - (left.core < right.core)

    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1

    for left_identifier, right_identifier in zip(
        left.prerelease, right.prerelease
    ):
        result = _compare_identifiers(left_identifier, right_identifier)
        if result:
            return result

    return (len(left.prerelease) > len(right.prerelease)) - (
        len(left.prerelease) < len(right.prerelease)
    )


def _zero_upper(major: int, minor: int, patch: int) -> _Version:
    """Build the exclusive ``-0`` upper bound used by desugaring."""
    return _Version(major, minor, patch, ("0",))


def _release_version(partial: _PartialVersion) -> _Version:
    """Return the partial version with missing components filled with zero."""
    return _Version(
        int(partial.major),
        partial.minor if partial.minor is not None else 0,
        partial.patch if partial.patch is not None else 0,
        partial.prerelease,
        partial.build,
    )


def _add_comparator(
    comparators: List[Tuple[str, _Version]],
    prerelease_cores: Set[_Core],
    operator: str,
    version: _Version,
    written_with_prerelease: bool = False,
) -> None:
    """Append a comparator and record an explicitly written prerelease."""
    comparators.append((operator, version))
    if written_with_prerelease and version.prerelease:
        prerelease_cores.add(version.core)


def _comparators_for(
    operator: str, partial: _PartialVersion
) -> _ComparatorSet:
    """Desugar one comparator (possibly partial) into primitive comparisons."""
    comparators: List[Tuple[str, _Version]] = []
    prerelease_cores: Set[_Core] = set()

    all_wildcard = partial.major is None
    if all_wildcard:
        if operator in (">", "<"):
            comparators.append(("<", _zero_upper(0, 0, 0)))
        elif operator in ("", ">=", "<="):
            comparators.append((">=", _Version(0, 0, 0)))
        else:
            raise _invalid(
                "operator {0!r} cannot be used with a wildcard".format(operator)
            )
        return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))

    major = int(partial.major)

    if operator == "~":
        lower = _release_version(partial)
        _add_comparator(
            comparators,
            prerelease_cores,
            ">=",
            lower,
            bool(partial.prerelease),
        )
        if partial.minor is None:
            upper = _zero_upper(major + 1, 0, 0)
        else:
            upper = _zero_upper(major, int(partial.minor) + 1, 0)
        comparators.append(("<", upper))
        return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))

    if operator == "^":
        lower = _release_version(partial)
        _add_comparator(
            comparators,
            prerelease_cores,
            ">=",
            lower,
            bool(partial.prerelease),
        )
        minor = partial.minor
        patch = partial.patch
        if major > 0:
            upper = _zero_upper(major + 1, 0, 0)
        elif minor is None:
            upper = _zero_upper(1, 0, 0)
        elif minor > 0:
            upper = _zero_upper(0, minor + 1, 0)
        elif patch is None:
            upper = _zero_upper(0, 1, 0)
        else:
            upper = _zero_upper(0, 0, patch + 1)
        comparators.append(("<", upper))
        return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))

    if operator in ("", "="):
        if partial.minor is None:
            lower = _Version(major, 0, 0)
            _add_comparator(comparators, prerelease_cores, ">=", lower)
            comparators.append(("<", _zero_upper(major + 1, 0, 0)))
        elif partial.patch is None:
            lower = _Version(major, int(partial.minor), 0)
            _add_comparator(comparators, prerelease_cores, ">=", lower)
            comparators.append(
                ("<", _zero_upper(major, int(partial.minor) + 1, 0))
            )
        else:
            version = _release_version(partial)
            _add_comparator(
                comparators,
                prerelease_cores,
                "=",
                version,
                bool(partial.prerelease),
            )
        return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))

    if operator == ">":
        if partial.minor is None:
            lower = _Version(major + 1, 0, 0)
            _add_comparator(comparators, prerelease_cores, ">=", lower)
        elif partial.patch is None:
            lower = _Version(major, int(partial.minor) + 1, 0)
            _add_comparator(comparators, prerelease_cores, ">=", lower)
        else:
            version = _release_version(partial)
            _add_comparator(
                comparators,
                prerelease_cores,
                ">",
                version,
                bool(partial.prerelease),
            )
        return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))

    if operator == ">=":
        if partial.minor is None:
            lower = _Version(major, 0, 0)
        elif partial.patch is None:
            lower = _Version(major, int(partial.minor), 0)
        else:
            lower = _release_version(partial)
        _add_comparator(
            comparators,
            prerelease_cores,
            ">=",
            lower,
            bool(partial.prerelease),
        )
        return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))

    if operator == "<":
        if partial.minor is None:
            upper = _zero_upper(major, 0, 0)
        elif partial.patch is None:
            upper = _zero_upper(major, int(partial.minor), 0)
        else:
            version = _release_version(partial)
            _add_comparator(
                comparators,
                prerelease_cores,
                "<",
                version,
                bool(partial.prerelease),
            )
            return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))
        comparators.append(("<", upper))
        return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))

    if operator == "<=":
        if partial.minor is None:
            upper = _zero_upper(major + 1, 0, 0)
        elif partial.patch is None:
            upper = _zero_upper(major, int(partial.minor) + 1, 0)
        else:
            version = _release_version(partial)
            _add_comparator(
                comparators,
                prerelease_cores,
                "<=",
                version,
                bool(partial.prerelease),
            )
            return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))
        comparators.append(("<", upper))
        return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))

    raise _invalid("unknown comparator operator: {0!r}".format(operator))


def _hyphen_comparators(left: str, right: str) -> _ComparatorSet:
    """Desugar a hyphen range into lower and upper primitive comparisons."""
    left_partial = _parse_range_operand(left)
    right_partial = _parse_range_operand(right)

    comparators: List[Tuple[str, _Version]] = []
    prerelease_cores: Set[_Core] = set()

    if left_partial.major is None:
        lower = _Version(0, 0, 0)
    else:
        lower = _release_version(left_partial)
    _add_comparator(
        comparators,
        prerelease_cores,
        ">=",
        lower,
        bool(left_partial.prerelease),
    )

    if right_partial.major is not None:
        major = int(right_partial.major)
        if right_partial.minor is None:
            comparators.append(("<", _zero_upper(major + 1, 0, 0)))
        elif right_partial.patch is None:
            comparators.append(
                ("<", _zero_upper(major, int(right_partial.minor) + 1, 0))
            )
        else:
            upper = _release_version(right_partial)
            _add_comparator(
                comparators,
                prerelease_cores,
                "<=",
                upper,
                bool(right_partial.prerelease),
            )

    return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))


def _split_operator(token: str) -> Tuple[str, str]:
    """Split a leading comparator operator from a token."""
    for operator in _OPERATORS:
        if token.startswith(operator):
            return operator, token[len(operator) :]
    return "", token


def _parse_comparator_set(text: str) -> _ComparatorSet:
    """Parse and desugar one whitespace-separated comparator set."""
    tokens = text.split()
    comparators: List[Tuple[str, _Version]] = []
    prerelease_cores: Set[_Core] = set()

    index = 0
    while index < len(tokens):
        token = tokens[index]

        operator, rest = _split_operator(token)
        if operator and not rest:
            if index + 1 >= len(tokens):
                raise _invalid(
                    "operator {0!r} is missing a version".format(operator)
                )
            operand = tokens[index + 1]
            if operand == "-":
                raise _invalid("operator cannot be followed by a hyphen")
            parsed = _comparators_for(
                operator, _parse_range_operand(operand)
            )
            comparators.extend(parsed.comparators)
            prerelease_cores.update(parsed.prerelease_cores)
            index += 2
            continue

        if operator:
            parsed = _comparators_for(operator, _parse_range_operand(rest))
            comparators.extend(parsed.comparators)
            prerelease_cores.update(parsed.prerelease_cores)
            index += 1
            continue

        if index + 1 < len(tokens) and tokens[index + 1] == "-":
            if index + 2 >= len(tokens):
                raise _invalid("hyphen range is missing its right-hand version")
            parsed = _hyphen_comparators(token, tokens[index + 2])
            comparators.extend(parsed.comparators)
            prerelease_cores.update(parsed.prerelease_cores)
            index += 3
            continue

        parsed = _comparators_for("", _parse_range_operand(token))
        comparators.extend(parsed.comparators)
        prerelease_cores.update(parsed.prerelease_cores)
        index += 1

    return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))


def _parse_range(text: str) -> List[_ComparatorSet]:
    """Parse and validate a complete range expression."""
    if not isinstance(text, str):
        raise _invalid("range must be a string")

    return [
        _parse_comparator_set(part)
        for part in text.split("||")
    ]


def _comparator_matches(
    version: _Version, operator: str, bound: _Version
) -> bool:
    """Return whether one primitive comparison holds."""
    result = _compare_versions(version, bound)
    if operator == "<":
        return result < 0
    if operator == "<=":
        return result <= 0
    if operator == ">":
        return result > 0
    if operator == ">=":
        return result >= 0
    if operator == "=":
        return result == 0
    raise _invalid("unknown comparator operator: {0!r}".format(operator))


def _set_matches(version: _Version, comparator_set: _ComparatorSet) -> bool:
    """Return whether a version satisfies one comparator set."""
    for operator, bound in comparator_set.comparators:
        if not _comparator_matches(version, operator, bound):
            return False

    if version.prerelease:
        return version.core in comparator_set.prerelease_cores

    return True


def _matches(version: _Version, comparator_sets: Sequence[_ComparatorSet]) -> bool:
    """Return whether a version satisfies at least one comparator set."""
    return any(_set_matches(version, comparator_set) for comparator_set in comparator_sets)


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version satisfies a range.

    Args:
        version: The version string to test.
        range_: The range expression to test against.

    Returns:
        True if the version satisfies the range, otherwise False.

    Raises:
        ValueError: If the version or the range is invalid.
    """
    parsed_version = _parse_version(version)
    comparator_sets = _parse_range(range_)
    return _matches(parsed_version, comparator_sets)


def max_satisfying(versions: list, range_: str) -> Optional[str]:
    """Return the highest version from a list that satisfies a range.

    Invalid entries in ``versions`` are skipped. Versions with equal
    precedence (for example, versions differing only in build metadata)
    keep the one that appears first in the list.

    Args:
        versions: Candidate version strings.
        range_: The range expression to test against.

    Returns:
        The original version string with the highest precedence, or None if
        no valid candidate satisfies the range.

    Raises:
        ValueError: If the range is invalid.
    """
    comparator_sets = _parse_range(range_)

    best_text: Optional[str] = None
    best_version: Optional[_Version] = None

    for candidate in versions:
        if not isinstance(candidate, str):
            continue
        try:
            parsed = _parse_version(candidate)
        except ValueError:
            continue

        if not _matches(parsed, comparator_sets):
            continue

        if best_version is None or _compare_versions(parsed, best_version) > 0:
            best_text = candidate
            best_version = parsed

    return best_text
