import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTests(unittest.TestCase):
    def test_spec_examples(self):
        assert next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)) == datetime(2026, 3, 4, 10, 15)
        assert next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)) == datetime(2026, 3, 9, 9, 0)
        assert next_run("0 0 29 2 *", datetime(2026, 3, 1)) == datetime(2028, 2, 29, 0, 0)
        assert next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)) == datetime(2026, 1, 2, 4, 30)

    def test_strictly_later_and_precision(self):
        for second, microsecond in [(0, 0), (30, 0), (0, 1), (59, 999999)]:
            self.assertEqual(next_run("* * * * *", datetime(2026, 3, 4, 12, 0, second, microsecond)),
                             datetime(2026, 3, 4, 12, 1))
        self.assertEqual(next_run("* * * * *", datetime(2026, 12, 31, 23, 59)), datetime(2027, 1, 1))

    def test_field_forms(self):
        cases = [
            ("5/20 * * * *", datetime(2026, 1, 1, 0, 25)),
            ("10-30/7 * * * *", datetime(2026, 1, 1, 0, 10)),
            ("1,3,5 * * * *", datetime(2026, 1, 1, 1, 1)),
            ("*/100 * * * *", datetime(2026, 1, 1, 1)),
            ("0 0 * jAn *", datetime(2026, 1, 2)),
            ("0 0 * JAN-MAR *", datetime(2026, 1, 2)),
            ("0 0 * * 5-7", datetime(2026, 1, 2)),
            ("0 0 * * 7", datetime(2026, 1, 4)),
            ("0 0 * * 7/2", datetime(2026, 1, 4)),
            ("0 0 * * sun", datetime(2026, 1, 4)),
            (" \t0\t 0 * * * \t", datetime(2026, 1, 2)),
        ]
        for expr, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, datetime(2026, 1, 1, 0, 5)), expected)

    def test_day_matching(self):
        after = datetime(2026, 1, 1)
        cases = {
            "0 0 * * *": datetime(2026, 1, 2),
            "0 0 15 * *": datetime(2026, 1, 15),
            "0 0 * * MON": datetime(2026, 1, 5),
            "0 0 3 * MON": datetime(2026, 1, 3),
            "0 0 15 * MON": datetime(2026, 1, 5),
            "0 0 */2 * MON": datetime(2026, 1, 3),
            "0 0 15 * */1": datetime(2026, 1, 2),
            "0 0 30 2 MON": datetime(2026, 2, 2),
        }
        for expr, expected in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_shortcuts(self):
        after = datetime(2026, 3, 4, 10, 7)
        for shortcut, expanded in {
            "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *",
            "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
            "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
            "@hourly": "0 * * * *",
        }.items():
            self.assertEqual(next_run(" " + shortcut.upper() + "\t", after), next_run(expanded, after))

    def test_invalid(self):
        expressions = [
            "", "* * * *", "* * * * * *", "*\n* * * *",
            "60 * * * *", "-1 * * * *", "* 24 * * *", "* * 0 * *",
            "* * 32 * *", "* * * 0 *", "* * * 13 *", "* * * * 8",
            "MON * * * *", "* JAN * * *", "* * MON * *", "* * * MON *", "* * * * JAN",
            ",1 * * * *", "1, * * * *", "1,,2 * * * *",
            "*/0 * * * *", "*/-1 * * * *", "*/1.5 * * * *", "*/ * * * *",
            "*/2/3 * * * *", "5-2 * * * *", "* * * * FRI-MON",
            "* * * * 7-0", "1-2-3 * * * *", "1- * * * *", "*-3 * * * *",
            "+1 * * * *", "1.0 * * * *", "１ * * * *", "1_0 * * * *",
            "* * * * @daily", "@unknown", "@daily extra", "*\v* * * *",
        ]
        for expr in expressions:
            with self.subTest(expr=expr), self.assertRaises(ValueError):
                next_run(expr, datetime(2026, 1, 1))
        for expr in [None, 1, b"* * * * *", []]:
            with self.subTest(expr=expr), self.assertRaises(TypeError):
                next_run(expr, datetime(2026, 1, 1))

    def test_impossible_and_calendar_limits(self):
        for expr in ["0 0 30 2 *", "0 0 31 4 *"]:
            with self.assertRaises(ValueError):
                next_run(expr, datetime(2026, 1, 1))
        # The Gregorian century gap can put the next leap day beyond five years.
        with self.assertRaises(ValueError):
            next_run("0 0 29 2 *", datetime(2096, 3, 1))
        self.assertEqual(next_run("0 0 29 2 *", datetime(2099, 3, 1)), datetime(2104, 2, 29))
        self.assertEqual(next_run("0 0 29 2 *", datetime(2024, 2, 29)), datetime(2028, 2, 29))
        self.assertEqual(next_run("* * * * *", datetime(9999, 12, 31, 23, 58)), datetime(9999, 12, 31, 23, 59))
        with self.assertRaises(ValueError):
            next_run("* * * * *", datetime.max)


if __name__ == "__main__":
    unittest.main()
