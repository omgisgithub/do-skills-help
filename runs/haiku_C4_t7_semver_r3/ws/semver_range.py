"""npm-style version range matching. See TASK.md for the exact spec."""

from __future__ import annotations

import operator
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

_NUMBER = r"0|[1-9][0-9]*"
_IDENTIFIER = r"[0-9A-Za-z-]+"
_DOTTED = rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*"
_FULL_VERSION_RE = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})(?:-({_DOTTED}))?(?:\+({_DOTTED}))?"
)
_PART_RE = re.compile(rf"(?:{_NUMBER})|[xX*]")
_WILDCARDS = frozenset({"x", "X", "*"})
_OPERATORS = ("<=", ">=", "<", ">", "=", "~", "^")
_OPERATOR_CHARS = "<>=~^-"
_ZERO = (0, 0, 0)
_COMPARE: dict[str, Callable[[object, object], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}


@dataclass(frozen=True)
class _Version:
    """A parsed version. Build metadata is dropped because it never affects ordering."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    @property
    def release(self) -> tuple[int, int, int]:
        """The MAJOR.MINOR.PATCH triple."""
        return (self.major, self.minor, self.patch)

    @property
    def precedence(self) -> tuple[tuple[int, int, int], int, tuple[tuple[int, int, str], ...]]:
        """A sort key implementing SemVer 2.0 precedence.

        A release without a prerelease sorts after any prerelease of it, so it gets the
        higher flag. The empty tuple never needs comparing against identifiers because the
        flag already decides.
        """
        if not self.prerelease:
            return (self.release, 1, ())
        return (self.release, 0, tuple(_identifier_key(part) for part in self.prerelease))


@dataclass(frozen=True)
class _Comparator:
    """One bound such as ``>=1.2.3``.

    ``is_anchor`` is set when the bound was written with a prerelease version. Only such
    bounds let prereleases of that release match a comparator set.
    """

    op: str
    version: _Version
    is_anchor: bool = False

    def matches(self, version: _Version) -> bool:
        """Return whether ``version`` satisfies this bound, ignoring the prerelease rule."""
        return _COMPARE[self.op](version.precedence, self.version.precedence)


@dataclass(frozen=True)
class _Operand:
    """A version as written after an operator. Wildcard numbers are ``None``."""

    parts: tuple[int | None, ...]
    prerelease: tuple[str, ...] = ()


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version satisfies an npm-style range.

    Args:
        version: A version such as ``1.2.3`` or ``v1.2.3-beta.1``.
        range_: A range such as ``^1.2.3 || >=2.0.0 <3``.

    Returns:
        True if the version satisfies at least one comparator set in the range.

    Raises:
        ValueError: If the version or the range is invalid.
    """
    parsed = _parse_version(version)
    return any(_set_matches(parsed, comparators) for comparators in _parse_range(range_))


def max_satisfying(versions: Sequence[str], range_: str) -> str | None:
    """Return the highest version in ``versions`` that satisfies ``range_``.

    Args:
        versions: Candidate version strings. Invalid entries are skipped.
        range_: A range such as ``~1.2.3``.

    Returns:
        The matching entry exactly as given, or None if nothing matches. When two entries
        have equal precedence, the one that comes first wins.

    Raises:
        ValueError: If the range is invalid.
    """
    sets = _parse_range(range_)
    matches: list[tuple[str, _Version]] = []
    for text in versions:
        try:
            candidate = _parse_version(text)
        except ValueError:
            continue
        if any(_set_matches(candidate, comparators) for comparators in sets):
            matches.append((text, candidate))
    if not matches:
        return None
    # max() returns the first maximal element, which gives the first-in-list tie-break.
    best_text, _ = max(matches, key=lambda match: match[1].precedence)
    return best_text


def _identifier_key(identifier: str) -> tuple[int, int, str]:
    """Order numeric identifiers first by value, then alphanumeric ones in ASCII order."""
    if identifier.isdigit():
        return (0, int(identifier), "")
    return (1, 0, identifier)


def _has_leading_zero(prerelease: str | None) -> bool:
    """Return whether any numeric prerelease identifier has a leading zero."""
    if prerelease is None:
        return False
    return any(
        len(part) > 1 and part[0] == "0" and part.isdigit() for part in prerelease.split(".")
    )


def _version_from_match(match: re.Match[str]) -> _Version:
    """Build a version from a full-version regex match."""
    major, minor, patch = (int(part) for part in match.group(1, 2, 3))
    prerelease = match.group(4)
    return _Version(major, minor, patch, tuple(prerelease.split(".")) if prerelease else ())


def _parse_version(text: str) -> _Version:
    """Parse a standalone version, allowing one leading ``v`` or ``=``.

    Raises:
        ValueError: If the text is not a valid version.
    """
    stripped = text.strip()
    if stripped[:1] in ("v", "="):
        stripped = stripped[1:]
    match = _FULL_VERSION_RE.fullmatch(stripped)
    if match is None or _has_leading_zero(match.group(4)):
        raise ValueError(f"invalid version: {text!r}")
    return _version_from_match(match)


def _parse_operand(text: str) -> _Operand:
    """Parse the version after an operator. Allows X-ranges and one leading ``v``.

    Raises:
        ValueError: If the text is not a valid full or partial version.
    """
    body = text[1:] if text.startswith("v") else text
    match = _FULL_VERSION_RE.fullmatch(body)
    if match is not None:
        if _has_leading_zero(match.group(4)):
            raise ValueError(f"invalid prerelease: {text!r}")
        version = _version_from_match(match)
        return _Operand((version.major, version.minor, version.patch), version.prerelease)
    return _parse_partial(body)


def _parse_partial(body: str) -> _Operand:
    """Parse ``1``, ``1.2``, ``1.x``, ``*`` and similar. Partial versions carry no prerelease.

    Raises:
        ValueError: If the text is not a valid partial version.
    """
    pieces = body.split(".")
    if len(pieces) > 3 or not all(_PART_RE.fullmatch(piece) for piece in pieces):
        raise ValueError(f"invalid version: {body!r}")
    parts: list[int | None] = [None if piece in _WILDCARDS else int(piece) for piece in pieces]
    first_wildcard = parts.index(None) if None in parts else len(parts)
    # Wildcards must trail, so "1.x.3" is rejected rather than read as "1.x".
    if any(part is not None for part in parts[first_wildcard:]):
        raise ValueError(f"invalid version: {body!r}")
    return _Operand(tuple(parts))


def _filled(numbers: Sequence[int], prerelease: tuple[str, ...] = ()) -> _Version:
    """Pad the given numbers with zeros, e.g. ``[1, 2]`` becomes ``1.2.0``."""
    major, minor, patch = (list(numbers) + [0, 0, 0])[:3]
    return _Version(major, minor, patch, prerelease)


def _zero(version: _Version) -> _Version:
    """Return the ``-0`` floor of a release, the lowest possible prerelease of it."""
    return replace(version, prerelease=("0",))


def _ceiling(numbers: Sequence[int]) -> _Version:
    """Return the exclusive upper bound for ``~`` and X-ranges, e.g. ``1.2`` gives ``1.3.0-0``."""
    lower = _filled(numbers)
    if len(numbers) == 1:
        return _zero(_Version(lower.major + 1, 0, 0))
    return _zero(_Version(lower.major, lower.minor + 1, 0))


def _caret_ceiling(numbers: Sequence[int]) -> _Version:
    """Return the exclusive upper bound for ``^``, which pins the left-most non-zero part."""
    lower = _filled(numbers)
    if lower.major > 0 or len(numbers) == 1:
        return _zero(_Version(lower.major + 1, 0, 0))
    if lower.minor > 0 or len(numbers) == 2:
        return _zero(_Version(0, lower.minor + 1, 0))
    return _zero(_Version(0, 0, lower.patch + 1))


def _is_wildcard(operand: _Operand) -> bool:
    """Return whether the operand is a bare ``*``, ``x`` or ``X``."""
    return all(part is None for part in operand.parts)


def _wildcard_comparators(op: str) -> list[_Comparator]:
    """Desugar an operator applied to a bare wildcard.

    Raises:
        ValueError: If the operator does not accept a wildcard.
    """
    if op in ("", "=", ">=", "<="):
        return [_Comparator(">=", _Version(*_ZERO))]
    if op in (">", "<"):
        return [_Comparator("<", _zero(_Version(*_ZERO)))]
    raise ValueError(f"operator {op!r} does not accept a wildcard")


def _comparators_for(op: str, operand: _Operand) -> list[_Comparator]:
    """Desugar one operator and operand into concrete bounds.

    Raises:
        ValueError: If the operator does not accept this operand.
    """
    if _is_wildcard(operand):
        return _wildcard_comparators(op)
    numbers = [part for part in operand.parts if part is not None]
    is_full = len(numbers) == 3
    lower = _filled(numbers, operand.prerelease)
    is_anchor = bool(operand.prerelease)
    if op in ("", "="):
        if is_full:
            return [_Comparator("=", lower, is_anchor)]
        return [_Comparator(">=", lower), _Comparator("<", _ceiling(numbers))]
    if op == ">=":
        return [_Comparator(">=", lower, is_anchor)]
    if op == "<":
        if is_full:
            return [_Comparator("<", lower, is_anchor)]
        # Partial "<1.2" means "below 1.2.0-0", so prereleases of 1.2.0 stay excluded.
        return [_Comparator("<", _zero(lower))]
    if op == "<=":
        if is_full:
            return [_Comparator("<=", lower, is_anchor)]
        return [_Comparator("<", _ceiling(numbers))]
    if op == ">":
        if is_full:
            return [_Comparator(">", lower, is_anchor)]
        # Partial ">1.2" means ">=1.3.0", with no prerelease floor.
        return [_Comparator(">=", replace(_ceiling(numbers), prerelease=()))]
    if op == "~":
        return [_Comparator(">=", lower, is_anchor), _Comparator("<", _ceiling(numbers))]
    if op == "^":
        return [_Comparator(">=", lower, is_anchor), _Comparator("<", _caret_ceiling(numbers))]
    raise ValueError(f"unknown operator {op!r}")


def _parse_comparator(text: str) -> list[_Comparator]:
    """Parse one comparator token such as ``>=1.2`` or ``~1.2.3``.

    Raises:
        ValueError: If the comparator is invalid.
    """
    op = next((candidate for candidate in _OPERATORS if text.startswith(candidate)), "")
    try:
        return _comparators_for(op, _parse_operand(text[len(op) :]))
    except ValueError as exc:
        raise ValueError(f"invalid comparator: {text!r}") from exc


def _hyphen_comparators(left: str, right: str) -> list[_Comparator]:
    """Desugar a hyphen range such as ``1.2.3 - 2.3``.

    Raises:
        ValueError: If either side is not a bare version.
    """
    try:
        low = _parse_operand(left)
        high = _parse_operand(right)
    except ValueError as exc:
        raise ValueError(f"invalid hyphen range: {left!r} - {right!r}") from exc
    # A wildcard on the right side means "no upper bound", not ">=0.0.0".
    upper = [] if _is_wildcard(high) else _comparators_for("<=", high)
    return _comparators_for(">=", low) + upper


def _parse_set(text: str) -> list[_Comparator]:
    """Parse a whitespace-separated comparator set. An empty set matches any version.

    Raises:
        ValueError: If any comparator in the set is invalid.
    """
    tokens = text.split()
    comparators: list[_Comparator] = []
    index = 0
    while index < len(tokens):
        if index + 1 < len(tokens) and tokens[index + 1] == "-":
            if index + 2 >= len(tokens):
                raise ValueError(f"hyphen range is missing its upper bound: {text!r}")
            comparators.extend(_hyphen_comparators(tokens[index], tokens[index + 2]))
            index += 3
            continue
        token = tokens[index]
        index += 1
        if token in _OPERATORS:
            # An operator may be followed by spaces, so "1.2.3 >= 1" is read as ">=1".
            if index >= len(tokens) or tokens[index][0] in _OPERATOR_CHARS:
                raise ValueError(f"operator {token!r} is not followed by a version: {text!r}")
            token += tokens[index]
            index += 1
        comparators.extend(_parse_comparator(token))
    return comparators


def _parse_range(range_: str) -> list[list[_Comparator]]:
    """Parse a range into its ``||``-separated comparator sets.

    Raises:
        ValueError: If any set in the range is invalid.
    """
    return [_parse_set(text) for text in range_.split("||")]


def _set_matches(version: _Version, comparators: Sequence[_Comparator]) -> bool:
    """Return whether a version satisfies one comparator set, including the prerelease rule."""
    if not all(comparator.matches(version) for comparator in comparators):
        return False
    if not version.prerelease:
        return True
    return any(
        comparator.is_anchor and comparator.version.release == version.release
        for comparator in comparators
    )
