import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTest(unittest.TestCase):
    def test_spec_examples(self):
        self.assertEqual(next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)), datetime(2026, 3, 4, 10, 15))
        self.assertEqual(next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)), datetime(2026, 3, 9, 9, 0))
        self.assertEqual(next_run("0 0 29 2 *", datetime(2026, 3, 1)), datetime(2028, 2, 29, 0, 0))
        self.assertEqual(next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)), datetime(2026, 1, 2, 4, 30))

    def test_strictly_later_minute(self):
        self.assertEqual(next_run("* * * * *", datetime(2026, 1, 1, 12, 0, 30)), datetime(2026, 1, 1, 12, 1))
        self.assertEqual(next_run("* * * * *", datetime(2026, 1, 1, 12, 0)), datetime(2026, 1, 1, 12, 1))

    def test_shortcuts_and_sunday(self):
        self.assertEqual(next_run("@WEEKLY", datetime(2026, 3, 4, 10, 0)), datetime(2026, 3, 8, 0, 0))
        self.assertEqual(next_run("0 0 * * 7", datetime(2026, 3, 4, 10, 0)), datetime(2026, 3, 8, 0, 0))

    def test_impossible_raises(self):
        with self.assertRaises(ValueError):
            next_run("0 0 30 2 *", datetime(2026, 1, 1))

    def test_invalid_raises(self):
        for bad in ["", "* * * *", "60 * * * *", "MON * * * *", "FRI-MON * * * *", "*/0 * * * *",
                    "1,,2 * * * *", "*-5 * * * *", "* * * * 8", "0 0 * * SUN-SAT-X"]:
            with self.subTest(expr=bad), self.assertRaises(ValueError):
                next_run(bad, datetime(2026, 1, 1))
        with self.assertRaises(TypeError):
            next_run(None, datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
