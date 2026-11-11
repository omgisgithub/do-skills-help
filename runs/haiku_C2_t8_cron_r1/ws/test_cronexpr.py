import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTest(unittest.TestCase):
    def test_spec_examples(self):
        self.assertEqual(next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)),
                         datetime(2026, 3, 4, 10, 15))
        self.assertEqual(next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)),
                         datetime(2026, 3, 9, 9, 0))
        self.assertEqual(next_run("0 0 29 2 *", datetime(2026, 3, 1)),
                         datetime(2028, 2, 29, 0, 0))
        self.assertEqual(next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)),
                         datetime(2026, 1, 2, 4, 30))

    def test_strictly_later_minute(self):
        self.assertEqual(next_run("* * * * *", datetime(2026, 1, 1, 12, 0, 30)),
                         datetime(2026, 1, 1, 12, 1))
        self.assertEqual(next_run("0 * * * *", datetime(2026, 1, 1, 12, 0)),
                         datetime(2026, 1, 1, 13, 0))

    def test_day_matching_or_and(self):
        # both restricted: either day-of-month or day-of-week matches
        self.assertEqual(next_run("0 0 13 * FRI", datetime(2026, 3, 1)),
                         datetime(2026, 3, 6, 0, 0))
        # only one restricted: only that one counts
        self.assertEqual(next_run("0 0 13 * *", datetime(2026, 3, 1)),
                         datetime(2026, 3, 13, 0, 0))

    def test_sunday_is_0_or_7(self):
        self.assertEqual(next_run("0 0 * * 7", datetime(2026, 2, 28, 12, 0)),
                         datetime(2026, 3, 1, 0, 0))
        self.assertEqual(next_run("0 0 * * 5-7", datetime(2026, 3, 6, 0, 0)),
                         datetime(2026, 3, 7, 0, 0))

    def test_steps_and_names(self):
        self.assertEqual(next_run("0 0 * * 1/3", datetime(2026, 3, 1)),
                         datetime(2026, 3, 2, 0, 0))  # 1/3 = Mon, Thu, Sun
        self.assertEqual(next_run("0 0 1 jan-mar/2 *", datetime(2026, 1, 2)),
                         datetime(2026, 3, 1, 0, 0))

    def test_shortcuts(self):
        self.assertEqual(next_run("@HOURLY", datetime(2026, 1, 1, 12, 30)),
                         datetime(2026, 1, 1, 13, 0))
        self.assertEqual(next_run("@yearly", datetime(2026, 1, 1, 0, 0)),
                         datetime(2027, 1, 1, 0, 0))

    def test_whitespace(self):
        self.assertEqual(next_run("  \t0\t0  * * *\t ", datetime(2026, 1, 1)),
                         datetime(2026, 1, 2, 0, 0))

    def test_no_match_raises(self):
        with self.assertRaises(ValueError):
            next_run("0 0 30 2 *", datetime(2026, 1, 1))

    def test_invalid_expressions_raise(self):
        for expr in ["", "* * * *", "60 * * * *", "* 24 * * *", "* * 0 * *",
                     "* * * 13 *", "* * * * 8", "*/0 * * * *", "5-1 * * * *",
                     "FRI-MON * * * *", "* * * JAN * *", "1,,2 * * * *",
                     "0 0 * * FRI-MON", "1-2-3 * * * *", "@sometimes"]:
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    next_run(expr, datetime(2026, 1, 1))

    def test_non_str_raises_type_error(self):
        with self.assertRaises(TypeError):
            next_run(None, datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
