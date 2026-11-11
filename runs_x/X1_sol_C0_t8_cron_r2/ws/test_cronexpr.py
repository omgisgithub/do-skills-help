import unittest
from datetime import datetime, timedelta

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

    def test_strictly_later_and_rollover(self):
        for second, microsecond in [(0, 0), (30, 0), (0, 1), (59, 999999)]:
            after = datetime(2026, 12, 31, 23, 59, second, microsecond)
            self.assertEqual(next_run("* * * * *", after), datetime(2027, 1, 1))

    def test_steps_names_and_lists(self):
        cases = [
            ("5/20 * * * *", datetime(2026, 1, 1, 0, 25), datetime(2026, 1, 1, 0, 45)),
            ("1-10/4,20 2 * * *", datetime(2026, 1, 1, 2, 5), datetime(2026, 1, 1, 2, 9)),
            ("0 0 * jAn-mar/2 *", datetime(2026, 2, 1), datetime(2026, 3, 1)),
            ("0 0 * * 5-7", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0 0 * * 7", datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ("0 0 * * MON-FRI/2", datetime(2026, 3, 2), datetime(2026, 3, 4)),
            (" \t0\t0 * * * \t", datetime(2026, 1, 1), datetime(2026, 1, 2)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_day_restrictions_are_syntactic(self):
        after = datetime(2026, 3, 2)  # Monday
        self.assertEqual(next_run("0 0 * * MON", after), datetime(2026, 3, 9))
        self.assertEqual(next_run("0 0 */1 * MON", after), datetime(2026, 3, 3))
        self.assertEqual(next_run("0 0 */2 * MON", after), datetime(2026, 3, 3))
        self.assertEqual(next_run("0 0 31 2 MON", datetime(2026, 2, 1)), datetime(2026, 2, 2))

    def test_shortcuts(self):
        after = datetime(2026, 3, 4, 10, 7)
        shortcuts = {
            "@yearly": datetime(2027, 1, 1),
            "@annually": datetime(2027, 1, 1),
            "@monthly": datetime(2026, 4, 1),
            "@weekly": datetime(2026, 3, 8),
            "@daily": datetime(2026, 3, 5),
            "@midnight": datetime(2026, 3, 5),
            "@hourly": datetime(2026, 3, 4, 11),
        }
        for expr, expected in shortcuts.items():
            with self.subTest(expr=expr):
                self.assertEqual(next_run(" " + expr.upper() + "\t", after), expected)

    def test_invalid_expressions(self):
        invalid = [
            "", "* * * *", "* * * * * *", "@unknown", "@daily extra",
            "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 8",
            "* * * * FRI-MON", "* * * * 7-0", "* * * JAN-MAR-DEC *",
            "*/0 * * * *", "*/-2 * * * *", "*/1/2 * * * *", "*/MON * * * *",
            ",1 * * * *", "1, * * * *", "1,,2 * * * *", "1- * * * *",
            "+1 * * * *", "1.0 * * * *", "MON * * * *", "* * * SUN *",
            "* * * * JAN", "*\n* * * *", "* * * * １", "** * * * *",
        ]
        for expr in invalid:
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    next_run(expr, datetime(2026, 1, 1))
        for expr in (None, 123, b"* * * * *", []):
            with self.assertRaises(TypeError):
                next_run(expr, datetime(2026, 1, 1))

    def test_impossible_dates_and_datetime_limits(self):
        for expr in ("0 0 30 2 *", "0 0 31 4 *"):
            with self.assertRaises(ValueError):
                next_run(expr, datetime(2026, 1, 1))
        # The eight-year leap-day gap around 2100 exceeds the search window.
        with self.assertRaises(ValueError):
            next_run("0 0 29 2 *", datetime(2096, 3, 1))
        self.assertEqual(next_run("* * * * *", datetime(9999, 12, 31, 23, 58)),
                         datetime(9999, 12, 31, 23, 59))
        with self.assertRaises(ValueError):
            next_run("* * * * *", datetime.max)
        self.assertEqual(next_run("@yearly", datetime(2024, 2, 29)), datetime(2025, 1, 1))

    def test_against_minute_by_minute_reference(self):
        # Independent predicates exercise jumps across hours, days, and months.
        cases = [
            ("7,37 1,13 * * *", lambda d: d.minute in (7, 37) and d.hour in (1, 13)),
            ("*/17 4-8 * * MON-FRI", lambda d: d.minute % 17 == 0 and 4 <= d.hour <= 8 and d.weekday() < 5),
            ("0 0 31 * SUN", lambda d: d.minute == d.hour == 0 and (d.day == 31 or d.weekday() == 6)),
        ]
        for expr, predicate in cases:
            for after in (datetime(2026, 1, 30, 23, 59, 15), datetime(2026, 3, 6, 8)):
                expected = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
                while not predicate(expected):
                    expected += timedelta(minutes=1)
                with self.subTest(expr=expr, after=after):
                    self.assertEqual(next_run(expr, after), expected)


if __name__ == "__main__":
    unittest.main()
