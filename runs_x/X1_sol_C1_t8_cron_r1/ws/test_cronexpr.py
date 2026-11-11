import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTests(unittest.TestCase):
    def test_spec_examples(self):
        assert next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)) == datetime(2026, 3, 4, 10, 15)
        assert next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)) == datetime(2026, 3, 9, 9, 0)
        assert next_run("0 0 29 2 *", datetime(2026, 3, 1)) == datetime(2028, 2, 29, 0, 0)
        assert next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)) == datetime(2026, 1, 2, 4, 30)

    def test_strictly_later_minute(self):
        for seconds, microseconds in [(0, 0), (30, 0), (0, 1), (59, 999999)]:
            with self.subTest(seconds=seconds, microseconds=microseconds):
                self.assertEqual(
                    next_run("* * * * *", datetime(2026, 3, 4, 12, 0, seconds, microseconds)),
                    datetime(2026, 3, 4, 12, 1),
                )

    def test_valid_forms(self):
        cases = [
            (" \t5\t0 1 jan * \n", datetime(2026, 1, 1, 0, 5)),
            ("5/20 * * * *", datetime(2026, 1, 1, 0, 5)),
            ("2-9/3 * * * *", datetime(2026, 1, 1, 0, 2)),
            ("0,10,20 * * * *", datetime(2026, 1, 1, 0, 10)),
            ("*/100 * * * *", datetime(2026, 1, 1, 1)),
            ("0 0 * jan-mar mon-fri", datetime(2026, 1, 2)),
            ("0 0 * * 5-7", datetime(2026, 1, 2)),
            ("0 0 * * 7", datetime(2026, 1, 4)),
            ("0 0 * * 7/2", datetime(2026, 1, 4)),
            ("0 0 * * 0", datetime(2026, 1, 4)),
            ("0 0 * * SUN", datetime(2026, 1, 4)),
            ("0 0 */2 * *", datetime(2026, 1, 3)),
            ("0 0 31 * *", datetime(2026, 1, 31)),
            ("59 23 31 DEC *", datetime(2026, 12, 31, 23, 59)),
        ]
        for expression, expected in cases:
            with self.subTest(expression=expression):
                self.assertEqual(next_run(expression, datetime(2026, 1, 1)), expected)

    def test_day_restriction_is_literal_star(self):
        # January 2 is Friday. A stepped wildcard is restricted, so OR applies.
        after = datetime(2026, 1, 1)
        self.assertEqual(next_run("0 0 */2 * FRI", after), datetime(2026, 1, 2))
        self.assertEqual(next_run("0 0 1 * */1", after), datetime(2026, 1, 2))
        self.assertEqual(next_run("0 0 1 * *", after), datetime(2026, 2, 1))
        self.assertEqual(next_run("0 0 * * MON", after), datetime(2026, 1, 5))
        self.assertEqual(next_run("0 0 30 2 MON", after), datetime(2026, 2, 2))

    def test_sunday_normalization_follows_range_and_step(self):
        after = datetime(2026, 1, 2)
        self.assertEqual(next_run("0 0 * * 5-7/2", after), datetime(2026, 1, 4))
        self.assertEqual(next_run("0 0 * * 6-7", after), datetime(2026, 1, 3))

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
                self.assertEqual(next_run(" \t" + shortcut.upper() + " ", after), expected)

    def test_invalid_expressions(self):
        invalid = [
            "", "* * * *", "* * * * * *", "@reboot", "@daily *",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *",
            "* * * 0 *", "* * * 13 *", "* * * * 8",
            "JAN * * * *", "* MON * * *", "* * JAN * *",
            "* * * MON *", "* * * * JAN", "* * * * FRI-MON",
            "* * * DEC-JAN *", "9-2 * * * *", "-1 * * * *",
            "1, * * * *", ",1 * * * *", "1,,2 * * * *",
            "*/0 * * * *", "*/-1 * * * *", "*/1.5 * * * *",
            "*/MON * * * *", "*/ * * * *", "*/2/3 * * * *",
            "1-2-3 * * * *", "*-5 * * * *", "1-* * * * *",
            "+1 * * * *", "1.0 * * * *", "１ * * * *", "? * * * *",
            "*\n* * * *", "*\v* * * *", "* * * * MONDAY",
            "1 /2 * * *", "* * * * 7-0", "* * * * 8/2",
        ]
        for expression in invalid:
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    next_run(expression, datetime(2026, 1, 1))

    def test_non_string(self):
        for expression in [None, 12, b"* * * * *", [], {}]:
            with self.subTest(expression=expression):
                with self.assertRaises(TypeError):
                    next_run(expression, datetime(2026, 1, 1))

    def test_impossible_and_datetime_boundaries(self):
        for expression in ["0 0 30 2 *", "0 0 31 4 *"]:
            with self.assertRaises(ValueError):
                next_run(expression, datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            next_run("* * * * *", datetime.max)
        self.assertEqual(next_run("@daily", datetime(2026, 12, 31, 23, 59)), datetime(2027, 1, 1))
        # The next leap day after 2096 is eight years away (2100 is not leap).
        with self.assertRaises(ValueError):
            next_run("0 0 29 2 *", datetime(2096, 2, 29))


if __name__ == "__main__":
    unittest.main()
