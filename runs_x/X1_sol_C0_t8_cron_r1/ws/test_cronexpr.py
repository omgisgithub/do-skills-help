import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTests(unittest.TestCase):
    def test_examples(self):
        cases = [
            ("*/15 * * * *", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
            ("0 9 * * MON-FRI", datetime(2026, 3, 6, 9), datetime(2026, 3, 9, 9)),
            ("0 0 29 2 *", datetime(2026, 3, 1), datetime(2028, 2, 29)),
            ("30 4 1,15 * 5", datetime(2026, 1, 1, 5), datetime(2026, 1, 2, 4, 30)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_strictly_later_minute(self):
        for second, microsecond in [(0, 0), (30, 0), (0, 1), (59, 999999)]:
            self.assertEqual(
                next_run("* * * * *", datetime(2026, 12, 31, 23, 59, second, microsecond)),
                datetime(2027, 1, 1),
            )

    def test_steps_lists_and_names(self):
        cases = [
            ("5/20 8-10/2 * * *", datetime(2026, 1, 1, 8, 45), datetime(2026, 1, 1, 10, 5)),
            ("0,30 9 * jan-mar/2 *", datetime(2026, 2, 1), datetime(2026, 3, 1, 9)),
            ("0 0 * * 5-7", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0 0 * * 7/2", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0 0 * * mon-fri/2", datetime(2026, 3, 2), datetime(2026, 3, 4)),
            (" \t0\t0 * * *\t ", datetime(2026, 1, 1), datetime(2026, 1, 2)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_restricted_day_matching(self):
        after = datetime(2026, 3, 2)  # Monday, day 2
        self.assertEqual(next_run("0 0 */2 * MON", after), datetime(2026, 3, 3))
        self.assertEqual(next_run("0 0 * * MON", after), datetime(2026, 3, 9))
        self.assertEqual(next_run("0 0 3 * *", after), datetime(2026, 3, 3))
        self.assertEqual(next_run("0 0 30 2 MON", datetime(2026, 2, 1)), datetime(2026, 2, 2))

    def test_shortcuts(self):
        after = datetime(2026, 3, 4, 10, 7)
        cases = {
            "@yearly": datetime(2027, 1, 1), "@annually": datetime(2027, 1, 1),
            "@monthly": datetime(2026, 4, 1), "@weekly": datetime(2026, 3, 8),
            "@daily": datetime(2026, 3, 5), "@midnight": datetime(2026, 3, 5),
            "@hourly": datetime(2026, 3, 4, 11),
        }
        for expr, expected in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(next_run(" " + expr.upper() + "\t", after), expected)

    def test_invalid_expressions(self):
        expressions = [
            "", "* * * *", "* * * * * *", "@unknown", "@daily extra",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 8",
            "* * * MON *", "JAN * * * *", "* * * * JAN", "* * * * FRI-MON",
            "5-2 * * * *", "*/0 * * * *", "*/-1 * * * *", "*/1/2 * * * *",
            ",1 * * * *", "1, * * * *", "1,,2 * * * *", "1- * * * *",
            "+1 * * * *", "1.0 * * * *", "? * * * *", "*/MON * * * *",
            "* * * * *\n", "*\n* * * *", "١ * * * *",
        ]
        for expr in expressions:
            with self.subTest(expr=expr), self.assertRaises(ValueError):
                next_run(expr, datetime(2026, 1, 1))
        for expr in [None, 5, b"* * * * *"]:
            with self.subTest(expr=expr), self.assertRaises(TypeError):
                next_run(expr, datetime(2026, 1, 1))

    def test_search_limit_and_datetime_ceiling(self):
        for expr, after in [
            ("0 0 30 2 *", datetime(2026, 1, 1)),
            ("0 0 29 2 *", datetime(2096, 3, 1)),
            ("* * * * *", datetime.max),
        ]:
            with self.subTest(expr=expr, after=after), self.assertRaises(ValueError):
                next_run(expr, after)
        self.assertEqual(next_run("@daily", datetime(9999, 12, 30)), datetime(9999, 12, 31))
        self.assertEqual(next_run("0 0 29 2 *", datetime(2024, 2, 29)), datetime(2028, 2, 29))


if __name__ == "__main__":
    unittest.main()
