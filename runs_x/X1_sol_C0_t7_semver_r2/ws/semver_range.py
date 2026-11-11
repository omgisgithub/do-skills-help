"""npm-style version range matching. See TASK.md for the exact spec."""

import re
from dataclasses import dataclass


_NUMBER = r"(?:0|[1-9][0-9]*)"
_IDENTIFIERS = r"[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*"
_FULL = re.compile(
    r"(" + _NUMBER + r")\.(" + _NUMBER + r")\.(" + _NUMBER + r")"
    r"(?:-(" + _IDENTIFIERS + r"))?(?:\+(" + _IDENTIFIERS + r"))?"
)
_PART = re.compile(_NUMBER + r"|[xX*]")
_COMPARATOR = re.compile(r"(<=|>=|[<>=~^])?(.*)")


@dataclass(frozen=True)
class _Version:
    core: tuple
    prerelease: tuple = ()

    @property
    def key(self):
        pre = (0, tuple((0, int(p)) if p.isascii() and p.isdigit()
                        else (1, p) for p in self.prerelease))
        return self.core + (pre if self.prerelease else (1,),)


def _full_version(value):
    match = _FULL.fullmatch(value)
    if not match:
        raise ValueError("Invalid version: {!r}".format(value))
    prerelease = tuple(match[4].split(".")) if match[4] else ()
    if any(p.isdigit() and len(p) > 1 and p[0] == "0" for p in prerelease):
        raise ValueError("Numeric prerelease identifiers cannot have leading zeros")
    return _Version(tuple(int(match[i]) for i in (1, 2, 3)), prerelease)


def _parse_version(value):
    if not isinstance(value, str):
        raise ValueError("Version must be a string")
    value = value.strip()
    if value.startswith(("v", "=")):
        value = value[1:]
    return _full_version(value)


def _operand(value):
    """Return the zero-filled version and number of specified components."""
    if value.startswith("v"):
        value = value[1:]
    if _FULL.fullmatch(value):
        return _full_version(value), 3
    parts = value.split(".")
    if not 1 <= len(parts) <= 3 or any(not _PART.fullmatch(p) for p in parts):
        raise ValueError("Invalid range version: {!r}".format(value))
    numbers = []
    wildcard = False
    for part in parts:
        if part in ("x", "X", "*"):
            wildcard = True
        elif wildcard:
            raise ValueError("A numeric component cannot follow a wildcard")
        else:
            numbers.append(int(part))
    return _Version(tuple(numbers + [0] * (3 - len(numbers)))), len(numbers)


def _upper(version, component):
    core = list(version.core)
    core[component] += 1
    for i in range(component + 1, 3):
        core[i] = 0
    return _Version(tuple(core), ("0",))


def _expand(operator, version, count):
    if operator in ("~", "^"):
        if count == 0:
            return [(">=", _Version((0, 0, 0)))]
        if operator == "~":
            component = 0 if count == 1 else 1
        else:
            # Missing components allow that component's entire range, even
            # when every specified component is zero.
            component = next((i for i in range(count) if version.core[i]), count - 1)
        return [(">=", version), ("<", _upper(version, component))]
    if count == 3:
        return [(operator or "=", version)]
    if count == 0:
        if operator in ("<", ">"):
            return [("<", _Version((0, 0, 0), ("0",)))]
        return [(">=", _Version((0, 0, 0)))]
    if operator == ">":
        upper = _upper(version, count - 1)
        return [(">=", _Version(upper.core))]
    if operator == ">=":
        return [(">=", version)]
    if operator == "<":
        return [("<", _Version(version.core, ("0",)))]
    if operator == "<=":
        return [("<", _upper(version, count - 1))]
    return [(">=", version), ("<", _upper(version, count - 1))]


def _parse_range(range_):
    if not isinstance(range_, str):
        raise ValueError("Range must be a string")
    sets = []
    for source in range_.split("||"):
        tokens = source.split()
        comparators = []
        prerelease_cores = set()
        i = 0
        while i < len(tokens):
            if i + 1 < len(tokens) and tokens[i + 1] == "-":
                if i + 2 >= len(tokens):
                    raise ValueError("Missing hyphen range endpoint")
                left, left_count = _operand(tokens[i])
                right, right_count = _operand(tokens[i + 2])
                if left.prerelease:
                    prerelease_cores.add(left.core)
                if right.prerelease:
                    prerelease_cores.add(right.core)
                comparators.append((">=", left))
                if right_count == 3:
                    comparators.append(("<=", right))
                elif right_count:
                    comparators.append(("<", _upper(right, right_count - 1)))
                i += 3
                continue
            operator, operand = _COMPARATOR.fullmatch(tokens[i]).groups()
            if not operand:
                i += 1
                if i >= len(tokens):
                    raise ValueError("Missing comparator version")
                operand = tokens[i]
            version, count = _operand(operand)
            if version.prerelease:
                prerelease_cores.add(version.core)
            comparators.extend(_expand(operator, version, count))
            i += 1
        sets.append((comparators, prerelease_cores))
    return sets


def _matches(version, sets):
    for comparators, prerelease_cores in sets:
        if version.prerelease and version.core not in prerelease_cores:
            continue
        for operator, bound in comparators:
            a, b = version.key, bound.key
            if not {"=": a == b, "<": a < b, "<=": a <= b,
                    ">": a > b, ">=": a >= b}[operator]:
                break
        else:
            return True
    return False


def satisfies(version, range_):
    """Return whether version satisfies range_; reject invalid inputs."""
    parsed = _parse_version(version)
    return _matches(parsed, _parse_range(range_))


def max_satisfying(versions, range_):
    """Return the first highest matching original string, skipping bad versions."""
    sets = _parse_range(range_)
    best = None
    best_key = None
    for original in versions:
        try:
            version = _parse_version(original)
        except ValueError:
            continue
        if _matches(version, sets) and (best_key is None or version.key > best_key):
            best, best_key = original, version.key
    return best
