import unittest
from datetime import datetime

from cronexpr import next_run


class SpecExamples(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)),
                         datetime(2026, 3, 4, 10, 15))
        self.assertEqual(next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)),
                         datetime(2026, 3, 9, 9, 0))
        self.assertEqual(next_run("0 0 29 2 *", datetime(2026, 3, 1)),
                         datetime(2028, 2, 29, 0, 0))
        self.assertEqual(next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)),
                         datetime(2026, 1, 2, 4, 30))


class Result(unittest.TestCase):
    def test_seconds_in_after(self):
        self.assertEqual(next_run("* * * * *", datetime(2026, 1, 1, 12, 0, 30)),
                         datetime(2026, 1, 1, 12, 1))

    def test_strictly_later(self):
        self.assertEqual(next_run("0 12 * * *", datetime(2026, 1, 1, 12, 0)),
                         datetime(2026, 1, 2, 12, 0))

    def test_microseconds_dropped(self):
        r = next_run("*/5 * * * *", datetime(2026, 1, 1, 12, 0, 0, 500))
        self.assertEqual(r, datetime(2026, 1, 1, 12, 5))
        self.assertEqual(r.microsecond, 0)

    def test_no_match_raises(self):
        with self.assertRaises(ValueError):
            next_run("0 0 30 2 *", datetime(2026, 1, 1))

    def test_limit_five_years(self):
        # Limit is 2104-02-28 00:00 from 2099-02-28; 2104-02-29 is past it
        with self.assertRaises(ValueError):
            next_run("0 0 29 2 *", datetime(2099, 2, 28))
        # Limit is 2104-03-01 from 2099-03-01; 2104-02-29 is inside it
        self.assertEqual(next_run("0 0 29 2 *", datetime(2099, 3, 1)),
                         datetime(2104, 2, 29))

    def test_types(self):
        with self.assertRaises(TypeError):
            next_run(None, datetime(2026, 1, 1))
        with self.assertRaises(TypeError):
            next_run(b"* * * * *", datetime(2026, 1, 1))


class Whitespace(unittest.TestCase):
    def test_tabs_and_padding_ok(self):
        self.assertEqual(next_run("\t 0\t 9  *  * *\t", datetime(2026, 3, 4, 8, 0)),
                         datetime(2026, 3, 4, 9, 0))

    def test_newline_inside_invalid(self):
        with self.assertRaises(ValueError):
            next_run("0\n9 * * *", datetime(2026, 1, 1))

    def test_comma_inside_field_space_invalid(self):
        with self.assertRaises(ValueError):
            next_run("0, 9 * * *", datetime(2026, 1, 1))


class Shortcuts(unittest.TestCase):
    def test_shortcuts(self):
        d = datetime(2026, 3, 4, 10, 7)
        self.assertEqual(next_run("@hourly", d), datetime(2026, 3, 4, 11, 0))
        self.assertEqual(next_run("@DAILY", d), datetime(2026, 3, 5, 0, 0))
        self.assertEqual(next_run("@midnight", d), datetime(2026, 3, 5, 0, 0))
        self.assertEqual(next_run("@monthly", d), datetime(2026, 4, 1, 0, 0))
        self.assertEqual(next_run("@annually", d), datetime(2027, 1, 1, 0, 0))
        self.assertEqual(next_run("@yearly", d), datetime(2027, 1, 1, 0, 0))
        # 2026-03-04 is a Wednesday; next Sunday is 03-08
        self.assertEqual(next_run("@weekly", d), datetime(2026, 3, 8, 0, 0))

    def test_shortcut_bad(self):
        for bad in ["@always", "@daily x", "@ daily", "@Daily1"]:
            with self.assertRaises(ValueError, msg=bad):
                next_run(bad, datetime(2026, 1, 1))


class FieldSyntax(unittest.TestCase):
    def test_bad_field_count(self):
        for bad in ["", "* * * *", "* * * * * *", "* * * * ,"]:
            with self.assertRaises(ValueError, msg=bad):
                next_run(bad, datetime(2026, 1, 1))

    def test_out_of_range(self):
        bad = ["60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *",
               "* * * 0 *", "* * * 13 *", "* * * * 8", "* * * * 9-10",
               "* * * * 5-8"]
        for expr in bad:
            with self.assertRaises(ValueError, msg=expr):
                next_run(expr, datetime(2026, 1, 1))

    def test_range_order(self):
        with self.assertRaises(ValueError):
            next_run("* * * * FRI-MON", datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            next_run("10-5 * * * *", datetime(2026, 1, 1))

    def test_step_zero_and_bad(self):
        for expr in ["*/0 * * * *", "0-5/0 * * * *", "5/0 * * * *",
                     "*/-1 * * * *", "*/1.5 * * * *", "*/ * * * *", "*-5 * * * *"]:
            with self.assertRaises(ValueError, msg=expr):
                next_run(expr, datetime(2026, 1, 1))

    def test_empty_items(self):
        for expr in ["1,,2 * * * *", ",1 * * * *", "1, * * * *"]:
            with self.assertRaises(ValueError, msg=expr):
                next_run(expr, datetime(2026, 1, 1))

    def test_names_only_in_own_field(self):
        for expr in ["MON * * * *", "* JAN * * *", "* * * MON *", "* * * * JAN",
                     "* * * * 1-MON-FRI", "* * * * MO", "* * * * MONDAY"]:
            with self.assertRaises(ValueError, msg=expr):
                next_run(expr, datetime(2026, 1, 1))

    def test_names_case_insensitive(self):
        self.assertEqual(next_run("0 9 * jan mon-fri", datetime(2026, 1, 1)),
                         datetime(2026, 1, 1, 9, 0))  # Thursday; Jan 1 2026 is Thu
        self.assertEqual(next_run("0 9 * Jan Mon-Fri", datetime(2026, 1, 1, 9, 0)),
                         datetime(2026, 1, 2, 9, 0))

    def test_numbers_must_be_digits(self):
        for expr in ["+5 * * * *", "-5 * * * *", "5.0 * * * *", "0x5 * * * *"]:
            with self.assertRaises(ValueError, msg=expr):
                next_run(expr, datetime(2026, 1, 1))

    def test_steps_and_lists(self):
        self.assertEqual(next_run("1,5/2 * * * *", datetime(2026, 1, 1, 0, 0)),
                         datetime(2026, 1, 1, 0, 1))
        self.assertEqual(next_run("5/20 * * * *", datetime(2026, 1, 1, 0, 6)),
                         datetime(2026, 1, 1, 0, 25))  # 5, 25, 45
        self.assertEqual(next_run("10-30/10 * * * *", datetime(2026, 1, 1, 0, 25)),
                         datetime(2026, 1, 1, 0, 30))
        self.assertEqual(next_run("*/59 * * * *", datetime(2026, 1, 1, 0, 1)),
                         datetime(2026, 1, 1, 0, 59))  # minutes 0 and 59


class DayOfWeek(unittest.TestCase):
    # 2026-03-01 is Sunday, 03-02 Monday ... 03-07 Saturday
    def test_seven_is_sunday(self):
        for expr in ["0 0 * * 0", "0 0 * * 7", "0 0 * * SUN", "0 0 * * 0-0",
                     "0 0 * * 7-7", "0 0 * * SUN-SUN"]:
            self.assertEqual(next_run(expr, datetime(2026, 3, 2)),
                             datetime(2026, 3, 8, 0, 0), msg=expr)

    def test_range_into_seven(self):
        self.assertEqual(next_run("0 0 * * 5-7", datetime(2026, 3, 1)),
                         datetime(2026, 3, 6, 0, 0))  # Fri
        with self.assertRaises(ValueError):  # no wrap-around
            next_run("0 0 * * FRI-SUN", datetime(2026, 3, 7))

    def test_sat_not_sun(self):
        self.assertEqual(next_run("0 0 * * SAT", datetime(2026, 3, 1)),
                         datetime(2026, 3, 7, 0, 0))

    def test_step_seven(self):
        # 1/3 in dow = 1,4,7 -> Mon, Thu, Sun
        self.assertEqual(next_run("0 0 * * 1/3", datetime(2026, 3, 2)),
                         datetime(2026, 3, 5, 0, 0))
        self.assertEqual(next_run("0 0 * * 1/3", datetime(2026, 3, 5)),
                         datetime(2026, 3, 8, 0, 0))

    def test_invalid_dow(self):
        for expr in ["0 0 * * 8", "0 0 * * FRI-MON", "0 0 * * 6-5"]:
            with self.assertRaises(ValueError, msg=expr):
                next_run(expr, datetime(2026, 1, 1))


class DayMatching(unittest.TestCase):
    def test_or_when_both_restricted(self):
        # 1st or Friday, at 00:00 in March 2026. Fri is 03-06, 1st is 03-01 (Sun)
        self.assertEqual(next_run("0 0 1 * FRI", datetime(2026, 3, 1, 0, 0)),
                         datetime(2026, 3, 6, 0, 0))
        self.assertEqual(next_run("0 0 15 * FRI", datetime(2026, 3, 6, 0, 0)),
                         datetime(2026, 3, 13, 0, 0))

    def test_only_dom_restricted(self):
        # dow is "*": only the 15th counts, not Sundays
        self.assertEqual(next_run("0 0 15 * *", datetime(2026, 3, 1)),
                         datetime(2026, 3, 15, 0, 0))

    def test_only_dow_restricted(self):
        self.assertEqual(next_run("0 0 * * SUN", datetime(2026, 3, 9)),
                         datetime(2026, 3, 15, 0, 0))

    def test_star_slash_one_is_restricted(self):
        # "*/1" in dom is restricted, so OR applies with Friday
        self.assertEqual(next_run("0 0 */1 * FRI", datetime(2026, 3, 1)),
                         datetime(2026, 3, 2, 0, 0))

    def test_neither_restricted_is_every_day(self):
        self.assertEqual(next_run("0 0 * * *", datetime(2026, 2, 28, 1, 0)),
                         datetime(2026, 3, 1, 0, 0))

    def test_leap_day_with_dow_or(self):
        # Month is 2, so only February counts: first Feb 29th or Monday after
        # 2026-03-01 is Mon 2027-02-01 (no Feb 2026 match)
        self.assertEqual(next_run("0 0 29 2 MON", datetime(2026, 3, 1)),
                         datetime(2027, 2, 1, 0, 0))


if __name__ == "__main__":
    unittest.main()
