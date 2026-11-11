import unittest
from datetime import datetime

from cronexpr import next_run


class NextRunTests(unittest.TestCase):
    def test_examples(self):
        cases = [
            ('*/15 * * * *', datetime(2026, 3, 4, 10, 7), datetime(2026, 3, 4, 10, 15)),
            ('0 9 * * MON-FRI', datetime(2026, 3, 6, 9), datetime(2026, 3, 9, 9)),
            ('0 0 29 2 *', datetime(2026, 3, 1), datetime(2028, 2, 29)),
            ('30 4 1,15 * 5', datetime(2026, 1, 1, 5), datetime(2026, 1, 2, 4, 30)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_strict_minute_and_rollovers(self):
        for second, microsecond in [(0, 0), (30, 0), (0, 1), (59, 999999)]:
            with self.subTest(second=second, microsecond=microsecond):
                self.assertEqual(
                    next_run('* * * * *', datetime(2026, 12, 31, 23, 59, second, microsecond)),
                    datetime(2027, 1, 1),
                )

    def test_steps_lists_names_and_sunday_alias(self):
        cases = [
            ('5/20 * * * *', datetime(2026, 1, 1, 0, 5), datetime(2026, 1, 1, 0, 25)),
            ('1-10/3,20 4 * * *', datetime(2026, 1, 1, 4, 7), datetime(2026, 1, 1, 4, 10)),
            ('0 0 * jan-mar/2 *', datetime(2026, 1, 31), datetime(2026, 3, 1)),
            ('0 0 * * 5-7', datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ('0 0 * * 7', datetime(2026, 3, 7), datetime(2026, 3, 8)),
            ('0 0 * * SUN-SAT/2', datetime(2026, 3, 8), datetime(2026, 3, 10)),
            ('\t 0\t0 1 JAN *  ', datetime(2026, 1, 1), datetime(2027, 1, 1)),
            ('0 0 * * 7/2', datetime(2026, 3, 7), datetime(2026, 3, 8)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_day_restriction_is_syntactic(self):
        cases = [
            ('0 0 */2 * MON', datetime(2026, 3, 3), datetime(2026, 3, 5)),
            ('0 0 * * MON', datetime(2026, 3, 3), datetime(2026, 3, 9)),
            ('0 0 1 * *', datetime(2026, 3, 3), datetime(2026, 4, 1)),
            ('0 0 1 * */1', datetime(2026, 3, 3), datetime(2026, 3, 4)),
            ('0 0 30 FEB MON', datetime(2026, 2, 1), datetime(2026, 2, 2)),
        ]
        for expr, after, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(next_run(expr, after), expected)

    def test_shortcuts(self):
        cases = {
            '@yearly': datetime(2027, 1, 1), '@annually': datetime(2027, 1, 1),
            '@monthly': datetime(2026, 4, 1), '@weekly': datetime(2026, 3, 8),
            '@daily': datetime(2026, 3, 5), '@midnight': datetime(2026, 3, 5),
            '@hourly': datetime(2026, 3, 4, 11),
        }
        for expr, expected in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(next_run(' ' + expr.upper() + '\t', datetime(2026, 3, 4, 10, 7)), expected)

    def test_invalid_expressions(self):
        invalid = [
            '', '* * * *', '* * * * * *', '@unknown', '@daily *',
            '60 * * * *', '* 24 * * *', '* * 0 * *', '* * 32 * *',
            '* * * 0 *', '* * * 13 *', '* * * * 8', '* * * * -1',
            '* * * * FRI-MON', '* * * DEC-JAN *', '5-2 * * * *',
            '*/0 * * * *', '*/-1 * * * *', '*/1.5 * * * *',
            '1,,2 * * * *', ',1 * * * *', '1, * * * *',
            '*/ * * * *', '1/2/3 * * * *', '1-* * * * *',
            '+1 * * * *', '1.0 * * * *', 'SUN * * * *', '* * * MON *',
            '* * * * JAN', '* * * * MON/FRI', '* * * * 7-0',
            '*\n* * * *', '*\v* * * *', '１ * * * *',
        ]
        for expr in invalid:
            with self.subTest(expr=expr), self.assertRaises(ValueError):
                next_run(expr, datetime(2026, 1, 1))

    def test_non_string(self):
        for expr in [None, 42, b'* * * * *', []]:
            with self.subTest(expr=expr), self.assertRaises(TypeError):
                next_run(expr, datetime(2026, 1, 1))

    def test_impossible_and_five_year_limit(self):
        for expr, after in [
            ('0 0 30 2 *', datetime(2026, 1, 1)),
            ('0 0 31 4 *', datetime(2026, 1, 1)),
            ('0 0 29 2 *', datetime(2096, 3, 1)),
        ]:
            with self.subTest(expr=expr, after=after), self.assertRaises(ValueError):
                next_run(expr, after)

    def test_datetime_upper_boundary(self):
        self.assertEqual(next_run('* * * * *', datetime(9999, 12, 31, 23, 58)), datetime(9999, 12, 31, 23, 59))
        with self.assertRaises(ValueError):
            next_run('* * * * *', datetime.max)


if __name__ == '__main__':
    unittest.main()
