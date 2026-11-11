"""Test cron parsing and bounded scheduling with the standard library."""

import unittest
from datetime import datetime

from cronexpr import next_run


class CronExpressionTests(unittest.TestCase):
    """Check expression syntax and calendar matching."""

    def test_examples_return_expected_minutes(self) -> None:
        cases = [
            ("*/15 * * * *", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
            ("0 9 * * MON-FRI", datetime(2026, 3, 6, 9), datetime(2026, 3, 9, 9)),
            ("0 0 29 2 *", datetime(2026, 3, 1), datetime(2028, 2, 29)),
            ("30 4 1,15 * 5", datetime(2026, 1, 1, 5), datetime(2026, 1, 2, 4, 30)),
        ]
        for expression, after, expected in cases:
            with self.subTest(expression=expression):
                self.assertEqual(next_run(expression, after), expected)

    def test_current_minute_is_always_excluded(self) -> None:
        for second, microsecond in [(0, 0), (30, 0), (0, 1), (59, 999999)]:
            with self.subTest(second=second, microsecond=microsecond):
                after = datetime(2026, 1, 1, 12, 0, second, microsecond)

                result = next_run("* * * * *", after)

                self.assertEqual(result, datetime(2026, 1, 1, 12, 1))

    def test_field_forms_and_day_rules_return_expected_minutes(self) -> None:
        after = datetime(2026, 1, 1)
        cases = [
            ("5/20 * * * *", datetime(2026, 1, 1, 0, 5)),
            ("1-9/3,20 * * * *", datetime(2026, 1, 1, 0, 1)),
            ("0 0 * JAN-MAR/2 MON-FRI", datetime(2026, 1, 2)),
            ("0 0 * * 7", datetime(2026, 1, 4)),
            ("0 0 * * 5-7", datetime(2026, 1, 2)),
            ("0 0 * * 7/2", datetime(2026, 1, 4)),
            ("0 0 */2 * *", datetime(2026, 1, 3)),
            ("0 0 */2 * MON", datetime(2026, 1, 3)),
            ("0 0 */1 * MON", datetime(2026, 1, 2)),
            ("0 0 * * */2", datetime(2026, 1, 3)),
            ("0 0 30 FEB MON", datetime(2026, 2, 2)),
            ("0 0 1 * *", datetime(2026, 2, 1)),
            (" \t0\t0  *  jAn\tSuN  ", datetime(2026, 1, 4)),
            ("0 0 31 12 *", datetime(2026, 12, 31)),
        ]
        for expression, expected in cases:
            with self.subTest(expression=expression):
                self.assertEqual(next_run(expression, after), expected)

    def test_shortcuts_are_case_insensitive(self) -> None:
        after = datetime(2026, 3, 4, 10, 7)
        cases = {
            "@YEARLY": datetime(2027, 1, 1),
            "@annually": datetime(2027, 1, 1),
            "@Monthly": datetime(2026, 4, 1),
            "@weekly": datetime(2026, 3, 8),
            "@daily": datetime(2026, 3, 5),
            "@midnight": datetime(2026, 3, 5),
            "@hourly": datetime(2026, 3, 4, 11),
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(next_run(expression, after), expected)

    def test_steps_progress_from_start_and_roll_over(self) -> None:
        cases = [
            ("5/20 * * * *", datetime(2026, 1, 1, 0, 5), datetime(2026, 1, 1, 0, 25)),
            ("1-9/3 * * * *", datetime(2026, 1, 1, 0, 7), datetime(2026, 1, 1, 1, 1)),
            ("*/100 * * * *", datetime(2026, 1, 1), datetime(2026, 1, 1, 1)),
            ("0 */6 * * *", datetime(2026, 1, 1, 6), datetime(2026, 1, 1, 12)),
            ("0 0 * JAN-MAY/2 *", datetime(2026, 1, 31), datetime(2026, 3, 1)),
            ("0 0 */2 * *", datetime(2026, 1, 31), datetime(2026, 2, 1)),
            ("0 0 * * FRI-7/2", datetime(2026, 1, 2), datetime(2026, 1, 4)),
            ("* * * * *", datetime(2026, 12, 31, 23, 59), datetime(2027, 1, 1)),
        ]
        for expression, after, expected in cases:
            with self.subTest(expression=expression, after=after):
                self.assertEqual(next_run(expression, after), expected)

    def test_invalid_expressions_raise_value_error(self) -> None:
        expressions = [
            "", "* * * *", "* * * * * *", "@unknown", "@daily *",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *",
            "* * * 0 *", "* * * 13 *", "* * * * 8", "-1 * * * *",
            "JAN * * * *", "* * MON * *", "* * * MON *", "* * * * JAN",
            "1, * * * *", ",1 * * * *", "1,,2 * * * *", "*/0 * * * *",
            "1/-2 * * * *", "1/ * * * *", "1/2/3 * * * *", "1-2-3 * * * *",
            "5-2 * * * *", "*-5 * * * *", "1-* * * * *", "+1 * * * *",
            "1.5 * * * *", "１ * * * *", "* * * * FRI-MON",
            "* * * * 7-0", "* * * * SUN-7/0", "*\n* * * *",
        ]
        for expression in expressions:
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    next_run(expression, datetime(2026, 1, 1))

    def test_non_string_expression_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            next_run(None, datetime(2026, 1, 1))  # type: ignore[arg-type]  # Test invalid input.

    def test_impossible_dates_raise_value_error(self) -> None:
        for expression in ["0 0 30 2 *", "0 0 31 4 *"]:
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    next_run(expression, datetime(2026, 1, 1))

    def test_leap_century_gap_exceeds_five_year_limit(self) -> None:
        with self.assertRaises(ValueError):
            next_run("0 0 29 2 *", datetime(2096, 3, 1))

    def test_leap_day_lower_bound_is_supported(self) -> None:
        self.assertEqual(
            next_run("0 0 29 2 *", datetime(2024, 2, 29)), datetime(2028, 2, 29)
        )

    def test_datetime_upper_boundary_does_not_overflow(self) -> None:
        self.assertEqual(
            next_run("* * * * *", datetime(9999, 12, 31, 23, 58)),
            datetime(9999, 12, 31, 23, 59),
        )
        with self.assertRaises(ValueError):
            next_run("* * * * *", datetime.max)


if __name__ == "__main__":
    unittest.main()
