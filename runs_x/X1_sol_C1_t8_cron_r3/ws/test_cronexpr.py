import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTests(unittest.TestCase):
    def test_spec_examples(self):
        self.assertEqual(next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)),
                         datetime(2026, 3, 4, 10, 15))
        self.assertEqual(next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)),
                         datetime(2026, 3, 9, 9, 0))
        self.assertEqual(next_run("0 0 29 2 *", datetime(2026, 3, 1)),
                         datetime(2028, 2, 29, 0, 0))
        self.assertEqual(next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)),
                         datetime(2026, 1, 2, 4, 30))

    def test_strictly_later_whole_minute(self):
        for seconds, micros in [(0, 0), (30, 0), (0, 1), (59, 999999)]:
            with self.subTest(seconds=seconds, micros=micros):
                self.assertEqual(
                    next_run("* * * * *", datetime(2026, 1, 1, 12, 0, seconds, micros)),
                    datetime(2026, 1, 1, 12, 1))
        self.assertEqual(next_run("* * * * *", datetime(2026, 12, 31, 23, 59)),
                         datetime(2027, 1, 1))

    def test_lists_ranges_steps_and_names(self):
        after = datetime(2026, 1, 1)
        cases = [
            ("5,2,5 0 * * *", datetime(2026, 1, 1, 0, 2)),
            ("2-8/3 0 * * *", datetime(2026, 1, 1, 0, 2)),
            ("58/2 * * * *", datetime(2026, 1, 1, 0, 58)),
            ("*/17 * * * *", datetime(2026, 1, 1, 0, 17)),
            ("0 0 */2 * *", datetime(2026, 1, 3)),
            ("0 0 * */2 *", datetime(2026, 1, 2)),
            ("0 0 * jan-MaR/2 *", datetime(2026, 1, 2)),
            ("0 0 * * fri-sat", datetime(2026, 1, 2)),
            ("0 0 * * 5-7", datetime(2026, 1, 2)),
            ("0 0 * * 7/2", datetime(2026, 1, 4)),
            ("0 0 * * 6-7/1", datetime(2026, 1, 3)),
            ("0 0 * * sun", datetime(2026, 1, 4)),
            ("0 0 * * 0", datetime(2026, 1, 4)),
            (" \t0\t0  * * *\t ", datetime(2026, 1, 2)),
            ("\n0 0 * * *\r\n", datetime(2026, 1, 2)),
            ("*/99 * * * *", datetime(2026, 1, 1, 1)),
            ("59-59 0 * * *", datetime(2026, 1, 1, 0, 59)),
        ]
        for expr, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_day_restrictions(self):
        after = datetime(2026, 1, 1)
        cases = [
            ("0 0 * * *", datetime(2026, 1, 2)),
            ("0 0 3 * *", datetime(2026, 1, 3)),
            ("0 0 * * MON", datetime(2026, 1, 5)),
            ("0 0 3 * MON", datetime(2026, 1, 3)),
            ("0 0 20 * FRI", datetime(2026, 1, 2)),
            ("0 0 */1 * MON", datetime(2026, 1, 2)),
            ("0 0 20 * */1", datetime(2026, 1, 2)),
            ("0 0 *,3 * MON", datetime(2026, 1, 2)),
            ("0 0 30 2 MON", datetime(2026, 2, 2)),
        ]
        for expr, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_shortcuts(self):
        after = datetime(2026, 3, 4, 10, 7)
        for shortcut, expected in [
            ("@yearly", datetime(2027, 1, 1)),
            ("@annually", datetime(2027, 1, 1)),
            ("@monthly", datetime(2026, 4, 1)),
            ("@weekly", datetime(2026, 3, 8)),
            ("@daily", datetime(2026, 3, 5)),
            ("@midnight", datetime(2026, 3, 5)),
            ("@hourly", datetime(2026, 3, 4, 11)),
        ]:
            with self.subTest(shortcut=shortcut):
                self.assertEqual(next_run("\t" + shortcut.upper() + " ", after), expected)

    def test_invalid_expressions(self):
        expressions = [
            "", "* * * *", "* * * * * *", "@unknown", "@daily *", "@ daily",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *",
            "* * * 0 *", "* * * 13 *", "* * * * 8", "-1 * * * *",
            "1.0 * * * *", "+1 * * * *", "1e1 * * * *", "١ * * * *",
            ",1 * * * *", "1, * * * *", "1,,2 * * * *",
            "*/0 * * * *", "*/-1 * * * *", "*/+1 * * * *",
            "*/1.5 * * * *", "*/ * * * *", "*/2/3 * * * *",
            "5-2 * * * *", "*-5 * * * *", "1-* * * * *",
            "1-2-3 * * * *", "1--2 * * * *", "1 /2 * * * *",
            "JAN * * * *", "* MON * * *", "* * JAN * *",
            "* * * MON *", "* * * * JAN", "* * * JUNE *",
            "* * * * FRI-MON", "* * * * 7-0", "* * * DEC-JAN *",
            "*\n* * * *", "*\r* * * *", "*\v* * * *",
        ]
        for expr in expressions:
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    next_run(expr, datetime(2026, 1, 1))
        for expr in [None, 123, b"* * * * *", [], {}]:
            with self.subTest(expr=expr):
                with self.assertRaises(TypeError):
                    next_run(expr, datetime(2026, 1, 1))

    def test_impossible_dates_and_search_limit(self):
        for expr, after in [
            ("0 0 30 2 *", datetime(2026, 1, 1)),
            ("0 0 31 4 *", datetime(2026, 1, 1)),
            ("0 0 29 2 *", datetime(2096, 2, 29)),
            ("0 0 30 2 *", datetime(2024, 2, 29)),
            ("* * * * *", datetime.max),
        ]:
            with self.subTest(expr=expr, after=after):
                with self.assertRaises(ValueError):
                    next_run(expr, after)
        self.assertEqual(next_run("* * * * *", datetime(9999, 12, 31, 23, 58)),
                         datetime(9999, 12, 31, 23, 59))


if __name__ == "__main__":
    unittest.main()
