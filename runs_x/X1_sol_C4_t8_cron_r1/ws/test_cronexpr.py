"""Test cron parsing and next-run scheduling using only the standard library."""

import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTests(unittest.TestCase):
    """Exercise valid expressions, calendar boundaries, and invalid input."""

    def test_examples_return_expected_minutes(self) -> None:
        cases = [
            ("*/15 * * * *", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
            ("0 9 * * MON-FRI", datetime(2026, 3, 6, 9), datetime(2026, 3, 9, 9)),
            ("0 0 29 2 *", datetime(2026, 3, 1), datetime(2028, 2, 29)),
            ("30 4 1,15 * 5", datetime(2026, 1, 1, 5), datetime(2026, 1, 2, 4, 30)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_minute_boundary_is_strict(self) -> None:
        for second, microsecond in [(0, 0), (30, 0), (0, 1), (59, 999999)]:
            with self.subTest(second=second, microsecond=microsecond):
                after = datetime(2026, 12, 31, 23, 59, second, microsecond)

                self.assertEqual(next_run("* * * * *", after), datetime(2027, 1, 1))

    def test_lists_ranges_steps_and_names_return_expected_minutes(self) -> None:
        cases = [
            ("5/20 * * * *", datetime(2026, 1, 1, 0, 5), datetime(2026, 1, 1, 0, 25)),
            ("1-10/3,20 * * * *", datetime(2026, 1, 1, 0, 7), datetime(2026, 1, 1, 0, 10)),
            ("0 0 * jAn-mAr/2 *", datetime(2026, 2, 1), datetime(2026, 3, 1)),
            ("0 0 * * 5-7", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0 0 * * 7", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0 0 * * 7/2", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0 0 */2 * MON", datetime(2026, 3, 1), datetime(2026, 3, 2)),
            ("0 0 * * */2", datetime(2026, 3, 1), datetime(2026, 3, 3)),
            ("0 0 30 FEB MON", datetime(2026, 2, 1), datetime(2026, 2, 2)),
            (" \t0\t0  1 JAN *\t ", datetime(2026, 1, 1), datetime(2027, 1, 1)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_shortcuts_return_expected_minutes(self) -> None:
        after = datetime(2026, 3, 4, 10, 7)
        cases = {
            "@yearly": datetime(2027, 1, 1),
            "@annually": datetime(2027, 1, 1),
            "@monthly": datetime(2026, 4, 1),
            "@weekly": datetime(2026, 3, 8),
            "@daily": datetime(2026, 3, 5),
            "@midnight": datetime(2026, 3, 5),
            "@hourly": datetime(2026, 3, 4, 11),
        }
        for expr, expected in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(next_run(" " + expr.upper() + "\t", after), expected)

    def test_invalid_expressions_raise_value_error(self) -> None:
        cases = [
            "", "* * * *", "* * * * * *", "@unknown", "@daily *", "*\n* * * *",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *", "* * * 0 *",
            "* * * 13 *", "* * * * 8", "MON * * * *", "0 0 JAN * *", "0 0 * MON *",
            "0 0 * * JAN", "0 0 * * FRI-MON", "5-1 * * * *", "-1 * * * *",
            "1, * * * *", ",1 * * * *", "1,,2 * * * *", "*/0 * * * *",
            "*/-1 * * * *", "*/1.5 * * * *", "*/ * * * *", "1/2/3 * * * *",
            "1-2-3 * * * *", "*-5 * * * *", "1-* * * * *", "+1 * * * *",
            "1.0 * * * *", "? * * * *", "١ * * * *", "1e1 * * * *",
        ]
        for expr in cases:
            with self.subTest(expr=expr), self.assertRaises(ValueError):
                next_run(expr, datetime(2026, 1, 1))

    def test_non_string_expression_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            next_run(None, datetime(2026, 1, 1))  # type: ignore[arg-type]  # Test bad input.

    def test_impossible_dates_and_five_year_limit_raise_value_error(self) -> None:
        cases = [
            ("0 0 30 2 *", datetime(2026, 1, 1)),
            ("0 0 31 4 *", datetime(2026, 1, 1)),
            ("0 0 29 2 *", datetime(2096, 3, 1)),
            ("* * * * *", datetime.max),
        ]
        for expr, after in cases:
            with self.subTest(expr=expr, after=after), self.assertRaises(ValueError):
                next_run(expr, after)

    def test_leap_day_start_and_maximum_year_are_supported(self) -> None:
        self.assertEqual(next_run("@yearly", datetime(2024, 2, 29)), datetime(2025, 1, 1))
        self.assertEqual(
            next_run("* * * * *", datetime(9999, 12, 31, 23, 58)),
            datetime(9999, 12, 31, 23, 59),
        )


if __name__ == "__main__":
    unittest.main()
