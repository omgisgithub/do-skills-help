"""Match npm-style version ranges as specified in TASK.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_NUMBER = r"(?:0|[1-9][0-9]*)"
_IDENTIFIERS = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_VERSION = re.compile(
    rf"[v=]?({_NUMBER})\.({_NUMBER})\.({_NUMBER})"
    rf"(?:-({_IDENTIFIERS}))?(?:\+({_IDENTIFIERS}))?"
)
_PARTIAL = re.compile(
    rf"[v=]?({_NUMBER}|[xX*])(?:\.({_NUMBER}|[xX*]))?"
    rf"(?:\.({_NUMBER}|[xX*]))?"
)


@dataclass(frozen=True)
class _Version:
    core: tuple[int, int, int]
    prerelease: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Operand:
    version: _Version
    precision: int


@dataclass(frozen=True)
class _Comparator:
    operator: str
    version: _Version

    def matches(self, version: _Version) -> bool:
        comparison = _compare(version, self.version)
        return {
            "=": comparison == 0,
            "<": comparison < 0,
            "<=": comparison <= 0,
            ">": comparison > 0,
            ">=": comparison >= 0,
        }[self.operator]


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
        raise ValueError("A version must be a string")
    match = _VERSION.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Invalid version: {value!r}")
    major, minor, patch, prerelease, _ = match.groups()
    identifiers = tuple(prerelease.split(".")) if prerelease else ()
    if any(item.isdigit() and len(item) > 1 and item.startswith("0") for item in identifiers):
        raise ValueError(f"Invalid numeric prerelease identifier: {value!r}")
    return _Version((int(major), int(minor), int(patch)), identifiers)


def _compare(left: _Version, right: _Version) -> int:
    if left.core != right.core:
        return 1 if left.core > right.core else -1
    if not left.prerelease or not right.prerelease:
        return int(not left.prerelease) - int(not right.prerelease)
    for first, second in zip(left.prerelease, right.prerelease):
        if first == second:
            continue
        if first.isdigit() and second.isdigit():
            return 1 if int(first) > int(second) else -1
        if first.isdigit() != second.isdigit():
            return -1 if first.isdigit() else 1
        return 1 if first > second else -1
    return (len(left.prerelease) > len(right.prerelease)) - (
        len(left.prerelease) < len(right.prerelease)
    )


def _parse_operand(value: str) -> _Operand:
    if _VERSION.fullmatch(value):
        return _Operand(_parse_version(value), 3)
    match = _PARTIAL.fullmatch(value)
    if match is None:
        raise ValueError(f"Invalid range version: {value!r}")
    numbers = []
    has_wildcard = False
    for part in match.groups():
        if part is None or part in ("x", "X", "*"):
            has_wildcard = True
        elif has_wildcard:
            raise ValueError(f"Numeric component after wildcard: {value!r}")
        else:
            numbers.append(int(part))
    precision = len(numbers)
    numbers.extend([0] * (3 - precision))
    return _Operand(_Version((numbers[0], numbers[1], numbers[2])), precision)


def _upper_bound(operand: _Operand, index: int) -> _Version:
    parts = list(operand.version.core)
    parts[index] += 1
    for position in range(index + 1, 3):
        parts[position] = 0
    return _Version((parts[0], parts[1], parts[2]), ("0",))


def _expand(operator: str, operand: _Operand) -> list[_Comparator]:
    version, precision = operand.version, operand.precision
    if precision == 0:
        # These strict wildcard comparisons are deliberately unsatisfiable.
        if operator in ("<", ">"):
            return [_Comparator("<", _Version((0, 0, 0), ("0",)))]
        return [_Comparator(">=", _Version((0, 0, 0)))]
    if operator in ("~", "^"):
        index = 0 if precision == 1 else 1
        if operator == "^":
            index = next((i for i in range(precision) if version.core[i]), precision - 1)
        return [_Comparator(">=", version), _Comparator("<", _upper_bound(operand, index))]
    if precision == 3:
        return [_Comparator(operator or "=", version)]
    upper = _upper_bound(operand, precision - 1)
    if operator == ">":
        return [_Comparator(">=", _Version(upper.core))]
    if operator == ">=":
        return [_Comparator(">=", version)]
    if operator == "<":
        return [_Comparator("<", _Version(version.core, ("0",)))]
    if operator == "<=":
        return [_Comparator("<", upper)]
    return [_Comparator(">=", version), _Comparator("<", upper)]


def _hyphen(left: _Operand, right: _Operand) -> list[_Comparator]:
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
                raise ValueError("Missing right side of hyphen range")
            operands = [_parse_operand(token), _parse_operand(tokens[index + 2])]
            comparators.extend(_hyphen(*operands))
            index += 3
        else:
            match = re.fullmatch(r"(<=|>=|<|>|=|~|\^)?(.*)", token)
            if match is None:
                raise ValueError(f"Invalid comparator: {token!r}")
            operator, raw = match.groups()
            if not raw:
                index += 1
                if index >= len(tokens):
                    raise ValueError("Missing comparator version")
                raw = tokens[index]
            if raw[0] in "<>=~^":
                raise ValueError(f"Invalid comparator version: {raw!r}")
            operands = [_parse_operand(raw)]
            comparators.extend(_expand(operator or "", operands[0]))
            index += 1
        prerelease_cores.update(item.version.core for item in operands if item.version.prerelease)
    return _ComparatorSet(tuple(comparators), frozenset(prerelease_cores))


def _parse_range(range_: str) -> tuple[_ComparatorSet, ...]:
    if not isinstance(range_, str):
        raise ValueError("A range must be a string")
    # Parse every branch before matching so an invalid branch always raises.
    return tuple(_parse_set(value) for value in range_.split("||"))


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version satisfies a range.

    Raises:
        ValueError: If the version or range is invalid.
    """
    parsed = _parse_version(version)
    return any(group.matches(parsed) for group in _parse_range(range_))


def max_satisfying(versions: list[object], range_: str) -> Optional[str]:
    """Return the first highest matching version string, skipping invalid entries.

    Raises:
        ValueError: If the range is invalid.
    """
    groups = _parse_range(range_)
    best = None
    best_version = None
    for value in versions:
        if not isinstance(value, str):
            continue
        try:
            parsed = _parse_version(value)
        except ValueError:
            # Invalid entries are explicitly excluded by the public API.
            continue
        if any(group.matches(parsed) for group in groups):
            if best_version is None or _compare(parsed, best_version) > 0:
                best, best_version = value, parsed
    return best
