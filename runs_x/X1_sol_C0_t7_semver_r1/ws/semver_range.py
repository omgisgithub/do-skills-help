"""npm-style version range matching. See TASK.md for the exact spec."""

import re
from dataclasses import dataclass


_NUMBER = r"(?:0|[1-9][0-9]*)"
_IDENTIFIERS = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_FULL = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})"
    rf"(?:-({_IDENTIFIERS}))?(?:\+({_IDENTIFIERS}))?"
)
@dataclass(frozen=True)
class _Version:
    core: tuple
    prerelease: tuple = ()

    @property
    def key(self):
        identifiers = tuple(
            (0, int(part)) if part.isdigit() else (1, part)
            for part in self.prerelease
        )
        return self.core, not self.prerelease, identifiers


def _parse_version(value):
    if not isinstance(value, str):
        raise ValueError("Version must be a string")
    value = value.strip()
    if value.startswith(("v", "=")):
        value = value[1:]
    match = _FULL.fullmatch(value)
    if match is None:
        raise ValueError("Invalid version: " + value)
    major, minor, patch, prerelease, _build = match.groups()
    parts = tuple(prerelease.split(".")) if prerelease else ()
    if any(p.isdigit() and len(p) > 1 and p[0] == "0" for p in parts):
        raise ValueError("Leading zero in prerelease")
    return _Version((int(major), int(minor), int(patch)), parts)


def _parse_endpoint(value):
    """Return a zero-filled version and the number of specified components."""
    if value.startswith("v"):
        value = value[1:]
    if _FULL.fullmatch(value):
        return _parse_version(value), 3
    parts = value.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Invalid range version: " + value)
    numbers = []
    wildcard = False
    for part in parts:
        if part in ("*", "x", "X"):
            wildcard = True
        elif not wildcard and re.fullmatch(_NUMBER, part):
            numbers.append(int(part))
        else:
            raise ValueError("Invalid range version: " + value)
    if len(numbers) == 3:
        # A full version would already have matched above.
        raise ValueError("Invalid range version: " + value)
    return _Version(tuple(numbers + [0] * (3 - len(numbers)))), len(numbers)


def _upper(version, component):
    core = list(version.core)
    core[component] += 1
    core[component + 1:] = [0] * (2 - component)
    return _Version(tuple(core), ("0",))


def _expand(operator, version, precision):
    if operator in ("~", "^"):
        if precision == 0:
            return [(">=", _Version((0, 0, 0)))]
        if operator == "~":
            component = 0 if precision == 1 else 1
        else:
            component = next(
                (i for i in range(precision) if version.core[i] != 0),
                precision - 1,
            )
        return [(">=", version), ("<", _upper(version, component))]
    if precision == 3:
        return [(operator or "=", version)]
    if precision == 0:
        if operator in ("<", ">"):
            return [("<", _Version((0, 0, 0), ("0",)))]
        return [(">=", _Version((0, 0, 0)))]
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
    for alternative in range_.split("||"):
        tokens = alternative.split()
        comparators = []
        prerelease_cores = set()

        def endpoint(token):
            version, precision = _parse_endpoint(token)
            if version.prerelease:
                prerelease_cores.add(version.core)
            return version, precision

        index = 0
        while index < len(tokens):
            token = tokens[index]
            if index + 1 < len(tokens) and tokens[index + 1] == "-":
                if index + 2 >= len(tokens):
                    raise ValueError("Missing hyphen range endpoint")
                left, _ = endpoint(token)
                right, precision = endpoint(tokens[index + 2])
                comparators.append((">=", left))
                if precision == 3:
                    comparators.append(("<=", right))
                elif precision:
                    comparators.append(("<", _upper(right, precision - 1)))
                index += 3
                continue
            match = re.fullmatch(r"(<=|>=|<|>|=|~|\^)?(.*)", token)
            operator, operand = match.groups()
            if operator and not operand:
                index += 1
                if index >= len(tokens):
                    raise ValueError("Missing comparator version")
                operand = tokens[index]
            version, precision = endpoint(operand)
            comparators.extend(_expand(operator, version, precision))
            index += 1
        sets.append((comparators, prerelease_cores))
    return sets


def _matches(version, sets):
    key = version.key
    for comparators, prerelease_cores in sets:
        if version.prerelease and version.core not in prerelease_cores:
            continue
        for operator, bound in comparators:
            other = bound.key
            if not {"=": key == other, "<": key < other, "<=": key <= other,
                    ">": key > other, ">=": key >= other}[operator]:
                break
        else:
            return True
    return False


def satisfies(version, range_):
    """Return whether a valid version satisfies a valid npm-style range."""
    return _matches(_parse_version(version), _parse_range(range_))


def max_satisfying(versions, range_):
    """Return the first highest matching input, skipping invalid versions."""
    sets = _parse_range(range_)
    best = None
    best_version = None
    for value in versions:
        try:
            version = _parse_version(value)
        except ValueError:
            continue
        if _matches(version, sets) and (
            best_version is None or version.key > best_version.key
        ):
            best, best_version = value, version
    return best
