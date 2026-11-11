"""Tests for semver_range, driven by the examples in TASK.md."""

import pytest

from semver_range import max_satisfying, satisfies


@pytest.mark.parametrize(
    "version, range_",
    [
        ("1.2.3", ">=1.2.3 <2.0.0"),
        ("1.2.3", ">= 1.2.3"),
        ("v1.2.3", "1.2.3"),
        ("=1.2.3", "1.2.3"),
        ("  1.2.3  ", "1.2.3"),
        ("1.2.3+build.5", "1.2.3"),
        ("1.2.3", "=1.2.3"),
        ("1.2.9", "1.2"),
        ("1.2.3", "1.2.x"),
        ("1.2.3", "1.2.*"),
        ("1.9.9", "1"),
        ("1.9.9", "1.x.x"),
        ("0.0.0", "*"),
        ("9.9.9", "x"),
        ("9.9.9", "X"),
        ("1.3.0", ">1.2"),
        ("2.0.0", ">1"),
        ("1.2.0", ">=1.2"),
        ("1.1.9", "<1.2"),
        ("1.2.9", "<=1.2"),
        ("1.9.9", "<=1"),
        ("1.2.0", "=1.2"),
        ("5.0.0", ">=*"),
        ("5.0.0", "<=*"),
        ("1.2.9", "~1.2.3"),
        ("1.2.0", "~1.2"),
        ("1.9.0", "~1"),
        ("0.2.9", "~0.2.3"),
        ("1.9.9", "^1.2.3"),
        ("0.2.9", "^0.2.3"),
        ("0.0.3", "^0.0.3"),
        ("1.2.0", "^1.2"),
        ("1.2.5", "^1.2.x"),
        ("1.9.9", "^1"),
        ("0.0.9", "^0.0"),
        ("0.9.9", "^0.x"),
        ("0.9.9", "^0"),
        ("0.1.9", "^0.1"),
        ("1.2.3", "1.2.3 - 2.3.4"),
        ("2.3.4", "1.2.3 - 2.3.4"),
        ("2.0.0", "1.2 - 2.3.4"),
        ("2.3.9", "1.2.3 - 2.3"),
        ("2.9.9", "1.2.3 - 2"),
        ("1.0.0", "1.2.3 || 1.0.0"),
        ("1.2.3", "||1.2.3"),
        ("9.0.0", ""),
        ("9.0.0", "   "),
        ("9.0.0", "1.0.0 ||"),
    ],
)
def test_satisfies_in_range_returns_true(version: str, range_: str) -> None:
    # Arrange / Act
    result = satisfies(version, range_)

    # Assert
    assert result is True


@pytest.mark.parametrize(
    "version, range_",
    [
        ("1.3.0", "~1.2.3"),
        ("2.0.0", "^1.2.3"),
        ("0.3.0", "^0.2.3"),
        ("0.0.4", "^0.0.3"),
        ("2.0.0", "^1.2"),
        ("1.0.0", "^0.0"),
        ("1.0.0", "^0.x"),
        ("1.0.0", "^0"),
        ("0.2.0", "^0.1"),
        ("1.3.0", "1.2"),
        ("1.2.9", ">1.2"),
        ("1.2.9", ">=1.3"),
        ("1.2.0", "<1.2"),
        ("1.3.0", "<=1.2"),
        ("2.0.0", "<=1"),
        ("3.0.0", "1.2.3 - 2.3.4"),
        ("2.3.4-alpha", "1.2.3 - 2.3.4"),
        ("2.4.0", "1.2.3 - 2.3"),
        ("3.0.0", "1.2.3 - 2"),
        ("1.1.9", "1.2 - 2.3.4"),
        ("9.9.9", ">*"),
        ("9.9.9", "<*"),
        ("0.0.0-alpha", ">*"),
        ("1.2.3", "<1.2.3"),
        ("1.2.3", ">1.2.3"),
        ("1.2.3", "1.2.4 || 1.2.5"),
    ],
)
def test_satisfies_out_of_range_returns_false(version: str, range_: str) -> None:
    # Arrange / Act
    result = satisfies(version, range_)

    # Assert
    assert result is False


@pytest.mark.parametrize(
    "version, range_, expected",
    [
        ("1.2.4-alpha", "^1.2.3", False),
        ("1.0.0-rc.1", "*", False),
        ("1.2.4-alpha", ">=1.2.3 <2.0.0-0", False),
        ("1.2.4-alpha", ">=1.2.0 <1.3.0", False),
        ("2.0.0-alpha", "1.2.3 - 2.3.4", False),
        ("1.2.3-beta.4", "^1.2.3-beta.2", True),
        ("1.2.3-beta.4", "~1.2.3-beta.2", True),
        ("1.2.3-alpha", "1.2.3-alpha - 2.3.4", True),
    ],
)
def test_satisfies_prerelease_rule_follows_spec(version: str, range_: str, expected: bool) -> None:
    # Arrange / Act
    result = satisfies(version, range_)

    # Assert
    assert result is expected


@pytest.mark.parametrize(
    "lower, higher",
    [
        ("1.0.0-alpha", "1.0.0-alpha.1"),
        ("1.0.0-alpha.1", "1.0.0-alpha.beta"),
        ("1.0.0-alpha.beta", "1.0.0-beta"),
        ("1.0.0-beta", "1.0.0-beta.2"),
        ("1.0.0-beta.2", "1.0.0-beta.11"),
        ("1.0.0-beta.11", "1.0.0-rc.1"),
        ("1.0.0-rc.1", "1.0.0"),
        ("1.0.0-1", "1.0.0-a"),
    ],
)
def test_max_satisfying_precedence_orders_prereleases(lower: str, higher: str) -> None:
    # Arrange
    versions = [higher, lower]

    # Act
    result = max_satisfying(versions, ">=1.0.0-0")

    # Assert
    assert result == higher


@pytest.mark.parametrize(
    "version",
    [
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2",
        "1.2.3.4",
        "1.2.3-",
        "1.2.3-01",
        "1.2.3-alpha..1",
        "1.2.3+",
        "1.2.3+build..1",
        "v",
        "v v1.2.3",
        "v= 1.2.3",
        "1.2.x",
        "",
    ],
)
def test_satisfies_invalid_version_raises_value_error(version: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        satisfies(version, "*")


@pytest.mark.parametrize(
    "range_",
    [
        "~>1.2",
        ">=1.2.3 -",
        "- 1.2.3",
        "1.2.3 -2.3.4",
        "1.2.3 - 2.3.4 - 3.0.0",
        "1.2.3 - *",
        "1.2.x.x.x",
        "1.x.3",
        "^",
        ">=a.b.c",
        ">",
        ">=",
        "> = 1.2.3",
        ">==1.2.3",
        "1.2.3.4",
        "1.2.3 <",
        "~ 1.2",
        "1.2.3-",
    ],
)
def test_satisfies_invalid_range_raises_value_error(range_: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        satisfies("1.2.3", range_)


def test_max_satisfying_returns_highest_matching_version_as_given() -> None:
    # Arrange
    versions = ["1.2.3", "1.10.0", "v1.9.9", "2.0.0", "1.5.0"]

    # Act
    result = max_satisfying(versions, "^1.2.3")

    # Assert
    assert result == "1.10.0"


def test_max_satisfying_returns_none_when_nothing_matches() -> None:
    # Arrange
    versions = ["0.1.0", "2.0.0"]

    # Act
    result = max_satisfying(versions, "1.x")

    # Assert
    assert result is None


def test_max_satisfying_skips_invalid_entries() -> None:
    # Arrange
    versions = ["not-a-version", "1.2.3", "1.2.3.4", "1.2.4"]

    # Act
    result = max_satisfying(versions, "1.2")

    # Assert
    assert result == "1.2.4"


def test_max_satisfying_equal_precedence_returns_first_entry() -> None:
    # Arrange
    versions = ["1.2.3+build.2", "1.2.3", "1.2.3+build.1"]

    # Act
    result = max_satisfying(versions, "1.2.3")

    # Assert
    assert result == "1.2.3+build.2"


def test_max_satisfying_honours_prerelease_rule() -> None:
    # Arrange
    versions = ["1.2.4-alpha", "1.2.2"]

    # Act
    result = max_satisfying(versions, "^1.2.3")

    # Assert
    assert result is None


def test_max_satisfying_invalid_range_raises_value_error() -> None:
    # Arrange
    versions = ["1.2.3"]

    # Act / Assert
    with pytest.raises(ValueError):
        max_satisfying(versions, "~>1.2")


def test_max_satisfying_empty_versions_returns_none() -> None:
    # Arrange / Act
    result = max_satisfying([], "*")

    # Assert
    assert result is None
