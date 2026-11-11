"""Tests for cronexpr.next_run, using only the standard library."""

import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunExamplesTests(unittest.TestCase):
    def test_next_run_spec_examples_return_expected_minute(self) -> None:
        cases = [
            ("*/15 * * * *", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
            ("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0), datetime(2026, 3, 9, 9, 0)),
            ("0 0 29 2 *", datetime(2026, 3, 1), datetime(2028, 2, 29, 0, 0)),
            ("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0), datetime(2026, 1, 2, 4, 30)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)


class StrictlyLaterTests(unittest.TestCase):
    def test_next_run_seconds_in_after_drop_to_next_minute(self) -> None:
        result = next_run("* * * * *", datetime(2026, 1, 1, 12, 0, 30))

        self.assertEqual(result, datetime(2026, 1, 1, 12, 1))

    def test_next_run_exact_match_returns_following_match(self) -> None:
        result = next_run("0 12 * * *", datetime(2026, 1, 1, 12, 0))

        self.assertEqual(result, datetime(2026, 1, 2, 12, 0))

    def test_next_run_microseconds_in_after_drop_to_next_minute(self) -> None:
        result = next_run("* * * * *", datetime(2026, 1, 1, 12, 0, 0, 1))

        self.assertEqual(result, datetime(2026, 1, 1, 12, 1))

    def test_next_run_result_has_zero_seconds_and_microseconds(self) -> None:
        result = next_run("* * * * *", datetime(2026, 1, 1, 12, 0, 45, 999))

        self.assertEqual((result.second, result.microsecond), (0, 0))


class ShortcutTests(unittest.TestCase):
    def test_next_run_shortcut_matches_expanded_expression(self) -> None:
        cases = [
            ("@yearly", "0 0 1 1 *"),
            ("@annually", "0 0 1 1 *"),
            ("@monthly", "0 0 1 * *"),
            ("@weekly", "0 0 * * 0"),
            ("@daily", "0 0 * * *"),
            ("@midnight", "0 0 * * *"),
            ("@hourly", "0 * * * *"),
        ]
        after = datetime(2026, 3, 4, 10, 7)
        for shortcut, expanded in cases:
            with self.subTest(shortcut=shortcut):
                self.assertEqual(next_run(shortcut, after), next_run(expanded, after))

    def test_next_run_shortcut_is_case_insensitive(self) -> None:
        result = next_run("@DAILY", datetime(2026, 3, 4, 10, 7))

        self.assertEqual(result, datetime(2026, 3, 5, 0, 0))

    def test_next_run_weekly_shortcut_fires_on_sunday(self) -> None:
        # 2026-03-04 is a Wednesday; the next Sunday is 2026-03-08.
        result = next_run("@weekly", datetime(2026, 3, 4, 10, 7))

        self.assertEqual(result, datetime(2026, 3, 8, 0, 0))


class FieldSyntaxTests(unittest.TestCase):
    def test_next_run_range_with_step_starts_at_range_start(self) -> None:
        result = next_run("10-30/10 * * * *", datetime(2026, 1, 1, 0, 10))

        self.assertEqual(result, datetime(2026, 1, 1, 0, 20))

    def test_next_run_single_value_with_step_runs_to_field_maximum(self) -> None:
        result = next_run("5/20 * * * *", datetime(2026, 1, 1, 0, 25))

        self.assertEqual(result, datetime(2026, 1, 1, 0, 45))

    def test_next_run_wildcard_step_starts_at_field_minimum(self) -> None:
        result = next_run("*/2 * * * *", datetime(2026, 1, 1, 0, 1))

        self.assertEqual(result, datetime(2026, 1, 1, 0, 2))

    def test_next_run_comma_list_picks_earliest_value(self) -> None:
        result = next_run("5,40 * * * *", datetime(2026, 1, 1, 0, 6))

        self.assertEqual(result, datetime(2026, 1, 1, 0, 40))

    def test_next_run_month_name_is_case_insensitive(self) -> None:
        result = next_run("0 0 1 jan-feb *", datetime(2026, 1, 15))

        self.assertEqual(result, datetime(2026, 2, 1, 0, 0))

    def test_next_run_tabs_and_repeated_spaces_separate_fields(self) -> None:
        result = next_run("  0\t\t 9   *  *\t*  ", datetime(2026, 1, 1, 8, 0))

        self.assertEqual(result, datetime(2026, 1, 1, 9, 0))

    def test_next_run_day_of_week_seven_is_sunday(self) -> None:
        # 2026-03-04 is a Wednesday; 7 and 0 both mean Sunday.
        result = next_run("0 0 * * 7", datetime(2026, 3, 4, 10, 7))

        self.assertEqual(result, datetime(2026, 3, 8, 0, 0))

    def test_next_run_day_of_week_range_ending_in_seven_includes_sunday(self) -> None:
        # 5-7 is Friday, Saturday, Sunday.
        result = next_run("0 0 * * 5-7", datetime(2026, 3, 4, 10, 7))

        self.assertEqual(result, datetime(2026, 3, 6, 0, 0))

    def test_next_run_day_of_week_name_range_ending_in_seven_is_sat_and_sun(self) -> None:
        result = next_run("0 0 * * SAT-7", datetime(2026, 3, 4, 10, 7))

        self.assertEqual(result, datetime(2026, 3, 7, 0, 0))


class DayMatchingTests(unittest.TestCase):
    def test_next_run_both_day_fields_restricted_matches_either(self) -> None:
        # Day 15 of the month, or any Friday. 2026-01-02 is a Friday.
        result = next_run("0 0 15 * FRI", datetime(2026, 1, 1, 12, 0))

        self.assertEqual(result, datetime(2026, 1, 2, 0, 0))

    def test_next_run_only_day_of_month_restricted_ignores_weekday(self) -> None:
        result = next_run("0 0 3 * *", datetime(2026, 1, 1, 12, 0))

        self.assertEqual(result, datetime(2026, 1, 3, 0, 0))

    def test_next_run_only_day_of_week_restricted_ignores_day_of_month(self) -> None:
        # 2026-01-05 is a Monday.
        result = next_run("0 0 * * MON", datetime(2026, 1, 1, 12, 0))

        self.assertEqual(result, datetime(2026, 1, 5, 0, 0))

    def test_next_run_wildcard_step_in_day_of_month_counts_as_restricted(self) -> None:
        # */2 means days 1, 3, 5, ... and counts as restricted, so the day-of-month
        # and weekday fields combine with OR. Jan 1 matches on day-of-month but
        # its 00:00 slot has already passed, so the next match is Friday Jan 2.
        result = next_run("0 0 */2 * FRI", datetime(2026, 1, 1, 12, 0))

        self.assertEqual(result, datetime(2026, 1, 2, 0, 0))

    def test_next_run_leap_day_skips_to_next_leap_year(self) -> None:
        result = next_run("0 0 29 2 *", datetime(2026, 3, 1))

        self.assertEqual(result, datetime(2028, 2, 29, 0, 0))


class NoMatchTests(unittest.TestCase):
    def test_next_run_impossible_date_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            next_run("0 0 30 2 *", datetime(2026, 1, 1))

    def test_next_run_leap_day_beyond_five_years_raises_value_error(self) -> None:
        # Feb 29 in 2100 does not exist, and the next one is 2104.
        with self.assertRaises(ValueError):
            next_run("0 0 29 2 *", datetime(2096, 3, 1))


class InvalidExpressionTests(unittest.TestCase):
    def test_next_run_non_string_expr_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            next_run(None, datetime(2026, 1, 1))  # type: ignore[arg-type]  # testing bad input

    def test_next_run_invalid_expressions_raise_value_error(self) -> None:
        cases = [
            "",
            "* * * *",
            "* * * * * *",
            "60 * * * *",
            "* 24 * * *",
            "* * 0 * *",
            "* * 32 * *",
            "* * * 0 *",
            "* * * 13 *",
            "* * * * 8",
            "*/0 * * * *",
            "*/ * * * *",
            "1/2/3 * * * *",
            "5-3 * * * *",
            "* * * * FRI-MON",
            "* * * * SAT-SUN",
            "1,,2 * * * *",
            "1, * * * *",
            "JAN * * * *",
            "* * * FRI *",
            "* * * * JAN",
            "1-2-3 * * * *",
            "@sometimes",
            "0\n0 * * *",
            "*/-1 * * * *",
            "+5 * * * *",
            "1.5 * * * *",
        ]
        for expr in cases:
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    next_run(expr, datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
