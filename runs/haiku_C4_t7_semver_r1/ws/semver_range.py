"""npm-style version range matching. See TASK.md for the exact spec."""

from __future__ import annotations

import operator
import re
from collections.abc import Iterable
from dataclasses import dataclass

_NUMBER = r"0|[1-9][0-9]*"
_IDENTIFIER = r"[0-9A-Za-z-]+"
_DOTTED = rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*"
_VERSION_RE = re.compile(rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})(?:-({_DOTTED}))?(?:\+{_DOTTED})?")
_PART_RE = re.compile(rf"\*|[xX]|{_NUMBER}")
_WILDCARDS = frozenset({"*", "x", "X"})
_COMPARATOR_RE = re.compile(r"(<=|>=|<|>|=|~|\^)?(.+)")
_OPERATOR_ONLY = frozenset({"<", "<=", ">", ">=", "=", "~", "^"})
_COMPARE = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "=": operator.eq,
}


@dataclass(frozen=True)
class _Version:
    """A concrete version. Build metadata is dropped because it never affects matching."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    @property
    def release(self) -> tuple[int, int, int]:
        """Return the MAJOR.MINOR.PATCH triple."""
        return (self.major, self.minor, self.patch)

    def sort_key(self) -> tuple[object, ...]:
        """Return a key whose ordering matches SemVer precedence."""
        if not self.prerelease:
            return (*self.release, 1)
        return (*self.release, 0, tuple(_identifier_key(part) for part in self.prerelease))


@dataclass(frozen=True)
class _Partial:
    """A version with wildcards or omitted parts; ``None`` marks a missing level."""

    major: int | None
    minor: int | None
    patch: int | None


@dataclass(frozen=True)
class _Comparator:
    """One bound such as ``>=1.2.3``.

    ``anchor`` is true when the user wrote a prerelease version here. Only such bounds let a
    prerelease candidate of the same MAJOR.MINOR.PATCH match the set.
    """

    op: str
    version: _Version
    anchor: bool = False

    def matches(self, candidate: _Version) -> bool:
        """Return whether ``candidate`` satisfies this bound."""
        return _COMPARE[self.op](candidate.sort_key(), self.version.sort_key())


_NOTHING = _Comparator("<", _Version(0, 0, 0, ("0",)))


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version satisfies an npm-style range.

    Args:
        version: A concrete version such as ``1.2.3-beta.1+build``.
        range_: A range such as ``^1.2.3 || >=2.0.0``.

    Returns:
        True if at least one comparator set in the range matches the version.

    Raises:
        ValueError: If the version or the range is invalid.
    """
    candidate = _parse_version(version)
    if candidate is None:
        raise ValueError(f"invalid version: {version!r}")
    return _matches_any(_parse_range(range_), candidate)


def max_satisfying(versions: Iterable[object], range_: str) -> object | None:
    """Return the highest version in ``versions`` that satisfies the range.

    Args:
        versions: Candidate version strings. Invalid entries are skipped.
        range_: A range such as ``~1.2``.

    Returns:
        The winning entry exactly as given, or None if nothing matches. Among entries of equal
        precedence, the first one wins.

    Raises:
        ValueError: If the range is invalid.
    """
    sets = _parse_range(range_)
    best: object | None = None
    best_key: tuple[object, ...] | None = None
    for text in versions:
        candidate = _parse_version(text) if isinstance(text, str) else None
        if candidate is None or not _matches_any(sets, candidate):
            continue
        key = candidate.sort_key()
        if best_key is None or key > best_key:
            best, best_key = text, key
    return best


def _identifier_key(part: str) -> tuple[int, int, str]:
    """Order numeric prerelease identifiers as numbers, below alphanumeric ones."""
    if part.isdigit():
        return (0, int(part), "")
    return (1, 0, part)


def _has_leading_zero_number(identifiers: Iterable[str]) -> bool:
    """Return whether any identifier is a number with a leading zero."""
    return any(part.isdigit() and part.startswith("0") and len(part) > 1 for part in identifiers)


def _parse_version_body(text: str) -> _Version | None:
    """Parse a version with no prefix, or return None if it is not one."""
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        return None
    major, minor, patch, prerelease_text = match.groups()
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    if _has_leading_zero_number(prerelease):
        return None
    return _Version(int(major), int(minor), int(patch), prerelease)


def _parse_version(text: str) -> _Version | None:
    """Parse a concrete version, allowing one leading ``v`` or ``=``."""
    stripped = text.strip()
    body = stripped[1:] if stripped[:1] in ("v", "=") else stripped
    return _parse_version_body(body)


def _parse_partial(text: str) -> _Partial | None:
    """Parse a partial version such as ``1.x`` or ``1.2``, or return None if it is not one."""
    parts = text.split(".")
    if len(parts) > 3 or not all(_PART_RE.fullmatch(part) for part in parts):
        return None
    padded = [*parts, *["*"] * (3 - len(parts))]
    values = [None if part in _WILDCARDS else int(part) for part in padded]
    if None in values and any(value is not None for value in values[values.index(None) :]):
        return None
    return _Partial(*values)


def _parse_operand(text: str) -> _Version | _Partial:
    """Parse the version after an operator, allowing one leading ``v``."""
    body = text[1:] if text.startswith("v") else text
    version = _parse_version_body(body)
    if version is not None:
        return version
    partial = _parse_partial(body)
    if partial is None:
        raise ValueError(f"invalid version in range: {text!r}")
    return partial


def _lower(partial: _Partial) -> _Version:
    """Return the lowest version covered by a partial, with missing parts as zero."""
    return _Version(partial.major or 0, partial.minor or 0, partial.patch or 0)


def _upper(partial: _Partial) -> _Version:
    """Return the exclusive ceiling of a partial's range, e.g. ``1.2`` gives ``1.3.0``."""
    if partial.minor is None:
        return _Version((partial.major or 0) + 1, 0, 0)
    return _Version(partial.major or 0, partial.minor + 1, 0)


def _caret_ceiling(major: int, minor: int | None, patch: int | None) -> _Version:
    """Return the exclusive ceiling for ``^`` by pinning the left-most non-zero part."""
    if major > 0:
        return _Version(major + 1, 0, 0)
    if minor is None:
        return _Version(1, 0, 0)
    if minor > 0 or patch is None:
        return _Version(0, minor + 1, 0)
    return _Version(0, 0, patch + 1)


def _ceiling_bound(version: _Version) -> _Comparator:
    """Return ``<version-0``, the bound that keeps out prereleases of ``version``."""
    return _Comparator("<", _Version(version.major, version.minor, version.patch, ("0",)))


def _expand(op: str, operand: _Version | _Partial) -> list[_Comparator]:
    """Desugar one operator and operand into bounds."""
    if isinstance(operand, _Partial):
        return _expand_partial(op, operand)
    return _expand_full(op, operand)


def _expand_full(op: str, version: _Version) -> list[_Comparator]:
    """Desugar an operator applied to a full version."""
    anchor = bool(version.prerelease)
    if op == "~":
        ceiling = _upper(_Partial(version.major, version.minor, None))
        return [_Comparator(">=", version, anchor), _ceiling_bound(ceiling)]
    if op == "^":
        ceiling = _caret_ceiling(version.major, version.minor, version.patch)
        return [_Comparator(">=", version, anchor), _ceiling_bound(ceiling)]
    return [_Comparator(op, version, anchor)]


def _expand_partial(op: str, partial: _Partial) -> list[_Comparator]:
    """Desugar an operator applied to a partial version or wildcard."""
    if partial.major is None:
        return _expand_wildcard(op)
    lower = _lower(partial)
    upper = _upper(partial)
    if op == ">":
        return [_Comparator(">=", upper)]
    if op == ">=":
        return [_Comparator(">=", lower)]
    if op == "<":
        return [_ceiling_bound(lower)]
    if op == "<=":
        return [_ceiling_bound(upper)]
    if op == "^":
        ceiling = _caret_ceiling(partial.major, partial.minor, partial.patch)
        return [_Comparator(">=", lower), _ceiling_bound(ceiling)]
    return [_Comparator(">=", lower), _ceiling_bound(upper)]


def _expand_wildcard(op: str) -> list[_Comparator]:
    """Desugar an operator applied to ``*``, ``x`` or ``X``."""
    if op in ("<", ">"):
        return [_NOTHING]
    if op in ("~", "^"):
        raise ValueError(f"operator {op!r} cannot be used with a wildcard")
    return [_Comparator(">=", _Version(0, 0, 0))]


def _expand_hyphen(low: _Version | _Partial, high: _Version | _Partial) -> list[_Comparator]:
    """Desugar a hyphen range ``low - high``."""
    lower = _Comparator(">=", _as_version(low), _is_anchored(low))
    if isinstance(high, _Version):
        return [lower, _Comparator("<=", high, _is_anchored(high))]
    if high.major is None:
        return [lower]
    return [lower, _ceiling_bound(_upper(high))]


def _as_version(operand: _Version | _Partial) -> _Version:
    """Return the lowest version an operand stands for."""
    return operand if isinstance(operand, _Version) else _lower(operand)


def _is_anchored(operand: _Version | _Partial) -> bool:
    """Return whether an operand was written with a prerelease tag."""
    return isinstance(operand, _Version) and bool(operand.prerelease)


def _join_operators(tokens: list[str]) -> list[str]:
    """Attach a standalone operator to the token after it, so ``>= 1.2`` reads as ``>=1.2``."""
    joined: list[str] = []
    index = 0
    while index < len(tokens):
        if tokens[index] in _OPERATOR_ONLY and index + 1 < len(tokens):
            joined.append(tokens[index] + tokens[index + 1])
            index += 2
        else:
            joined.append(tokens[index])
            index += 1
    return joined


def _parse_comparator(token: str) -> list[_Comparator]:
    """Parse one comparator such as ``>=1.2`` or a bare ``1.2.3``."""
    match = _COMPARATOR_RE.fullmatch(token)
    if match is None:
        raise ValueError(f"invalid comparator: {token!r}")
    op, text = match.group(1) or "=", match.group(2)
    return _expand(op, _parse_operand(text))


def _parse_set(text: str) -> tuple[_Comparator, ...]:
    """Parse one comparator set. An empty set comes back as an empty tuple."""
    items = _join_operators(text.split())
    comparators: list[_Comparator] = []
    index = 0
    while index < len(items):
        if index + 2 < len(items) and items[index + 1] == "-":
            low = _parse_operand(items[index])
            high = _parse_operand(items[index + 2])
            comparators.extend(_expand_hyphen(low, high))
            index += 3
        else:
            comparators.extend(_parse_comparator(items[index]))
            index += 1
    return tuple(comparators)


def _parse_range(range_: str) -> list[tuple[_Comparator, ...]]:
    """Parse a full range into its comparator sets."""
    return [_parse_set(part) for part in range_.split("||")]


def _set_matches(comparators: tuple[_Comparator, ...], candidate: _Version) -> bool:
    """Return whether a version satisfies one comparator set, including the prerelease rule."""
    if not all(comparator.matches(candidate) for comparator in comparators):
        return False
    if not candidate.prerelease:
        return True
    return any(
        comparator.anchor and comparator.version.release == candidate.release
        for comparator in comparators
    )


def _matches_any(sets: list[tuple[_Comparator, ...]], candidate: _Version) -> bool:
    """Return whether a version satisfies at least one comparator set."""
    return any(_set_matches(comparators, candidate) for comparators in sets)
