"""npm-style version range matching. See TASK.md for the exact spec."""

import re
from dataclasses import dataclass
from functools import total_ordering


_NUMBER = r"(?:0|[1-9][0-9]*)"
_IDENTIFIERS = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_VERSION = re.compile(
    r"(" + _NUMBER + r")\.(" + _NUMBER + r")\.(" + _NUMBER + r")"
    r"(?:-(" + _IDENTIFIERS + r"))?(?:\+(" + _IDENTIFIERS + r"))?"
)
_PART = re.compile(_NUMBER)
_COMPARATOR = re.compile(r"(<=|>=|<|>|=|~|\^)?(.+)")
_OPERATORS = {"<", "<=", ">", ">=", "=", "~", "^"}


@total_ordering
@dataclass(frozen=True)
class _Version:
    core: tuple
    prerelease: tuple = ()

    def __lt__(self, other):
        if self.core != other.core:
            return self.core < other.core
        if not self.prerelease or not other.prerelease:
            return bool(self.prerelease) and not other.prerelease
        for left, right in zip(self.prerelease, other.prerelease):
            if left == right:
                continue
            left_numeric, right_numeric = left.isdigit(), right.isdigit()
            if left_numeric != right_numeric:
                return left_numeric
            if left_numeric:
                return int(left) < int(right)
            return left < right
        return len(self.prerelease) < len(other.prerelease)


def _parse_version(text, prefix=True):
    if not isinstance(text, str):
        raise ValueError("Version must be a string")
    text = text.strip()
    if prefix and text[:1] in ("v", "="):
        text = text[1:]
    match = _VERSION.fullmatch(text)
    if match is None:
        raise ValueError("Invalid version: {!r}".format(text))
    major, minor, patch, prerelease, _build = match.groups()
    identifiers = tuple(prerelease.split(".")) if prerelease else ()
    if any(part.isdigit() and len(part) > 1 and part[0] == "0"
           for part in identifiers):
        raise ValueError("Numeric prerelease identifiers cannot have leading zeros")
    return _Version((int(major), int(minor), int(patch)), identifiers)


def _parse_operand(text):
    """Return a zero-filled version and the number of specified core parts."""
    if text.startswith("v"):
        text = text[1:]
    if _VERSION.fullmatch(text):
        return _parse_version(text, prefix=False), 3
    parts = text.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Invalid range version: {!r}".format(text))
    numbers = []
    wildcard = False
    for part in parts:
        if part in ("*", "x", "X"):
            wildcard = True
        elif not wildcard and _PART.fullmatch(part):
            numbers.append(int(part))
        else:
            raise ValueError("Invalid range version: {!r}".format(text))
    return _Version(tuple(numbers + [0] * (3 - len(numbers)))), len(numbers)


def _upper(version, index):
    core = list(version.core)
    core[index] += 1
    core[index + 1:] = [0] * (2 - index)
    return _Version(tuple(core), ("0",))


def _expand(operator, version, precision):
    if precision == 0:
        # No release can satisfy these strict wildcard comparators.
        if operator in ("<", ">"):
            return [("<", _Version((0, 0, 0), ("0",)))]
        return [(">=", _Version((0, 0, 0)))]
    if operator in ("~", "^"):
        if operator == "~":
            index = 0 if precision == 1 else 1
        else:
            # Missing parts may vary even when all specified parts are zero.
            index = next((i for i in range(precision) if version.core[i]),
                         min(precision - 1, 2))
        return [(">=", version), ("<", _upper(version, index))]
    if precision == 3:
        return [(operator or "=", version)]
    if operator in ("", "="):
        return [(">=", version), ("<", _upper(version, precision - 1))]
    if operator == ">=":
        return [(">=", version)]
    if operator == ">":
        return [(">=", _Version(_upper(version, precision - 1).core))]
    if operator == "<":
        return [("<", _Version(version.core, ("0",)))]
    return [("<", _upper(version, precision - 1))]  # <= partial


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("Range must be a string")
    sets = []
    for alternative in range_.split("||"):
        tokens = alternative.split()
        comparisons = []
        prerelease_cores = set()

        def operand(text):
            version, precision = _parse_operand(text)
            if version.prerelease:
                prerelease_cores.add(version.core)
            return version, precision

        index = 0
        while index < len(tokens):
            token = tokens[index]
            if index + 1 < len(tokens) and tokens[index + 1] == "-":
                if index + 2 >= len(tokens):
                    raise ValueError("Missing hyphen range endpoint")
                left, left_precision = operand(token)
                right, right_precision = operand(tokens[index + 2])
                if left_precision:
                    comparisons.append((">=", left))
                if right_precision == 3:
                    comparisons.append(("<=", right))
                elif right_precision:
                    comparisons.append(("<", _upper(right, right_precision - 1)))
                index += 3
                continue
            if token in _OPERATORS:
                if index + 1 >= len(tokens):
                    raise ValueError("Missing comparator version")
                operator = token
                index += 1
                text = tokens[index]
            else:
                match = _COMPARATOR.fullmatch(token)
                if match is None:
                    raise ValueError("Invalid comparator: {!r}".format(token))
                operator, text = match.groups()
                operator = operator or ""
            version, precision = operand(text)
            comparisons.extend(_expand(operator, version, precision))
            index += 1
        sets.append((comparisons, prerelease_cores))
    return sets


def _matches(version, sets):
    for comparisons, prerelease_cores in sets:
        if version.prerelease and version.core not in prerelease_cores:
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


def satisfies(version, range_):
    """Whether version satisfies range_; raise ValueError for invalid input."""
    return _matches(_parse_version(version), _parse_range(range_))


def max_satisfying(versions, range_):
    """Return the first highest matching version, skipping invalid versions."""
    sets = _parse_range(range_)
    best = None
    result = None
    for text in versions:
        try:
            version = _parse_version(text)
        except ValueError:
            continue
        if (best is None or best < version) and _matches(version, sets):
            best, result = version, text
    return result
