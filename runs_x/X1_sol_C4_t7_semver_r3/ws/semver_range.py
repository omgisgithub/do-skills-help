"""Match npm-style version ranges as specified in TASK.md."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional, Union

_NUMBER = r"(?:0|[1-9][0-9]*)"
_IDENTIFIERS = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_VERSION = re.compile(
    rf"[v=]?({_NUMBER})\.({_NUMBER})\.({_NUMBER})"
    rf"(?:-({_IDENTIFIERS}))?(?:\+({_IDENTIFIERS}))?"
)
_PART = re.compile(rf"{_NUMBER}|[xX*]")
_OPERATORS = {"<", "<=", ">", ">=", "=", "~", "^"}


@dataclass(frozen=True)
class _Version:
    core: tuple[int, int, int]
    prerelease: tuple[str, ...] = ()

    def key(self) -> tuple[
        tuple[int, int, int], bool, tuple[tuple[int, Union[int, str]], ...]
    ]:
        identifiers: tuple[tuple[int, Union[int, str]], ...] = tuple(
            (0, int(part)) if part.isdigit() else (1, part) for part in self.prerelease
        )
        return self.core, not self.prerelease, identifiers


@dataclass(frozen=True)
class _Partial:
    version: _Version
    precision: int


@dataclass(frozen=True)
class _Comparator:
    operator: str
    version: _Version

    def matches(self, version: _Version) -> bool:
        left, right = version.key(), self.version.key()
        if self.operator == "<":
            return left < right
        if self.operator == "<=":
            return left <= right
        if self.operator == ">":
            return left > right
        if self.operator == ">=":
            return left >= right
        return left == right


@dataclass(frozen=True)
class _ComparatorSet:
    comparators: tuple[_Comparator, ...]
    prerelease_cores: frozenset[tuple[int, int, int]]

    def matches(self, version: _Version) -> bool:
        if version.prerelease and version.core not in self.prerelease_cores:
            return False
        return all(comparator.matches(version) for comparator in self.comparators)


def _parse_version(value: str) -> _Version:
    if not isinstance(value, str):
        raise ValueError("Version must be a string")
    match = _VERSION.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Invalid version: {value!r}")
    major, minor, patch, prerelease, _build = match.groups()
    identifiers = tuple(prerelease.split(".")) if prerelease else ()
    if any(part.isdigit() and len(part) > 1 and part[0] == "0" for part in identifiers):
        raise ValueError(f"Invalid numeric prerelease identifier: {value!r}")
    return _Version((int(major), int(minor), int(patch)), identifiers)


def _parse_partial(value: str) -> _Partial:
    if _VERSION.fullmatch(value):
        return _Partial(_parse_version(value), 3)
    original = value
    if value.startswith("v"):
        value = value[1:]
    parts = value.split(".")
    if not 1 <= len(parts) <= 3 or any(_PART.fullmatch(part) is None for part in parts):
        raise ValueError(f"Invalid range version: {original!r}")
    numbers = []
    has_wildcard = False
    for part in parts:
        if part in {"*", "x", "X"}:
            has_wildcard = True
        elif has_wildcard:
            raise ValueError(f"Numeric component after wildcard: {original!r}")
        else:
            numbers.append(int(part))
    precision = len(numbers)
    numbers.extend([0] * (3 - precision))
    return _Partial(_Version((numbers[0], numbers[1], numbers[2])), precision)


def _upper_bound(partial: _Partial, index: int) -> _Version:
    parts = list(partial.version.core)
    parts[index] += 1
    for trailing in range(index + 1, 3):
        parts[trailing] = 0
    return _Version((parts[0], parts[1], parts[2]), ("0",))


def _expand(operator: str, partial: _Partial) -> list[_Comparator]:
    version, precision = partial.version, partial.precision
    if precision == 0:
        if operator in {"<", ">"}:
            return [_Comparator("<", _Version((0, 0, 0)))]
        return [_Comparator(">=", _Version((0, 0, 0)))]
    if operator in {"~", "^"}:
        index = 0 if precision == 1 else 1
        if operator == "^":
            index = next(
                (i for i in range(precision) if version.core[i] != 0), precision - 1
            )
        return [_Comparator(">=", version), _Comparator("<", _upper_bound(partial, index))]
    if precision == 3:
        return [_Comparator(operator or "=", version)]
    upper = _upper_bound(partial, precision - 1)
    if operator == ">":
        return [_Comparator(">=", _Version(upper.core))]
    if operator == ">=":
        return [_Comparator(">=", version)]
    if operator == "<":
        return [_Comparator("<", _Version(version.core, ("0",)))]
    if operator == "<=":
        return [_Comparator("<", upper)]
    return [_Comparator(">=", version), _Comparator("<", upper)]


def _hyphen(left: _Partial, right: _Partial) -> list[_Comparator]:
    comparators = [_Comparator(">=", left.version)]
    if right.precision == 3:
        comparators.append(_Comparator("<=", right.version))
    elif right.precision:
        comparators.append(_Comparator("<", _upper_bound(right, right.precision - 1)))
    return comparators


def _parse_set(value: str) -> _ComparatorSet:
    tokens = value.split()
    comparators = []
    prerelease_cores = set()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if index + 1 < len(tokens) and tokens[index + 1] == "-":
            if index + 2 >= len(tokens):
                raise ValueError("Hyphen range requires two versions")
            operands = [_parse_partial(token), _parse_partial(tokens[index + 2])]
            comparators.extend(_hyphen(*operands))
            index += 3
        else:
            match = re.fullmatch(r"(<=|>=|<|>|=|~|\^)?(.*)", token)
            if match is None:
                raise ValueError(f"Invalid comparator: {token!r}")
            operator, operand = match.groups()
            if token in _OPERATORS:
                index += 1
                if index >= len(tokens):
                    raise ValueError("Comparator requires a version")
                operand = tokens[index]
            # An equals sign here would be a second operator, not a version prefix.
            if operand.startswith("="):
                raise ValueError(f"Invalid comparator: {token!r}")
            operands = [_parse_partial(operand)]
            comparators.extend(_expand(operator or "", operands[0]))
            index += 1
        prerelease_cores.update(
            part.version.core for part in operands if part.version.prerelease
        )
    return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))


def _parse_range(range_: str) -> tuple[_ComparatorSet, ...]:
    if not isinstance(range_, str):
        raise ValueError("Range must be a string")
    return tuple(_parse_set(value) for value in range_.split("||"))


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version satisfies a range.

    Raises:
        ValueError: If the version or range is invalid.
    """
    parsed_version = _parse_version(version)
    comparator_sets = _parse_range(range_)
    return any(comparator_set.matches(parsed_version) for comparator_set in comparator_sets)


def max_satisfying(versions: Sequence[object], range_: str) -> Optional[str]:
    """Return the first highest matching version, skipping invalid entries.

    Raises:
        ValueError: If the range is invalid.
    """
    comparator_sets = _parse_range(range_)
    best_version = None
    best_string = None
    for value in versions:
        if not isinstance(value, str):
            continue
        try:
            version = _parse_version(value)
        except ValueError:
            # Invalid entries are explicitly ignored by this API.
            continue
        if not any(comparator_set.matches(version) for comparator_set in comparator_sets):
            continue
        if best_version is None or version.key() > best_version.key():
            best_version, best_string = version, value
    return best_string
