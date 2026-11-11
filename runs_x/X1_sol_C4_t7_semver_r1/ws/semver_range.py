"""npm-style version range matching. See TASK.md for the exact spec."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_NUMBER = r"(?:0|[1-9][0-9]*)"
_IDENTIFIERS = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_VERSION = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})"
    rf"(?:-({_IDENTIFIERS}))?(?:\+({_IDENTIFIERS}))?"
)
_OPERATORS = frozenset(("<", "<=", ">", ">=", "=", "~", "^"))


@dataclass(frozen=True)
class _Version:
    core: tuple[int, int, int]
    prerelease: tuple[str, ...] = ()

    def compare(self, other: _Version) -> int:
        if self.core != other.core:
            return 1 if self.core > other.core else -1
        if not self.prerelease or not other.prerelease:
            return bool(other.prerelease) - bool(self.prerelease)
        for left, right in zip(self.prerelease, other.prerelease):
            if left == right:
                continue
            if left.isdigit() and right.isdigit():
                return 1 if int(left) > int(right) else -1
            if left.isdigit() != right.isdigit():
                return -1 if left.isdigit() else 1
            return 1 if left > right else -1
        return (len(self.prerelease) > len(other.prerelease)) - (
            len(self.prerelease) < len(other.prerelease)
        )


def _parse_version(value: str) -> _Version:
    if not isinstance(value, str):
        raise ValueError("Version must be a string")
    text = value.strip()
    if text.startswith(("v", "=")):
        text = text[1:]
    match = _VERSION.fullmatch(text)
    if match is None:
        raise ValueError(f"Invalid version: {value!r}")
    major, minor, patch, prerelease, _ = match.groups()
    identifiers = tuple(prerelease.split(".")) if prerelease else ()
    if any(part.isdigit() and len(part) > 1 and part[0] == "0" for part in identifiers):
        raise ValueError(f"Invalid numeric prerelease identifier: {value!r}")
    return _Version((int(major), int(minor), int(patch)), identifiers)


def _parse_operand(text: str) -> tuple[_Version, int]:
    if text.startswith("v"):
        text = text[1:]
    if "-" in text or "+" in text:
        # Prefixes have already been consumed; a second prefix is invalid.
        if not text or text[0] not in "0123456789":
            raise ValueError(f"Invalid range version: {text!r}")
        return _parse_version(text), 3
    parts = text.split(".")
    if len(parts) > 3:
        raise ValueError(f"Invalid range version: {text!r}")
    numbers: list[int] = []
    has_wildcard = False
    for part in parts:
        if part in ("*", "x", "X"):
            has_wildcard = True
        elif not has_wildcard and re.fullmatch(_NUMBER, part):
            numbers.append(int(part))
        else:
            raise ValueError(f"Invalid range version: {text!r}")
    precision = len(numbers)
    numbers.extend([0] * (3 - precision))
    return _Version((numbers[0], numbers[1], numbers[2])), precision


@dataclass(frozen=True)
class _Comparator:
    operator: str
    version: _Version

    def matches(self, version: _Version) -> bool:
        comparison = version.compare(self.version)
        if self.operator == "<":
            return comparison < 0
        if self.operator == "<=":
            return comparison <= 0
        if self.operator == ">":
            return comparison > 0
        if self.operator == ">=":
            return comparison >= 0
        return comparison == 0


def _upper_bound(version: _Version, index: int) -> _Version:
    parts = list(version.core)
    parts[index] += 1
    for following in range(index + 1, 3):
        parts[following] = 0
    return _Version((parts[0], parts[1], parts[2]), ("0",))


def _expand(operator: str, version: _Version, precision: int) -> list[_Comparator]:
    if precision == 0:
        if operator in ("<", ">"):
            return [_Comparator("<", _Version((0, 0, 0)))]
        return [_Comparator(">=", _Version((0, 0, 0)))]
    if operator in ("~", "^"):
        if operator == "~":
            index = min(precision - 1, 1)
        else:
            index = next(
                (i for i in range(precision) if version.core[i] != 0), precision - 1
            )
        return [_Comparator(">=", version), _Comparator("<", _upper_bound(version, index))]
    if precision == 3:
        return [_Comparator(operator or "=", version)]
    upper = _upper_bound(version, precision - 1)
    if operator == ">":
        return [_Comparator(">=", _Version(upper.core))]
    if operator == ">=":
        return [_Comparator(">=", version)]
    if operator == "<":
        return [_Comparator("<", _Version(version.core, ("0",)))]
    if operator == "<=":
        return [_Comparator("<", upper)]
    return [_Comparator(">=", version), _Comparator("<", upper)]


@dataclass(frozen=True)
class _ComparatorSet:
    comparators: tuple[_Comparator, ...]
    prerelease_cores: frozenset[tuple[int, int, int]]

    def matches(self, version: _Version) -> bool:
        if version.prerelease and version.core not in self.prerelease_cores:
            return False
        return all(comparator.matches(version) for comparator in self.comparators)


def _parse_set(text: str) -> _ComparatorSet:
    tokens = text.split()
    comparators: list[_Comparator] = []
    prerelease_cores: set[tuple[int, int, int]] = set()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if index + 1 < len(tokens) and tokens[index + 1] == "-":
            if index + 2 >= len(tokens):
                raise ValueError("Hyphen range requires two endpoints")
            left, _ = _parse_operand(token)
            right, precision = _parse_operand(tokens[index + 2])
            expanded = [_Comparator(">=", left)]
            if precision == 3:
                expanded.append(_Comparator("<=", right))
            elif precision:
                expanded.append(_Comparator("<", _upper_bound(right, precision - 1)))
            originals = (left, right)
            index += 3
        else:
            if token in _OPERATORS:
                index += 1
                if index == len(tokens):
                    raise ValueError("Comparator requires a version")
                token += tokens[index]
            match = re.fullmatch(r"(<=|>=|<|>|=|~|\^)?(.+)", token)
            if match is None:
                raise ValueError(f"Invalid comparator: {token!r}")
            operator, operand = match.groups()
            version, precision = _parse_operand(operand)
            expanded = _expand(operator or "", version, precision)
            originals = (version,)
            index += 1
        comparators.extend(expanded)
        prerelease_cores.update(version.core for version in originals if version.prerelease)
    return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))


def _parse_range(range_: str) -> tuple[_ComparatorSet, ...]:
    if not isinstance(range_, str):
        raise ValueError("Range must be a string")
    return tuple(_parse_set(part) for part in range_.split("||"))


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version satisfies a range.

    Raises:
        ValueError: If the version or range is invalid.
    """
    parsed = _parse_version(version)
    comparator_sets = _parse_range(range_)
    return any(comparator_set.matches(parsed) for comparator_set in comparator_sets)


def max_satisfying(versions: list[object], range_: str) -> Optional[str]:
    """Return the first highest matching version, skipping invalid entries.

    Raises:
        ValueError: If the range is invalid.
    """
    comparator_sets = _parse_range(range_)
    best: Optional[_Version] = None
    result: Optional[str] = None
    for value in versions:
        if not isinstance(value, str):
            continue
        try:
            parsed = _parse_version(value)
        except ValueError:
            # The API explicitly requires invalid entries to be skipped.
            continue
        if (best is None or parsed.compare(best) > 0) and any(
            comparator_set.matches(parsed) for comparator_set in comparator_sets
        ):
            best, result = parsed, value
    return result
