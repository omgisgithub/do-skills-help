"""npm-style version range matching. See TASK.md for the exact spec."""

import re
from dataclasses import dataclass


_NUMBER = r"(?:0|[1-9][0-9]*)"
_IDENTIFIERS = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_VERSION = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})"
    rf"(?:-({_IDENTIFIERS}))?(?:\+({_IDENTIFIERS}))?"
)
_PARTIAL = re.compile(
    rf"({_NUMBER}|[xX*])(?:\.({_NUMBER}|[xX*]))?"
    rf"(?:\.({_NUMBER}|[xX*]))?"
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
        return self.core + (not self.prerelease, identifiers)


def _parse_version(text):
    if not isinstance(text, str):
        raise ValueError("Version must be a string")
    text = text.strip()
    if text.startswith(("v", "=")):
        text = text[1:]
    return _full_version(text)


def _full_version(text):
    match = _VERSION.fullmatch(text)
    if match is None:
        raise ValueError("Invalid version: {!r}".format(text))
    major, minor, patch, prerelease, _build = match.groups()
    parts = tuple(prerelease.split(".")) if prerelease else ()
    if any(p.isdigit() and len(p) > 1 and p[0] == "0" for p in parts):
        raise ValueError("Numeric prerelease identifiers cannot have leading zeros")
    return _Version((int(major), int(minor), int(patch)), parts)


def _operand(text):
    """Return a zero-filled version and the number of specified components."""
    if text.startswith("v"):
        text = text[1:]
    if _VERSION.fullmatch(text):
        return _full_version(text), 3
    match = _PARTIAL.fullmatch(text)
    if match is None:
        raise ValueError("Invalid range version: {!r}".format(text))
    core = []
    precision = 0
    ended = False
    for part in match.groups():
        if part is None or part in ("x", "X", "*"):
            ended = True
            core.append(0)
        else:
            if ended:
                raise ValueError("A number cannot follow a wildcard")
            core.append(int(part))
            precision += 1
    return _Version(tuple(core)), precision


def _next(version, component, prerelease=True):
    core = list(version.core)
    core[component] += 1
    for i in range(component + 1, 3):
        core[i] = 0
    return _Version(tuple(core), ("0",) if prerelease else ())


def _expand(operator, version, precision):
    if precision == 0:
        if operator in (">", "<"):
            return [("<", _Version((0, 0, 0), ("0",)))]
        return [(">=", _Version((0, 0, 0)))]
    if operator in ("~", "^"):
        if operator == "~":
            component = 0 if precision == 1 else 1
        else:
            # Missing components may vary, even when all specified parts are zero.
            component = next(
                (i for i in range(precision) if version.core[i] != 0),
                precision - 1,
            )
        return [(">=", version), ("<", _next(version, component))]
    if precision == 3:
        return [(operator or "=", version)]
    upper = _next(version, precision - 1)
    if operator in ("", "="):
        return [(">=", version), ("<", upper)]
    if operator == ">":
        return [(">=", _next(version, precision - 1, prerelease=False))]
    if operator == ">=":
        return [(">=", version)]
    if operator == "<":
        return [("<", _Version(version.core, ("0",)))]
    return [("<", upper)]  # <= a partial version


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("Range must be a string")
    sets = []
    for source in range_.split("||"):
        tokens = source.split()
        comparators = []
        explicit_prereleases = set()

        def record(version):
            if version.prerelease:
                explicit_prereleases.add(version.core)

        i = 0
        while i < len(tokens):
            if i + 1 < len(tokens) and tokens[i + 1] == "-":
                if i + 2 >= len(tokens):
                    raise ValueError("Missing right side of hyphen range")
                left, _ = _operand(tokens[i])
                right, precision = _operand(tokens[i + 2])
                record(left)
                record(right)
                comparators.append((">=", left))
                if precision == 3:
                    comparators.append(("<=", right))
                elif precision:
                    comparators.append(("<", _next(right, precision - 1)))
                i += 3
                continue
            match = re.fullmatch(r"(<=|>=|<|>|=|~|\^)?(.*)", tokens[i])
            operator, operand = match.groups()
            operator = operator or ""
            if not operand:
                i += 1
                if i >= len(tokens):
                    raise ValueError("Missing comparator version")
                operand = tokens[i]
            version, precision = _operand(operand)
            record(version)
            comparators.extend(_expand(operator, version, precision))
            i += 1
        sets.append((comparators, explicit_prereleases))
    return sets


def _matches(version, sets):
    key = version.key
    for comparators, explicit_prereleases in sets:
        if version.prerelease and version.core not in explicit_prereleases:
            continue
        for operator, bound in comparators:
            other = bound.key
            if not {
                "=": key == other,
                "<": key < other,
                "<=": key <= other,
                ">": key > other,
                ">=": key >= other,
            }[operator]:
                break
        else:
            return True
    return False


def satisfies(version, range_):
    """Return whether version satisfies range_; reject invalid input."""
    return _matches(_parse_version(version), _parse_range(range_))


def max_satisfying(versions, range_):
    """Return the first highest matching input string, skipping invalid versions."""
    sets = _parse_range(range_)
    best = None
    best_version = None
    for text in versions:
        try:
            version = _parse_version(text)
        except ValueError:
            continue
        if _matches(version, sets) and (
            best_version is None or version.key > best_version.key
        ):
            best = text
            best_version = version
    return best
