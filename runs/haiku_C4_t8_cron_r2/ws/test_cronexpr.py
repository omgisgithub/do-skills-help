"""Tests for next_run in cronexpr.py, following the spec in TASK.md."""

from datetime import datetime

import pytest

from cronexpr import next_run


@pytest.mark.parametrize(
    ("expr", "after", "expected"),
    [
        ("*/15 * * * *", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
        ("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0), datetime(2026, 3, 9, 9, 0)),
        ("0 0 29 2 *", datetime(2026, 3, 1), datetime(2028, 2, 29, 0, 0)),
        ("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0), datetime(2026, 1, 2, 4, 30)),
    ],
)
def test_next_run_spec_examples_return_expected(expr, after, expected):
    # Arrange / Act
    result = next_run(expr, after)

    # Assert
    assert result == expected


def test_next_run_seconds_in_after_skips_to_next_minute():
    # Arrange
    after = datetime(2026, 3, 4, 12, 0, 30)

    # Act
    result = next_run("* * * * *", after)

    # Assert
    assert result == datetime(2026, 3, 4, 12, 1)


def test_next_run_exact_match_is_strictly_later():
    # Arrange
    after = datetime(2026, 3, 4, 12, 0, 0)

    # Act
    result = next_run("0 12 * * *", after)

    # Assert
    assert result == datetime(2026, 3, 5, 12, 0)


def test_next_run_impossible_date_raises_value_error():
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        next_run("0 0 30 2 *", datetime(2026, 1, 1))


@pytest.mark.parametrize(
    "expr",
    [
        "* * * *",
        "* * * * * *",
        "60 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * * 13 *",
        "* * * * 8",
        "*/0 * * * *",
        "5-1 * * * *",
        "FRI-MON * * * *",
        "* * * * JAN",
        "* * * 0 *",
        "@reboot",
        "1,,2 * * * *",
        "1+2 * * * *",
        "MON * * * *",
    ],
)
def test_next_run_invalid_expression_raises_value_error(expr):
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        next_run(expr, datetime(2026, 1, 1))


def test_next_run_non_string_expr_raises_type_error():
    # Arrange / Act / Assert
    with pytest.raises(TypeError):
        next_run(None, datetime(2026, 1, 1))  # type: ignore[arg-type]  # testing runtime check


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("@yearly", datetime(2027, 1, 1, 0, 0)),
        ("@ANNUALLY", datetime(2027, 1, 1, 0, 0)),
        ("@monthly", datetime(2026, 2, 1, 0, 0)),
        ("@weekly", datetime(2026, 1, 4, 0, 0)),
        ("@daily", datetime(2026, 1, 2, 0, 0)),
        ("@midnight", datetime(2026, 1, 2, 0, 0)),
        ("@hourly", datetime(2026, 1, 1, 1, 0)),
    ],
)
def test_next_run_shortcut_returns_expected(expr, expected):
    # Arrange
    after = datetime(2026, 1, 1, 0, 0)

    # Act
    result = next_run(expr, after)

    # Assert
    assert result == expected


@pytest.mark.parametrize("dow", ["0", "7", "SUN"])
def test_next_run_sunday_zero_and_seven_are_equivalent(dow):
    # Arrange
    after = datetime(2026, 3, 4, 0, 0)  # Wednesday

    # Act
    result = next_run(f"0 0 * * {dow}", after)

    # Assert
    assert result == datetime(2026, 3, 8, 0, 0)


def test_next_run_day_fields_both_restricted_matches_either():
    # Arrange: the 13th or any Friday
    after = datetime(2026, 3, 1, 0, 0)

    # Act
    result = next_run("0 0 13 * FRI", after)

    # Assert
    assert result == datetime(2026, 3, 6, 0, 0)


def test_next_run_only_day_of_month_restricted_ignores_weekday():
    # Arrange: weekday is unrestricted, so only the 13th counts
    after = datetime(2026, 3, 6, 0, 0)

    # Act
    result = next_run("0 0 13 * *", after)

    # Assert
    assert result == datetime(2026, 3, 13, 0, 0)


def test_next_run_step_on_day_of_month_counts_as_restricted():
    # Arrange: */2 is restricted, so the odd-numbered 7th matches even though it is a Saturday
    after = datetime(2026, 3, 6, 0, 0)  # Friday, even day of month

    # Act
    result = next_run("0 0 */2 * FRI", after)

    # Assert
    assert result == datetime(2026, 3, 7, 0, 0)


def test_next_run_range_with_step_and_names_selects_expected_hours():
    # Arrange
    after = datetime(2026, 3, 4, 9, 30)

    # Act
    result = next_run("0 9-17/4 * * *", after)

    # Assert
    assert result == datetime(2026, 3, 4, 13, 0)


def test_next_run_single_value_with_step_runs_to_field_maximum():
    # Arrange
    after = datetime(2026, 3, 4, 0, 0)

    # Act
    result = next_run("50/5 * * * *", after)

    # Assert
    assert result == datetime(2026, 3, 4, 0, 50)


def test_next_run_lowercase_names_are_accepted():
    # Arrange
    after = datetime(2026, 3, 6, 9, 0)

    # Act
    result = next_run("0 9 * jan-dec mon-fri", after)

    # Assert
    assert result == datetime(2026, 3, 9, 9, 0)


def test_next_run_tabs_and_extra_spaces_are_separators():
    # Arrange
    after = datetime(2026, 3, 4, 10, 7)

    # Act
    result = next_run("  */15\t*  *\t* *  ", after)

    # Assert
    assert result == datetime(2026, 3, 4, 10, 15)
