"""npm-style version range matching. See TASK.md for the exact spec."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

_NUM = r"(?:0|[1-9][0-9]*)"
_IDENT = r"[0-9A-Za-z-]+"
_VERSION_RE = re.compile(
    rf"^({_NUM})\.({_NUM})\.({_NUM})"
    rf"(?:-({_IDENT}(?:\.{_IDENT})*))?"
    rf"(?:\+({_IDENT}(?:\.{_IDENT})*))?$"
)
_PARTIAL_NUM_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")

_OPERATORS = frozenset(("<", "<=", ">", ">=", "=", "~", "^"))
_ATTACHED_OPERATOR_RE = re.compile(r"^(<=|>=|<|>|=|~|\^)(.*)$")
_HYPHEN_RANGE_RE = re.compile(r"^\s*(\S+)\s+-\s+(\S+)\s*$")

_Prerelease = Tuple[Union[int, str], ...]


@dataclass(frozen=True)
class _Version:
    """A fully parsed semantic version."""

    major: int
    minor: int
    patch: int
    prerelease: _Prerelease = ()
    build: Tuple[str, ...] = ()


@dataclass(frozen=True)
class _Partial:
    """A possibly incomplete version used by X-ranges and ranges."""

    major: Optional[int]
    minor: Optional[int]
    patch: Optional[int]


@dataclass(frozen=True)
class _Comparator:
    """A single comparison against a concrete version."""

    op: str
    version: _Version
    counts_prerelease: bool = False


_NO_MATCH = _Comparator("none", _Version(0, 0, 0))


def _strip_version_marker(text: str) -> str:
    """Remove one optional leading ``v`` or ``=`` marker."""
    if text and text[0] in ("v", "="):
        return text[1:]
    return text


def _parse_version(value: object, *, allow_marker: bool = True) -> _Version:
    """Parse a complete version string or raise ``ValueError``."""
    if not isinstance(value, str):
        raise ValueError("version must be a string")

    text = value.strip()
    if not text:
        raise ValueError("empty version")

    if allow_marker:
        text = _strip_version_marker(text)
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid version: {value!r}")

    prerelease: List[Union[int, str]] = []
    if match.group(4) is not None:
        for identifier in match.group(4).split("."):
            if identifier.isdigit():
                if len(identifier) > 1 and identifier[0] == "0":
                    raise ValueError(f"invalid prerelease identifier: {identifier!r}")
                prerelease.append(int(identifier))
            else:
                prerelease.append(identifier)

    build = tuple(match.group(5).split(".")) if match.group(5) is not None else ()
    return _Version(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        tuple(prerelease),
        build,
    )


def _parse_partial(value: object, *, allow_marker: bool = True) -> _Partial:
    """Parse a partial version or X-range or raise ``ValueError``."""
    if not isinstance(value, str):
        raise ValueError("version must be a string")

    text = value.strip()
    if not text:
        raise ValueError("empty version")

    if allow_marker:
        text = _strip_version_marker(text)
    if not text:
        raise ValueError("empty version")
    if "-" in text or "+" in text:
        raise ValueError(f"invalid partial version: {value!r}")

    parts = text.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"invalid partial version: {value!r}")

    values: List[Optional[int]] = []
    wildcard_seen = False
    for part in parts:
        if part in ("*", "x", "X"):
            wildcard_seen = True
            values.append(None)
            continue
        if wildcard_seen:
            raise ValueError(f"invalid partial version: {value!r}")
        if _PARTIAL_NUM_RE.fullmatch(part) is None:
            raise ValueError(f"invalid partial version: {value!r}")
        values.append(int(part))

    while len(values) < 3:
        values.append(None)

    return _Partial(values[0], values[1], values[2])


def _parse_version_or_partial(value: object) -> Union[_Version, _Partial]:
    """Parse a complete version, falling back to a partial version.

    Range operands may carry a single leading ``v``, but a leading ``=`` is
    an operator and must already have been consumed by the range parser.
    """
    if not isinstance(value, str):
        raise ValueError("version must be a string")

    text = value.strip()
    if not text:
        raise ValueError("empty version")
    if text[0] == "=":
        raise ValueError(f"invalid version: {value!r}")
    if text[0] == "v":
        text = text[1:]
        if not text:
            raise ValueError(f"invalid version: {value!r}")

    try:
        return _parse_version(text, allow_marker=False)
    except ValueError:
        return _parse_partial(text, allow_marker=False)


def _compare_prerelease(left: _Prerelease, right: _Prerelease) -> int:
    """Compare prerelease identifier tuples."""
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1

    for left_identifier, right_identifier in zip(left, right):
        if left_identifier == right_identifier:
            continue
        if isinstance(left_identifier, int) and isinstance(right_identifier, int):
            return -1 if left_identifier < right_identifier else 1
        if isinstance(left_identifier, int):
            return -1
        if isinstance(right_identifier, int):
            return 1
        return -1 if left_identifier < right_identifier else 1

    if len(left) < len(right):
        return -1
    if len(left) > len(right):
        return 1
    return 0


def _compare_versions(left: _Version, right: _Version) -> int:
    """Compare two versions by SemVer precedence, ignoring build metadata."""
    for attribute in ("major", "minor", "patch"):
        left_value = getattr(left, attribute)
        right_value = getattr(right, attribute)
        if left_value != right_value:
            return -1 if left_value < right_value else 1
    return _compare_prerelease(left.prerelease, right.prerelease)


def _lower_bound(partial: _Partial) -> _Version:
    """Return the lowest complete version covered by a partial version."""
    return _Version(partial.major or 0, partial.minor or 0, partial.patch or 0)


def _next_version(partial: _Partial) -> _Version:
    """Return the version just after the range covered by a partial version."""
    if partial.minor is None:
        return _Version((partial.major or 0) + 1, 0, 0)
    if partial.patch is None:
        return _Version(partial.major or 0, partial.minor + 1, 0)
    return _Version(partial.major or 0, partial.minor, partial.patch + 1)


def _next_version_zero(partial: _Partial) -> _Version:
    """Return the exclusive upper bound used by partial versions."""
    next_version = _next_version(partial)
    return _Version(
        next_version.major,
        next_version.minor,
        next_version.patch,
        (0,),
    )


def _lower_bound_zero(partial: _Partial) -> _Version:
    """Return a partial version's lower bound with a ``-0`` prerelease."""
    lower = _lower_bound(partial)
    return _Version(lower.major, lower.minor, lower.patch, (0,))


def _plain_comparators(
    op: str, target: Union[_Version, _Partial]
) -> List[_Comparator]:
    """Desugar a plain comparator or X-range."""
    if isinstance(target, _Version):
        return [_Comparator(op or "=", target, bool(target.prerelease))]

    partial = target
    if partial.major is None:
        if op in (">", "<"):
            return [_NO_MATCH]
        return [_Comparator(">=", _Version(0, 0, 0))]

    if op in ("", "="):
        return [
            _Comparator(">=", _lower_bound(partial)),
            _Comparator("<", _next_version_zero(partial)),
        ]
    if op == ">":
        return [_Comparator(">=", _next_version(partial))]
    if op == ">=":
        return [_Comparator(">=", _lower_bound(partial))]
    if op == "<":
        return [_Comparator("<", _lower_bound_zero(partial))]
    if op == "<=":
        return [_Comparator("<", _next_version_zero(partial))]

    raise ValueError(f"invalid comparator operator: {op!r}")


def _tilde_comparators(target: Union[_Version, _Partial]) -> List[_Comparator]:
    """Desugar a tilde range."""
    if isinstance(target, _Version):
        upper = _Version(target.major, target.minor + 1, 0, (0,))
        return [
            _Comparator(">=", target, bool(target.prerelease)),
            _Comparator("<", upper),
        ]

    partial = target
    if partial.major is None:
        return [_Comparator(">=", _Version(0, 0, 0))]

    if partial.minor is None:
        upper = _Version(partial.major + 1, 0, 0, (0,))
    else:
        upper = _Version(partial.major, partial.minor + 1, 0, (0,))

    return [
        _Comparator(">=", _lower_bound(partial)),
        _Comparator("<", upper),
    ]


def _caret_comparators(target: Union[_Version, _Partial]) -> List[_Comparator]:
    """Desugar a caret range without changing the left-most non-zero part."""
    if isinstance(target, _Version):
        if target.major > 0:
            upper = _Version(target.major + 1, 0, 0, (0,))
        elif target.minor > 0:
            upper = _Version(0, target.minor + 1, 0, (0,))
        elif target.patch > 0:
            upper = _Version(0, 0, target.patch + 1, (0,))
        else:
            upper = _Version(0, 0, 1, (0,))
        return [
            _Comparator(">=", target, bool(target.prerelease)),
            _Comparator("<", upper),
        ]

    partial = target
    if partial.major is None:
        return [_Comparator(">=", _Version(0, 0, 0))]

    if partial.major > 0:
        upper = _Version(partial.major + 1, 0, 0, (0,))
    elif partial.minor is None:
        upper = _Version(1, 0, 0, (0,))
    elif partial.minor > 0:
        upper = _Version(0, partial.minor + 1, 0, (0,))
    elif partial.patch is None:
        upper = _Version(0, 1, 0, (0,))
    elif partial.patch > 0:
        upper = _Version(0, 0, partial.patch + 1, (0,))
    else:
        upper = _Version(0, 0, 1, (0,))

    return [
        _Comparator(">=", _lower_bound(partial)),
        _Comparator("<", upper),
    ]


def _parse_comparator(op: str, operand: str) -> List[_Comparator]:
    """Parse one comparator into concrete comparators."""
    target = _parse_version_or_partial(operand)
    if op == "~":
        return _tilde_comparators(target)
    if op == "^":
        return _caret_comparators(target)
    return _plain_comparators(op, target)


def _hyphen_comparators(left_text: str, right_text: str) -> List[_Comparator]:
    """Desugar a hyphen range into lower and upper comparators."""
    left = _parse_version_or_partial(left_text)
    right = _parse_version_or_partial(right_text)

    if isinstance(left, _Version):
        comparators = [_Comparator(">=", left, bool(left.prerelease))]
    elif left.major is None:
        comparators = [_Comparator(">=", _Version(0, 0, 0))]
    else:
        comparators = [_Comparator(">=", _lower_bound(left))]

    if isinstance(right, _Version):
        comparators.append(_Comparator("<=", right, bool(right.prerelease)))
    elif right.major is not None:
        comparators.append(_Comparator("<", _next_version_zero(right)))

    return comparators


def _parse_comparator_set(text: str) -> List[_Comparator]:
    """Parse one ``||``-separated comparator set."""
    text = text.strip()
    if not text:
        return []

    hyphen_match = _HYPHEN_RANGE_RE.fullmatch(text)
    if hyphen_match is not None:
        return _hyphen_comparators(hyphen_match.group(1), hyphen_match.group(2))

    tokens = text.split()
    comparators: List[_Comparator] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if token in _OPERATORS:
            if index + 1 >= len(tokens):
                raise ValueError(f"missing version after operator: {token!r}")
            comparators.extend(_parse_comparator(token, tokens[index + 1]))
            index += 2
            continue

        match = _ATTACHED_OPERATOR_RE.fullmatch(token)
        if match is not None:
            op = match.group(1)
            operand = match.group(2)
            if not operand:
                raise ValueError(f"missing version after operator: {op!r}")
            comparators.extend(_parse_comparator(op, operand))
        else:
            comparators.extend(_parse_comparator("", token))
        index += 1

    return comparators


def _parse_range(value: object) -> List[List[_Comparator]]:
    """Parse a complete range into comparator sets."""
    if not isinstance(value, str):
        raise ValueError("range must be a string")
    return [_parse_comparator_set(part) for part in value.split("||")]


def _same_core(left: _Version, right: _Version) -> bool:
    """Return whether two versions share MAJOR.MINOR.PATCH."""
    return (
        left.major == right.major
        and left.minor == right.minor
        and left.patch == right.patch
    )


def _comparator_matches(comparator: _Comparator, version: _Version) -> bool:
    """Return whether a version satisfies one comparator."""
    if comparator.op == "none":
        return False

    comparison = _compare_versions(version, comparator.version)
    if comparator.op == "<":
        return comparison < 0
    if comparator.op == "<=":
        return comparison <= 0
    if comparator.op == ">":
        return comparison > 0
    if comparator.op == ">=":
        return comparison >= 0
    if comparator.op == "=":
        return comparison == 0
    raise ValueError(f"invalid comparator operator: {comparator.op!r}")


def _set_satisfies(comparators: List[_Comparator], version: _Version) -> bool:
    """Return whether a version satisfies one comparator set."""
    for comparator in comparators:
        if not _comparator_matches(comparator, version):
            return False

    if version.prerelease:
        for comparator in comparators:
            if (
                comparator.counts_prerelease
                and _same_core(comparator.version, version)
            ):
                return True
        return False

    return True


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version satisfies an npm-style range.

    Args:
        version: The version string to test.
        range_: The range expression to test against.

    Returns:
        ``True`` if the version satisfies the range, otherwise ``False``.

    Raises:
        ValueError: If the version or the range is invalid.
    """
    parsed_version = _parse_version(version)
    parsed_range = _parse_range(range_)
    return any(_set_satisfies(comparators, parsed_version) for comparators in parsed_range)


def max_satisfying(versions: Sequence[str], range_: str) -> Optional[str]:
    """Return the highest version in ``versions`` satisfying a range.

    Invalid version strings are skipped. When two versions have equal
    precedence, the one appearing first in ``versions`` is returned.

    Args:
        versions: Candidate version strings.
        range_: The range expression to test against.

    Returns:
        The original string of the highest satisfying version, or ``None``.

    Raises:
        ValueError: If the range is invalid.
    """
    parsed_range = _parse_range(range_)
    best_text: Optional[str] = None
    best_version: Optional[_Version] = None

    for value in versions:
        try:
            candidate = _parse_version(value)
        except ValueError:
            continue

        if not any(
            _set_satisfies(comparators, candidate)
            for comparators in parsed_range
        ):
            continue

        if best_version is None or _compare_versions(candidate, best_version) > 0:
            best_text = value
            best_version = candidate

    return best_text
