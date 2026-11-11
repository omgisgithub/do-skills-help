"""npm-style version range matching. See TASK.md for the exact spec."""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUMERIC = r"(?:0|[1-9][0-9]*)"
_VERSION_RE = re.compile(
    rf"^({_NUMERIC})\.({_NUMERIC})\.({_NUMERIC})"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_NUMERIC_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")
_WILDCARDS = frozenset(("*", "x", "X"))
_OPERATORS = ("<=", ">=", "<", ">", "=", "~", "^")


@dataclass(frozen=True)
class _Version:
    """A parsed semantic version, excluding the build metadata."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[tuple[bool, int | str], ...] = ()

    def precedence_key(self) -> tuple[object, ...]:
        """Return a key that orders versions by SemVer precedence."""
        core = (self.major, self.minor, self.patch)
        if not self.prerelease:
            return (*core, 1)
        identifiers = tuple(
            (0, value) if is_numeric else (1, value)
            for is_numeric, value in self.prerelease
        )
        return (*core, 0, identifiers)

    def has_prerelease(self) -> bool:
        """Return whether the version contains a prerelease tag."""
        return bool(self.prerelease)


@dataclass(frozen=True)
class _Comparator:
    """A single normalized comparator in a comparator set."""

    op: str
    version: _Version
    written_prerelease: bool = False


@dataclass(frozen=True)
class _Atom:
    """A full version or an X-range partial version."""

    version: _Version | None
    numbers: tuple[int, ...]


def _strip_prefix(text: str) -> str:
    """Strip surrounding whitespace and one optional ``v`` or ``=`` prefix."""
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    stripped = text.strip()
    if stripped[:1] in ("v", "="):
        stripped = stripped[1:]
    return stripped


def _parse_version_body(text: str) -> _Version:
    """Parse a complete version body that has already been prefix-stripped."""
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid version: {text!r}")

    major, minor, patch, prerelease_text, _build = match.groups()
    identifiers: list[tuple[bool, int | str]] = []
    if prerelease_text is not None:
        for identifier in prerelease_text.split("."):
            if identifier.isdigit():
                if len(identifier) > 1 and identifier[0] == "0":
                    raise ValueError(f"invalid prerelease identifier: {identifier!r}")
                identifiers.append((True, int(identifier)))
            else:
                identifiers.append((False, identifier))

    return _Version(int(major), int(minor), int(patch), tuple(identifiers))


def _parse_version(text: str) -> _Version:
    """Parse a complete version string."""
    return _parse_version_body(_strip_prefix(text))


def _parse_partial_body(text: str) -> tuple[int, ...]:
    """Parse an X-range partial version body into its numeric components."""
    if "-" in text or "+" in text:
        raise ValueError(f"invalid partial version: {text!r}")

    parts = text.split(".")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"invalid partial version: {text!r}")

    numbers: list[int] = []
    wildcard_seen = False
    for part in parts:
        if part in _WILDCARDS:
            wildcard_seen = True
            continue
        if wildcard_seen or _NUMERIC_RE.fullmatch(part) is None:
            raise ValueError(f"invalid partial version: {text!r}")
        numbers.append(int(part))

    return tuple(numbers)


def _parse_atom(text: str) -> _Atom:
    """Parse a comparator operand as either a full or partial version."""
    body = _strip_prefix(text)
    try:
        version = _parse_version_body(body)
    except ValueError:
        numbers = _parse_partial_body(body)
        return _Atom(None, numbers)
    return _Atom(version, (version.major, version.minor, version.patch))


def _filled_version(
    numbers: tuple[int, ...],
    prerelease: tuple[tuple[bool, int | str], ...] = (),
) -> _Version:
    """Fill a partial version with zeroes to form a complete lower bound."""
    padded = (*numbers, 0, 0, 0)[:3]
    return _Version(padded[0], padded[1], padded[2], prerelease)


def _next_version(
    numbers: tuple[int, ...],
    prerelease: tuple[tuple[bool, int | str], ...] = (),
) -> _Version:
    """Return the exclusive upper bound after the given partial prefix."""
    if len(numbers) == 1:
        return _Version(numbers[0] + 1, 0, 0, prerelease)
    return _Version(numbers[0], numbers[1] + 1, 0, prerelease)


def _upper_after(numbers: tuple[int, ...]) -> _Version | None:
    """Return the exclusive upper bound after a partial prefix, if any."""
    if not numbers:
        return None
    return _next_version(numbers, ((True, 0),))


def _caret_upper(numbers: tuple[int, ...]) -> _Version:
    """Return the exclusive caret upper bound for a partial version."""
    if len(numbers) == 1:
        return _Version(numbers[0] + 1, 0, 0, ((True, 0),))

    major, minor = numbers[0], numbers[1]
    if major > 0:
        return _Version(major + 1, 0, 0, ((True, 0),))
    if minor > 0 or len(numbers) == 2:
        return _Version(0, minor + 1, 0, ((True, 0),))
    return _Version(0, 0, numbers[2] + 1, ((True, 0),))


def _desugar(op: str, atom: _Atom) -> list[_Comparator] | None:
    """Turn one comparator into zero or more normalized comparators."""
    version = atom.version
    numbers = atom.numbers
    exact = op in ("", "=")

    if exact:
        if version is not None:
            return [_Comparator("=", version, version.has_prerelease())]
        if not numbers:
            return [_Comparator(">=", _Version(0, 0, 0))]
        return [
            _Comparator(">=", _filled_version(numbers)),
            _Comparator("<", _next_version(numbers, ((True, 0),))),
        ]

    if op == ">=":
        if version is not None:
            return [_Comparator(">=", version, version.has_prerelease())]
        if not numbers:
            return [_Comparator(">=", _Version(0, 0, 0))]
        return [_Comparator(">=", _filled_version(numbers))]

    if op == ">":
        if version is not None:
            return [_Comparator(">", version, version.has_prerelease())]
        if not numbers:
            return None
        return [_Comparator(">=", _next_version(numbers))]

    if op == "<":
        if version is not None:
            return [_Comparator("<", version, version.has_prerelease())]
        if not numbers:
            return None
        return [_Comparator("<", _filled_version(numbers, ((True, 0),)))]

    if op == "<=":
        if version is not None:
            return [_Comparator("<=", version, version.has_prerelease())]
        if not numbers:
            return [_Comparator(">=", _Version(0, 0, 0))]
        return [_Comparator("<", _next_version(numbers, ((True, 0),)))]

    if op == "~":
        if not numbers:
            return [_Comparator(">=", _Version(0, 0, 0))]
        lower = version if version is not None else _filled_version(numbers)
        upper = _next_version(numbers, ((True, 0),))
        written_prerelease = version is not None and version.has_prerelease()
        return [
            _Comparator(">=", lower, written_prerelease),
            _Comparator("<", upper),
        ]

    if op == "^":
        if not numbers:
            return [_Comparator(">=", _Version(0, 0, 0))]
        lower = version if version is not None else _filled_version(numbers)
        written_prerelease = version is not None and version.has_prerelease()
        return [
            _Comparator(">=", lower, written_prerelease),
            _Comparator("<", _caret_upper(numbers)),
        ]

    raise ValueError(f"invalid operator: {op!r}")


def _hyphen(left: _Atom, right: _Atom) -> list[_Comparator]:
    """Turn a hyphen range into lower and upper comparators."""
    comparators: list[_Comparator] = []

    if left.version is not None:
        comparators.append(
            _Comparator(">=", left.version, left.version.has_prerelease())
        )
    elif left.numbers:
        comparators.append(_Comparator(">=", _filled_version(left.numbers)))
    else:
        comparators.append(_Comparator(">=", _Version(0, 0, 0)))

    if right.version is not None:
        comparators.append(
            _Comparator("<=", right.version, right.version.has_prerelease())
        )
    else:
        upper = _upper_after(right.numbers)
        if upper is not None:
            comparators.append(_Comparator("<", upper))

    return comparators


def _is_plain_atom_token(token: str) -> bool:
    """Return whether a token starts a bare version rather than an operator."""
    if token == "-":
        return False
    # A leading "=" is ambiguous: it can be the exact operator or a version
    # prefix. Only treat it as a prefix when a hyphen range follows.
    if token.startswith("=") and len(token) > 1:
        return True
    return not any(token.startswith(op) for op in _OPERATORS)


def _split_operator(tokens: list[str], index: int) -> tuple[str, str, int]:
    """Split an operator token, joining a following operand when needed."""
    token = tokens[index]
    for op in _OPERATORS:
        if token.startswith(op):
            body = token[len(op) :]
            if body:
                return op, body, 1
            if index + 1 >= len(tokens):
                raise ValueError("operator without a version")
            return op, tokens[index + 1], 2
    return "", token, 1


def _parse_set(text: str) -> list[_Comparator] | None:
    """Parse a comparator set, returning ``None`` when it is unsatisfiable."""
    tokens = text.split()
    if not tokens:
        return [_Comparator(">=", _Version(0, 0, 0))]

    comparators: list[_Comparator] = []
    impossible = False
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token == "-":
            raise ValueError("hyphen range is missing an endpoint")

        if (
            _is_plain_atom_token(token)
            and index + 2 < len(tokens)
            and tokens[index + 1] == "-"
        ):
            left = _parse_atom(token)
            right = _parse_atom(tokens[index + 2])
            comparators.extend(_hyphen(left, right))
            index += 3
            continue

        op, body, consumed = _split_operator(tokens, index)
        atom = _parse_atom(body)
        expanded = _desugar(op, atom)
        if expanded is None:
            impossible = True
        else:
            comparators.extend(expanded)
        index += consumed

    if impossible:
        return None
    return comparators


def _parse_range(range_: str) -> list[list[_Comparator] | None]:
    """Parse a range into comparator sets, or raise ``ValueError``."""
    if not isinstance(range_, str):
        raise ValueError("range must be a string")
    return [_parse_set(part) for part in range_.split("||")]


def _matches(comparator: _Comparator, version: _Version) -> bool:
    """Return whether one comparator holds for a version."""
    left = version.precedence_key()
    right = comparator.version.precedence_key()

    if comparator.op == "=":
        return left == right
    if comparator.op == "<":
        return left < right
    if comparator.op == "<=":
        return left <= right
    if comparator.op == ">":
        return left > right
    if comparator.op == ">=":
        return left >= right
    return False


def _satisfies_set(comparators: list[_Comparator], version: _Version) -> bool:
    """Return whether a version satisfies one comparator set."""
    if not all(_matches(comparator, version) for comparator in comparators):
        return False

    if version.has_prerelease():
        core = (version.major, version.minor, version.patch)
        return any(
            comparator.written_prerelease
            and (
                comparator.version.major,
                comparator.version.minor,
                comparator.version.patch,
            )
            == core
            for comparator in comparators
        )

    return True


def satisfies(version: str, range_: str) -> bool:
    """Return whether a version satisfies an npm-style range.

    Args:
        version: The version to test.
        range_: The range expression to test against.

    Returns:
        True when the version satisfies at least one comparator set.

    Raises:
        ValueError: If the version or the range is invalid.
    """
    parsed_version = _parse_version(version)
    sets = _parse_range(range_)
    return any(
        comparator_set is not None and _satisfies_set(comparator_set, parsed_version)
        for comparator_set in sets
    )


def max_satisfying(versions: list[str], range_: str) -> str | None:
    """Return the highest version string satisfying a range.

    Invalid entries in ``versions`` are skipped. When multiple entries have
    equal precedence, the first one in the list wins.

    Args:
        versions: Candidate version strings, returned unchanged when selected.
        range_: The range expression to test against.

    Returns:
        The original highest satisfying version string, or ``None``.

    Raises:
        ValueError: If the range is invalid.
    """
    sets = _parse_range(range_)
    best_version: str | None = None
    best_key: tuple[object, ...] | None = None

    for raw_version in versions:
        if not isinstance(raw_version, str):
            continue
        try:
            parsed_version = _parse_version(raw_version)
        except ValueError:
            continue

        if not any(
            comparator_set is not None
            and _satisfies_set(comparator_set, parsed_version)
            for comparator_set in sets
        ):
            continue

        key = parsed_version.precedence_key()
        if best_key is None or key > best_key:
            best_version = raw_version
            best_key = key

    return best_version
