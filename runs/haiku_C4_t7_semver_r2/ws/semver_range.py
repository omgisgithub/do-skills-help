"""npm-style version range matching. See TASK.md for the exact spec."""

from __future__ import annotations

import operator
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

_NUMBER = r"0|[1-9][0-9]*"
_PRERELEASE_IDENTIFIER = rf"(?:{_NUMBER}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_VERSION_RE = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})"
    rf"(?:-({_PRERELEASE_IDENTIFIER}(?:\.{_PRERELEASE_IDENTIFIER})*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
_NUMBER_RE = re.compile(_NUMBER)
_WILDCARDS = frozenset({"x", "X", "*"})
_RANGE_SIGNS = frozenset({"~", "^"})
# Longer operators come first so ``<=`` is not read as ``<`` followed by ``=``.
_OPERATORS = ("<=", ">=", "<", ">", "=")
_COMPARE = {
    "=": operator.eq,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


@dataclass(frozen=True)
class _Version:
    """A parsed version. Build metadata is dropped because it never affects ordering."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Operand:
    """A version or partial version as written in a comparator, without its operator.

    Attributes:
        numbers: The leading numeric parts that were written. Empty for a bare wildcard.
        version: The complete version, set only when all three parts were written.
    """

    numbers: tuple[int, ...]
    version: _Version | None = None

    def is_wildcard(self) -> bool:
        """Report whether this operand is a bare wildcard such as ``*``."""
        return not self.numbers

    def lower(self) -> _Version:
        """Return the lowest version this operand stands for."""
        if self.version is not None:
            return self.version
        return _Version(*_pad(self.numbers))

    def upper(self) -> _Version:
        """Return the first release past this partial operand, without a prerelease tag."""
        return _bump(self.numbers, len(self.numbers) - 1)

    def base(self) -> tuple[int, int, int] | None:
        """Return the MAJOR.MINOR.PATCH of a written prerelease, for the prerelease rule."""
        if self.version is None or not self.version.prerelease:
            return None
        return (self.version.major, self.version.minor, self.version.patch)


@dataclass(frozen=True)
class _Comparator:
    """One comparator with its bound already desugared, such as ``>=1.2.3``.

    Attributes:
        op: One of ``=``, ``<``, ``<=``, ``>``, ``>=``.
        bound: The version this comparator is measured against.
        prerelease_base: MAJOR.MINOR.PATCH of the version it was written from, when that
            version had a prerelease tag. Desugared ``-0`` bounds leave this as None.
    """

    op: str
    bound: _Version
    prerelease_base: tuple[int, int, int] | None = None


# Matches every version the prerelease rule allows: ``*``, ``>=*`` and friends.
_ANY = _Comparator(">=", _Version(0, 0, 0))
# No version sorts below ``0.0.0-0``, so this matches nothing: ``>*`` and ``<*``.
_NEVER = _Comparator("<", _Version(0, 0, 0, ("0",)))


def satisfies(version: str, range_: str) -> bool:
    """Report whether a version satisfies an npm-style range.

    Args:
        version: A version such as ``1.2.3``, ``v1.2.3-beta.1`` or ``1.2.3+build``.
        range_: One or more comparator sets separated by ``||``.

    Returns:
        True if the version satisfies at least one comparator set.

    Raises:
        ValueError: If the version or the range is invalid.
    """
    parsed = _parse_top_version(version)
    if parsed is None:
        raise ValueError(f"invalid version: {version!r}")
    return _range_matches(parsed, _parse_range(range_))


def max_satisfying(versions: Sequence[str], range_: str) -> str | None:
    """Return the highest version in ``versions`` that satisfies ``range_``.

    Args:
        versions: Candidate version strings. Invalid entries are skipped.
        range_: One or more comparator sets separated by ``||``.

    Returns:
        The winning entry exactly as it was given, or None if no entry satisfies the range.
        When several entries have equal precedence, the first one wins.

    Raises:
        ValueError: If ``range_`` is invalid.
    """
    comparator_sets = _parse_range(range_)
    best_text: str | None = None
    best: _Version | None = None
    for text in versions:
        parsed = _parse_top_version(text)
        if parsed is None or not _range_matches(parsed, comparator_sets):
            continue
        if best is None or _sort_key(parsed) > _sort_key(best):
            best_text, best = text, parsed
    return best_text


def _sort_key(version: _Version) -> tuple[int, int, int, int, tuple[tuple[int, int | str], ...]]:
    """Return a tuple whose ordering matches SemVer precedence.

    A release sorts above any prerelease of the same MAJOR.MINOR.PATCH. The fourth element
    is 1 for a release and 0 for a prerelease, so the prerelease identifiers only matter
    between two prereleases of the same version.
    """
    release = (version.major, version.minor, version.patch)
    if not version.prerelease:
        return (*release, 1, ())
    return (*release, 0, tuple(_identifier_key(part) for part in version.prerelease))


def _identifier_key(identifier: str) -> tuple[int, int | str]:
    """Order numeric identifiers as numbers, below alphanumeric ones compared as text."""
    if identifier.isdigit():
        return (0, int(identifier))
    return (1, identifier)


def _parse_top_version(text: str) -> _Version | None:
    """Parse a version passed to ``satisfies``, which may carry one leading ``v`` or ``=``."""
    return _parse_version(_strip_prefix(text.strip(), "v="))


def _parse_version(text: str) -> _Version | None:
    """Parse a complete ``MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`` string, or return None."""
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.group(1, 2, 3))
    prerelease = match.group(4)
    return _Version(major, minor, patch, tuple(prerelease.split(".")) if prerelease else ())


def _parse_partial(text: str) -> tuple[int, ...] | None:
    """Parse a partial version such as ``1``, ``1.2``, ``1.x`` or ``*``.

    Returns:
        The leading numbers that were written, which is empty for a bare wildcard. None when
        the text is not a partial version, including when a number follows a wildcard.
    """
    parts = text.split(".")
    if len(parts) > 3:
        return None
    numbers: list[int] = []
    for position, part in enumerate(parts):
        if part in _WILDCARDS:
            if any(later not in _WILDCARDS for later in parts[position + 1 :]):
                return None
            break
        if _NUMBER_RE.fullmatch(part) is None:
            return None
        numbers.append(int(part))
    return tuple(numbers)


def _parse_operand(text: str) -> _Operand | None:
    """Parse a version or partial version, which may carry a leading ``v``."""
    version_text = _strip_prefix(text, "v")
    version = _parse_version(version_text)
    if version is not None:
        return _Operand((version.major, version.minor, version.patch), version)
    numbers = _parse_partial(version_text)
    if numbers is None:
        return None
    return _Operand(numbers)


def _strip_prefix(text: str, prefixes: str) -> str:
    """Drop one leading character when it appears in ``prefixes``."""
    if text and text[0] in prefixes:
        return text[1:]
    return text


def _pad(numbers: Sequence[int]) -> tuple[int, int, int]:
    """Fill missing trailing parts with zeros."""
    major, minor, patch = (*numbers, 0, 0, 0)[:3]
    return major, minor, patch


def _bump(numbers: Sequence[int], index: int) -> _Version:
    """Increment the part at ``index`` and zero every part after it."""
    parts = list(_pad(numbers))
    parts[index] += 1
    for later in range(index + 1, 3):
        parts[later] = 0
    return _Version(parts[0], parts[1], parts[2])


def _zero_prerelease(version: _Version) -> _Version:
    """Return ``version-0``, the exclusive bound that keeps out prereleases of ``version``."""
    return replace(version, prerelease=("0",))


def _parse_range(range_: str) -> list[list[_Comparator]]:
    """Parse ``||``-separated comparator sets."""
    return [_parse_comparator_set(text) for text in range_.split("||")]


def _parse_comparator_set(text: str) -> list[_Comparator]:
    """Parse one comparator set, such as ``>=1.2.3 <2`` or ``1.2.3 - 2.3.4``."""
    tokens = text.split()
    if not tokens:
        return [_ANY]
    if "-" in tokens:
        return _hyphen_comparators(tokens)
    return _juxtaposed_comparators(tokens)


def _hyphen_comparators(tokens: list[str]) -> list[_Comparator]:
    """Desugar a hyphen range such as ``1.2 - 2.3.4``, whose surrounding spaces are required."""
    if len(tokens) != 3 or tokens[1] != "-":
        raise ValueError(f"invalid hyphen range: {' '.join(tokens)!r}")
    low = _parse_operand(tokens[0])
    high = _parse_operand(tokens[2])
    if low is None or high is None or low.is_wildcard() or high.is_wildcard():
        raise ValueError(f"invalid hyphen range: {' '.join(tokens)!r}")
    return [*_operator_comparators(">=", low), *_operator_comparators("<=", high)]


def _juxtaposed_comparators(tokens: list[str]) -> list[_Comparator]:
    """Desugar a list of comparators, joining a bare operator to the version after it."""
    comparators: list[_Comparator] = []
    index = 0
    while index < len(tokens):
        op, body = _split_operator(tokens[index])
        index += 1
        if not body:
            if index == len(tokens):
                raise ValueError(f"operator {op!r} is not followed by a version")
            body = tokens[index]
            index += 1
        comparators.extend(_comparators_for(op, body))
    return comparators


def _split_operator(token: str) -> tuple[str, str]:
    """Split a leading comparator operator from a token, returning ``""`` when there is none."""
    for op in _OPERATORS:
        if token.startswith(op):
            return op, token[len(op) :]
    return "", token


def _comparators_for(op: str, body: str) -> list[_Comparator]:
    """Desugar one comparator from its operator (possibly empty) and its version text."""
    is_range = not op and body[:1] in _RANGE_SIGNS
    operand = _parse_operand(body[1:] if is_range else body)
    if operand is None:
        raise ValueError(f"invalid comparator: {body!r}")
    if is_range:
        return _range_comparators(body[0], operand)
    return _operator_comparators(op, operand)


def _operator_comparators(op: str, operand: _Operand) -> list[_Comparator]:
    """Desugar an operator applied to a version, a partial version or a wildcard."""
    if operand.is_wildcard():
        return [_NEVER] if op in (">", "<") else [_ANY]
    if operand.version is not None:
        return [_Comparator(op or "=", operand.version, operand.base())]
    return _partial_comparators(op or "=", operand)


def _partial_comparators(op: str, operand: _Operand) -> list[_Comparator]:
    """Desugar an operator applied to a partial version such as ``1.2``."""
    if op == ">":
        return [_Comparator(">=", operand.upper())]
    if op == ">=":
        return [_at_least(operand)]
    if op == "<":
        return [_Comparator("<", _zero_prerelease(operand.lower()))]
    if op == "<=":
        return [_Comparator("<", _zero_prerelease(operand.upper()))]
    return [_at_least(operand), _Comparator("<", _zero_prerelease(operand.upper()))]


def _at_least(operand: _Operand) -> _Comparator:
    """Return the ``>=`` comparator for an operand's lowest version."""
    return _Comparator(">=", operand.lower(), operand.base())


def _range_comparators(sign: str, operand: _Operand) -> list[_Comparator]:
    """Desugar a tilde (``~``) or caret (``^``) range around an operand."""
    if operand.is_wildcard():
        return [_ANY]
    index = _tilde_index(operand.numbers) if sign == "~" else _caret_index(operand.numbers)
    return [_at_least(operand), _Comparator("<", _zero_prerelease(_bump(operand.numbers, index)))]


def _tilde_index(numbers: Sequence[int]) -> int:
    """Return the index a tilde range increments: minor, or major when only major is written."""
    return min(len(numbers), 2) - 1


def _caret_index(numbers: Sequence[int]) -> int:
    """Return the index of the left-most non-zero part, which a caret range must not change."""
    for index, number in enumerate(numbers):
        if number != 0:
            return index
    return len(numbers) - 1


def _range_matches(version: _Version, comparator_sets: Sequence[Sequence[_Comparator]]) -> bool:
    """Report whether a version satisfies at least one comparator set."""
    return any(_set_matches(version, comparators) for comparators in comparator_sets)


def _set_matches(version: _Version, comparators: Sequence[_Comparator]) -> bool:
    """Report whether a version satisfies every comparator in one set, under the prerelease rule."""
    if not all(_comparator_matches(version, comparator) for comparator in comparators):
        return False
    if not version.prerelease:
        return True
    release = (version.major, version.minor, version.patch)
    return any(comparator.prerelease_base == release for comparator in comparators)


def _comparator_matches(version: _Version, comparator: _Comparator) -> bool:
    """Report whether a version satisfies a single comparator."""
    compare = _COMPARE[comparator.op]
    return compare(_sort_key(version), _sort_key(comparator.bound))
