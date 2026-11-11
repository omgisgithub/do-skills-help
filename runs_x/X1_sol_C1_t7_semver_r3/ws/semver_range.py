"""Strict npm-style version range matching as specified in TASK.md."""

import re
from functools import total_ordering


_NUMBER = r"(?:0|[1-9][0-9]*)"
_IDENTIFIER = r"[0-9A-Za-z-]+"
_FULL = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})"
    rf"(?:-({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?"
    rf"(?:\+({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?"
)
_PART = re.compile(rf"(?:{_NUMBER}|[xX*])")
_OPERATORS = {"<", "<=", ">", ">=", "=", "~", "^"}


@total_ordering
class _Version:
    def __init__(self, core, pre=()):
        self.core = tuple(core)
        self.pre = tuple(pre)

    def __eq__(self, other):
        return self.core == other.core and self.pre == other.pre

    def __lt__(self, other):
        if self.core != other.core:
            return self.core < other.core
        if not self.pre or not other.pre:
            return bool(self.pre) and not other.pre
        for left, right in zip(self.pre, other.pre):
            if left == right:
                continue
            left_num, right_num = left.isdigit(), right.isdigit()
            if left_num and right_num:
                return int(left) < int(right)
            if left_num != right_num:
                return left_num
            return left < right
        return len(self.pre) < len(other.pre)


def _parse_version(value):
    if not isinstance(value, str):
        raise ValueError("Version must be a string")
    value = value.strip()
    if value.startswith(("v", "=")):
        value = value[1:]
    match = _FULL.fullmatch(value)
    if match is None:
        raise ValueError("Invalid version: " + value)
    major, minor, patch, pre, _build = match.groups()
    identifiers = tuple(pre.split(".")) if pre else ()
    if any(p.isdigit() and len(p) > 1 and p[0] == "0" for p in identifiers):
        raise ValueError("Leading zero in prerelease")
    return _Version((int(major), int(minor), int(patch)), identifiers)


def _parse_operand(value):
    """Return a zero-filled version and the number of specified components."""
    if value.startswith("v"):
        value = value[1:]
    if _FULL.fullmatch(value):
        return _parse_version(value), 3
    parts = value.split(".")
    if not 1 <= len(parts) <= 3 or any(not _PART.fullmatch(p) for p in parts):
        raise ValueError("Invalid range version: " + value)
    core = []
    wildcard = False
    for part in parts:
        if part in ("x", "X", "*"):
            wildcard = True
        elif wildcard:
            raise ValueError("Numeric component after wildcard")
        else:
            core.append(int(part))
    precision = len(core)
    return _Version(core + [0] * (3 - precision)), precision


def _upper(version, component):
    core = list(version.core)
    core[component] += 1
    for index in range(component + 1, 3):
        core[index] = 0
    return _Version(core, ("0",))


def _expand(operator, version, precision):
    if operator in ("~", "^"):
        if precision == 0:
            return [(">=", version)]
        if operator == "~":
            component = 0 if precision == 1 else 1
        else:
            component = next((i for i in range(precision) if version.core[i]), precision - 1)
        return [(">=", version), ("<", _upper(version, component))]
    if precision == 3:
        return [(operator or "=", version)]
    if precision == 0:
        if operator in ("<", ">"):
            return [("<", _Version((0, 0, 0), ("0",)))]
        return [(">=", version)]
    upper = _upper(version, precision - 1)
    if operator == ">":
        return [(">=", _Version(upper.core))]
    if operator == ">=":
        return [(">=", version)]
    if operator == "<":
        return [("<", _Version(version.core, ("0",)))]
    if operator == "<=":
        return [("<", upper)]
    return [(">=", version), ("<", upper)]


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("Range must be a string")
    sets = []
    for text in range_.split("||"):
        tokens = text.split()
        comparisons, prerelease_cores = [], set()
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if index + 1 < len(tokens) and tokens[index + 1] == "-":
                if index + 2 >= len(tokens):
                    raise ValueError("Missing hyphen range endpoint")
                left, left_precision = _parse_operand(token)
                right, right_precision = _parse_operand(tokens[index + 2])
                comparisons.append((">=", left))
                if right_precision == 3:
                    comparisons.append(("<=", right))
                elif right_precision:
                    comparisons.append(("<", _upper(right, right_precision - 1)))
                for endpoint in (left, right):
                    if endpoint.pre:
                        prerelease_cores.add(endpoint.core)
                index += 3
                continue
            match = re.fullmatch(r"(<=|>=|<|>|=|~|\^)?(.*)", token)
            operator, operand = match.groups()
            if token in _OPERATORS:
                index += 1
                if index >= len(tokens):
                    raise ValueError("Missing comparator operand")
                operand = tokens[index]
            version, precision = _parse_operand(operand)
            if version.pre:
                prerelease_cores.add(version.core)
            comparisons.extend(_expand(operator, version, precision))
            index += 1
        sets.append((comparisons, prerelease_cores))
    return sets


def _matches(version, sets):
    for comparisons, prerelease_cores in sets:
        if version.pre and version.core not in prerelease_cores:
            continue
        for operator, bound in comparisons:
            if operator == "=":
                matches = version == bound
            elif operator == "<":
                matches = version < bound
            elif operator == "<=":
                matches = version <= bound
            elif operator == ">":
                matches = version > bound
            else:
                matches = version >= bound
            if not matches:
                break
        else:
            return True
    return False


def satisfies(version: str, range_: str) -> bool:
    """Return whether version matches range_; invalid input raises ValueError."""
    return _matches(_parse_version(version), _parse_range(range_))


def max_satisfying(versions: list, range_: str):
    """Return the first highest-precedence matching string, skipping invalid entries."""
    sets = _parse_range(range_)
    best, best_version = None, None
    for value in versions:
        try:
            version = _parse_version(value)
        except ValueError:
            continue
        if _matches(version, sets) and (best_version is None or best_version < version):
            best, best_version = value, version
    return best
