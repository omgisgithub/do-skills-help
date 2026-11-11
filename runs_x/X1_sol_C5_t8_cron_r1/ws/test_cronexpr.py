import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTests(unittest.TestCase):
    def test_spec_examples(self):
        cases = [
            ("*/15 * * * *", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
            ("0 9 * * MON-FRI", datetime(2026, 3, 6, 9), datetime(2026, 3, 9, 9)),
            ("0 0 29 2 *", datetime(2026, 3, 1), datetime(2028, 2, 29)),
            ("30 4 1,15 * 5", datetime(2026, 1, 1, 5), datetime(2026, 1, 2, 4, 30)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_strictly_next_minute(self):
        for second, microsecond in [(0, 0), (30, 0), (0, 1), (59, 999999)]:
            with self.subTest(second=second, microsecond=microsecond):
                self.assertEqual(
                    next_run("* * * * *", datetime(2026, 1, 1, 12, 0, second, microsecond)),
                    datetime(2026, 1, 1, 12, 1),
                )

    def test_lists_ranges_steps_and_names(self):
        cases = [
            ("5/20 * * * *", datetime(2026, 1, 1, 0, 25), datetime(2026, 1, 1, 0, 45)),
            ("10-20/3 * * * *", datetime(2026, 1, 1, 0, 16), datetime(2026, 1, 1, 0, 19)),
            ("59,0 23,0 * * *", datetime(2026, 12, 31, 23, 59), datetime(2027, 1, 1)),
            ("0 0 * jAn-MaR/2 *", datetime(2026, 1, 31), datetime(2026, 3, 1)),
            ("0 0 */2 * *", datetime(2026, 4, 1), datetime(2026, 4, 3)),
            ("0 0 * */5 *", datetime(2026, 1, 31), datetime(2026, 6, 1)),
            ("0 0 * * MON/2", datetime(2026, 3, 2), datetime(2026, 3, 4)),
            ("0 0 * * 5-7", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0 0 * * 7/2", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0 0 * * 0-7/7", datetime(2026, 3, 8), datetime(2026, 3, 15)),
            ("0 0 * * 6-7/2", datetime(2026, 3, 7), datetime(2026, 3, 14)),
            ("  0\t0  * * sun  ", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0/999 0 * * *", datetime(2026, 1, 1), datetime(2026, 1, 2)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_day_restrictions_depend_on_exact_star(self):
        cases = [
            ("0 0 31 * MON", datetime(2026, 4, 5), datetime(2026, 4, 6)),
            ("0 0 30 2 MON", datetime(2026, 2, 1), datetime(2026, 2, 2)),
            ("0 0 */2 * MON", datetime(2026, 3, 1), datetime(2026, 3, 2)),
            ("0 0 */1 * MON", datetime(2026, 3, 2), datetime(2026, 3, 3)),
            ("0 0 15 * */1", datetime(2026, 3, 2), datetime(2026, 3, 3)),
            ("0 0 *,1 * MON", datetime(2026, 3, 2), datetime(2026, 3, 3)),
            ("0 0 15 * *", datetime(2026, 3, 2), datetime(2026, 3, 15)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_shortcuts(self):
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
                self.assertEqual(next_run(" \t" + expr.upper() + " ", after), expected)

    def test_invalid_expressions(self):
        expressions = [
            "", " ", "* * * *", "* * * * * *", "@unknown", "@daily *",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *",
            "* * * 0 *", "* * * 13 *", "* * * * 8", "-1 * * * *",
            "1,,2 * * * *", ",1 * * * *", "1, * * * *", "*/0 * * * *",
            "*/-1 * * * *", "*/1.5 * * * *", "*/+2 * * * *",
            "*/ * * * *", "1/2/3 * * * *", "2-1 * * * *",
            "* * * * FRI-MON", "* * * * 7-0", "1-2-3 * * * *",
            "JAN * * * *", "* MON * * *", "* * SUN * *", "* * * MON *",
            "* * * * JAN", "* * * SEPT *", "? * * * *", "+1 * * * *",
            "1.0 * * * *", "١ * * * *", "1_0 * * * *", "*,60 * * * *",
            "*\n* * * *", "*\v* * * *", "*-5 * * * *",
        ]
        for expr in expressions:
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    next_run(expr, datetime(2026, 1, 1))

    def test_non_string_expression(self):
        for expr in [None, 1, b"* * * * *", [], {}]:
            with self.subTest(expr=expr):
                with self.assertRaises(TypeError):
                    next_run(expr, datetime(2026, 1, 1))

    def test_impossible_dates_and_five_year_limit(self):
        for expr, after in [
            ("0 0 30 2 *", datetime(2026, 1, 1)),
            ("0 0 31 4 *", datetime(2026, 1, 1)),
            ("0 0 29 2 *", datetime(2096, 3, 1)),
        ]:
            with self.subTest(expr=expr, after=after):
                with self.assertRaises(ValueError):
                    next_run(expr, after)

    def test_datetime_boundaries(self):
        self.assertEqual(next_run("* * * * *", datetime(9999, 12, 31, 23, 58)),
                         datetime(9999, 12, 31, 23, 59))
        self.assertEqual(next_run("* * * * *", datetime.min), datetime(1, 1, 1, 0, 1))
        for after in [datetime.max, datetime(9999, 12, 31, 23, 59)]:
            with self.subTest(after=after):
                with self.assertRaises(ValueError):
                    next_run("* * * * *", after)


if __name__ == "__main__":
    unittest.main()
