"""Test the cron expression behavior specified in TASK.md."""

import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTests(unittest.TestCase):
    """Verify cron parsing and the earliest matching minute."""

    def test_next_run_valid_expression_returns_expected_minute(self) -> None:
        cases = [
            ("*/15 * * * *", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
            ("0 9 * * MON-FRI", datetime(2026, 3, 6, 9), datetime(2026, 3, 9, 9)),
            ("0 0 29 2 *", datetime(2026, 3, 1), datetime(2028, 2, 29)),
            ("30 4 1,15 * 5", datetime(2026, 1, 1, 5), datetime(2026, 1, 2, 4, 30)),
            ("* * * * *", datetime(2026, 1, 1), datetime(2026, 1, 1, 0, 1)),
            ("* * * * *", datetime(2026, 1, 1, 0, 0, 30, 1), datetime(2026, 1, 1, 0, 1)),
            ("* * * * *", datetime(2026, 12, 31, 23, 59), datetime(2027, 1, 1)),
            ("5/20 * * * *", datetime(2026, 1, 1, 0, 5), datetime(2026, 1, 1, 0, 25)),
            ("10-20/4 * * * *", datetime(2026, 1, 1, 0, 14), datetime(2026, 1, 1, 0, 18)),
            ("*/100 * * * *", datetime(2026, 1, 1), datetime(2026, 1, 1, 1)),
            ("0 0 */2 * MON", datetime(2026, 1, 3), datetime(2026, 1, 5)),
            ("0 0 * * */2", datetime(2026, 1, 4), datetime(2026, 1, 6)),
            ("0 0 1 * *", datetime(2026, 1, 1), datetime(2026, 2, 1)),
            ("0 0 * * 7", datetime(2026, 1, 3), datetime(2026, 1, 4)),
            ("0 0 * * 5-7", datetime(2026, 1, 3), datetime(2026, 1, 4)),
            ("0 0 * * 0-7/7", datetime(2026, 1, 4), datetime(2026, 1, 11)),
            ("0 0 * * 7/2", datetime(2026, 1, 3), datetime(2026, 1, 4)),
            ("0 0 30 FEB MON", datetime(2026, 2, 1), datetime(2026, 2, 2)),
            ("0 0 1 jan-mar/2 *", datetime(2026, 1, 1), datetime(2026, 3, 1)),
            ("0 0 * * mon-fri/2", datetime(2026, 1, 5), datetime(2026, 1, 7)),
            (" \t0\t 0  1 JAN * \t", datetime(2026, 1, 1), datetime(2027, 1, 1)),
            ("59,0,30 23,0 * * *", datetime(2026, 1, 1), datetime(2026, 1, 1, 0, 30)),
            ("* * * * *", datetime(9999, 12, 31, 23, 58), datetime(9999, 12, 31, 23, 59)),
        ]
        for expression, after, expected in cases:
            with self.subTest(expression=expression, after=after):
                self.assertEqual(next_run(expression, after), expected)

    def test_next_run_shortcut_matches_expanded_expression(self) -> None:
        shortcuts = {
            "@yearly": "0 0 1 1 *",
            "@annually": "0 0 1 1 *",
            "@monthly": "0 0 1 * *",
            "@weekly": "0 0 * * 0",
            "@daily": "0 0 * * *",
            "@midnight": "0 0 * * *",
            "@hourly": "0 * * * *",
        }
        after = datetime(2026, 3, 4, 10, 7, 42)

        for shortcut, expanded in shortcuts.items():
            with self.subTest(shortcut=shortcut):
                self.assertEqual(
                    next_run(" " + shortcut.upper() + "\t", after), next_run(expanded, after)
                )

    def test_next_run_invalid_expression_raises_value_error(self) -> None:
        expressions = [
            "", "* * * *", "* * * * * *", "@unknown", "@daily *", "60 * * * *",
            "* 24 * * *", "* * 0 * *", "* * 32 * *", "* * * 0 *", "* * * 13 *",
            "* * * * 8", "-1 * * * *", "+1 * * * *", "1.0 * * * *", "1_0 * * * *",
            "١ * * * *", "JAN * * * *", "* * MON * *", "* * * MON *", "* * * * JAN",
            "* * * * FRI-MON", "20-10 * * * *", "* * * * 7-0", "1, * * * *",
            ",1 * * * *", "1,,2 * * * *", "*/0 * * * *", "*/-1 * * * *",
            "*/+2 * * * *", "*/JAN * * * *", "1/2/3 * * * *", "1-2-3 * * * *",
            "*-5 * * * *", "1-* * * * *", "1/ * * * *", "? * * * *",
            "0 0 L * *", "0 0 * * MON#2", "0\n0 * * *", "0 0 *\v* *",
            "0 0 * * 0-8/2", "0 0 * DEC-JAN *", "1,60 * * * *",
        ]
        for expression in expressions:
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    next_run(expression, datetime(2026, 1, 1))

    def test_next_run_non_string_expression_raises_type_error(self) -> None:
        for expression in (None, 42, b"* * * * *", []):
            with self.subTest(expression=expression):
                self.assertRaises(TypeError, next_run, expression, datetime(2026, 1, 1))

    def test_next_run_no_match_within_five_years_raises_value_error(self) -> None:
        cases = [
            ("0 0 30 2 *", datetime(2026, 1, 1)),
            ("0 0 31 4 *", datetime(2026, 1, 1)),
            ("0 0 29 2 *", datetime(2096, 2, 29)),
            ("* * * * *", datetime.max),
            ("0 0 1 1 *", datetime(9999, 12, 31)),
        ]
        for expression, after in cases:
            with self.subTest(expression=expression, after=after):
                with self.assertRaises(ValueError):
                    next_run(expression, after)


if __name__ == "__main__":
    unittest.main()
