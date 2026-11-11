import unittest
from datetime import datetime, timedelta

from cronexpr import next_run


class NextRunTests(unittest.TestCase):
    def test_examples(self):
        examples = [
            ("*/15 * * * *", datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
            ("0 9 * * MON-FRI", datetime(2026, 3, 6, 9), datetime(2026, 3, 9, 9)),
            ("0 0 29 2 *", datetime(2026, 3, 1), datetime(2028, 2, 29)),
            ("30 4 1,15 * 5", datetime(2026, 1, 1, 5), datetime(2026, 1, 2, 4, 30)),
        ]
        for expr, after, expected in examples:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_strict_minute_boundary(self):
        for seconds, micros in [(0, 0), (30, 0), (59, 999999)]:
            after = datetime(2026, 1, 1, 12, 0, seconds, micros)
            self.assertEqual(next_run("* * * * *", after), datetime(2026, 1, 1, 12, 1))

    def test_steps_lists_names_and_whitespace(self):
        self.assertEqual(
            next_run(" \t5/20 8-12/2 * jAn,mAr mon-FRI\t", datetime(2026, 1, 2, 8, 46)),
            datetime(2026, 1, 2, 10, 5),
        )
        self.assertEqual(next_run("0 0 * * 5-7", datetime(2026, 1, 3)), datetime(2026, 1, 4))
        self.assertEqual(next_run("0 0 * * 7/2", datetime(2026, 1, 3)), datetime(2026, 1, 4))
        self.assertEqual(next_run("0 0 * * 0-7/2", datetime(2026, 1, 4)), datetime(2026, 1, 6))

    def test_exact_star_controls_day_restrictions(self):
        after = datetime(2026, 1, 5)  # Monday
        self.assertEqual(next_run("0 0 * * MON", after), datetime(2026, 1, 12))
        self.assertEqual(next_run("0 0 */1 * MON", after), datetime(2026, 1, 6))
        self.assertEqual(next_run("0 0 15 * *", after), datetime(2026, 1, 15))
        self.assertEqual(next_run("0 0 15 * */1", after), datetime(2026, 1, 6))
        self.assertEqual(next_run("0 0 30 FEB MON", after), datetime(2026, 2, 2))

    def test_shortcuts(self):
        after = datetime(2026, 3, 4, 10, 7)
        expected = {
            "@yearly": datetime(2027, 1, 1),
            "@annually": datetime(2027, 1, 1),
            "@monthly": datetime(2026, 4, 1),
            "@weekly": datetime(2026, 3, 8),
            "@daily": datetime(2026, 3, 5),
            "@midnight": datetime(2026, 3, 5),
            "@hourly": datetime(2026, 3, 4, 11),
        }
        for expr, result in expected.items():
            with self.subTest(expr=expr):
                self.assertEqual(next_run(" " + expr.upper() + "\t", after), result)

    def test_invalid_expressions(self):
        expressions = [
            "", "* * * *", "* * * * * *", "@unknown", "@daily extra",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 8",
            "1, * * * *", ",1 * * * *", "1,,2 * * * *", "*/0 * * * *",
            "*/-1 * * * *", "*/1.5 * * * *", "*/ * * * *", "*//2 * * * *",
            "9-2 * * * *", "* * * * FRI-MON", "1-2-3 * * * *",
            "+1 * * * *", "1.0 * * * *", "MON * * * *", "* * JAN * *",
            "* * * MON *", "* * * * JAN", "*\n* * * *", "* * * * ?",
        ]
        for expr in expressions:
            with self.subTest(expr=expr), self.assertRaises(ValueError):
                next_run(expr, datetime(2026, 1, 1))
        for expr in [None, 123, b"* * * * *"]:
            with self.subTest(expr=expr), self.assertRaises(TypeError):
                next_run(expr, datetime(2026, 1, 1))

    def test_impossible_dates_and_horizon(self):
        for expr, after in [
            ("0 0 30 2 *", datetime(2026, 1, 1)),
            ("0 0 31 4 *", datetime(2026, 1, 1)),
            ("0 0 29 2 *", datetime(2096, 3, 1)),
            ("* * * * *", datetime.max),
        ]:
            with self.subTest(expr=expr, after=after), self.assertRaises(ValueError):
                next_run(expr, after)
        self.assertEqual(next_run("0 0 29 2 *", datetime(2024, 2, 29)), datetime(2028, 2, 29))
        self.assertEqual(next_run("* * * * *", datetime.max - timedelta(minutes=1)),
                         datetime(9999, 12, 31, 23, 59))


if __name__ == "__main__":
    unittest.main()
