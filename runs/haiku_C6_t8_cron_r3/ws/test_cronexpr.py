import unittest
from datetime import datetime

from cronexpr import next_run


class SpecExamples(unittest.TestCase):
    def test_every_15_minutes(self):
        self.assertEqual(next_run("*/15 * * * *", datetime(2026, 3, 4, 10, 7)),
                         datetime(2026, 3, 4, 10, 15))

    def test_weekdays_friday_to_monday(self):
        self.assertEqual(next_run("0 9 * * MON-FRI", datetime(2026, 3, 6, 9, 0)),
                         datetime(2026, 3, 9, 9, 0))

    def test_leap_day(self):
        self.assertEqual(next_run("0 0 29 2 *", datetime(2026, 3, 1)),
                         datetime(2028, 2, 29, 0, 0))

    def test_dom_or_dow(self):
        self.assertEqual(next_run("30 4 1,15 * 5", datetime(2026, 1, 1, 5, 0)),
                         datetime(2026, 1, 2, 4, 30))

    def test_no_match_raises(self):
        with self.assertRaises(ValueError):
            next_run("0 0 30 2 *", datetime(2026, 1, 1))


class Result(unittest.TestCase):
    def test_strictly_later_from_seconds(self):
        self.assertEqual(next_run("* * * * *", datetime(2026, 1, 1, 12, 0, 30)),
                         datetime(2026, 1, 1, 12, 1))

    def test_strictly_later_on_boundary(self):
        self.assertEqual(next_run("* * * * *", datetime(2026, 1, 1, 12, 0, 0)),
                         datetime(2026, 1, 1, 12, 1))
        self.assertEqual(next_run("0 * * * *", datetime(2026, 1, 1, 12, 0, 0)),
                         datetime(2026, 1, 1, 13, 0))

    def test_result_has_zero_seconds(self):
        r = next_run("* * * * *", datetime(2026, 1, 1, 12, 0, 59, 999999))
        self.assertEqual((r.second, r.microsecond), (0, 0))

    def test_year_rollover(self):
        self.assertEqual(next_run("0 0 1 1 *", datetime(2026, 3, 4)),
                         datetime(2027, 1, 1))

    def test_no_match_in_five_years_raises(self):
        with self.assertRaises(ValueError):
            next_run("0 0 31 4 *", datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            next_run("0 0 30 2 *", datetime(2026, 1, 1))

    def test_leap_day_found_when_after_is_on_leap_day(self):
        self.assertEqual(next_run("0 0 29 2 *", datetime(2028, 2, 29, 0, 0)),
                         datetime(2032, 2, 29, 0, 0))


class Fields(unittest.TestCase):
    def test_ranges_and_lists(self):
        self.assertEqual(next_run("5,10-12 * * * *", datetime(2026, 1, 1, 0, 0)),
                         datetime(2026, 1, 1, 0, 5))
        self.assertEqual(next_run("5,10-12 * * * *", datetime(2026, 1, 1, 0, 5)),
                         datetime(2026, 1, 1, 0, 10))

    def test_step_on_range(self):
        self.assertEqual(next_run("1-10/3 * * * *", datetime(2026, 1, 1, 0, 1)),
                         datetime(2026, 1, 1, 0, 4))
        self.assertEqual(next_run("1-10/3 * * * *", datetime(2026, 1, 1, 0, 10)),
                         datetime(2026, 1, 1, 1, 1))

    def test_step_on_single_value_runs_to_field_max(self):
        self.assertEqual(next_run("5/20 * * * *", datetime(2026, 1, 1, 12, 25)),
                         datetime(2026, 1, 1, 12, 45))
        self.assertEqual(next_run("5/20 * * * *", datetime(2026, 1, 1, 12, 45)),
                         datetime(2026, 1, 1, 13, 5))

    def test_names_case_insensitive(self):
        self.assertEqual(next_run("0 9 * * mon-fri", datetime(2026, 3, 6, 9, 0)),
                         datetime(2026, 3, 9, 9, 0))
        self.assertEqual(next_run("0 0 1 jan-mar *", datetime(2026, 1, 15)),
                         datetime(2026, 2, 1))

    def test_dow_zero_seven_and_sun_are_sunday(self):
        # 2026-03-06 is a Friday; the next Sunday is 2026-03-08.
        for expr in ("0 9 * * 0", "0 9 * * 7", "0 9 * * SUN", "0 9 * * sun"):
            self.assertEqual(next_run(expr, datetime(2026, 3, 6, 9, 0)),
                             datetime(2026, 3, 8, 9, 0), expr)

    def test_dow_7_inside_range(self):
        # 5-7 is Fri, Sat, Sun: from Thursday 2026-03-05 the next is Fri 2026-03-06.
        self.assertEqual(next_run("0 0 * * 5-7", datetime(2026, 3, 5, 12, 0)),
                         datetime(2026, 3, 6, 0, 0))

    def test_star_with_step_starts_at_field_minimum(self):
        self.assertEqual(next_run("*/2 * * * *", datetime(2026, 1, 1, 0, 0)),
                         datetime(2026, 1, 1, 0, 2))
        self.assertEqual(next_run("0 */5 * * *", datetime(2026, 1, 1, 4, 0)),
                         datetime(2026, 1, 1, 5, 0))


class DayMatching(unittest.TestCase):
    def test_dom_and_dow_either_matches(self):
        # 2026-03-13 is a Friday, the 15th is later: the Friday wins.
        self.assertEqual(next_run("0 12 15 * FRI", datetime(2026, 3, 7, 0, 0)),
                         datetime(2026, 3, 13, 12, 0))

    def test_only_dom_restricted(self):
        self.assertEqual(next_run("0 12 15 * *", datetime(2026, 3, 7, 0, 0)),
                         datetime(2026, 3, 15, 12, 0))

    def test_only_dow_restricted(self):
        self.assertEqual(next_run("0 12 * * FRI", datetime(2026, 3, 7, 0, 0)),
                         datetime(2026, 3, 13, 12, 0))

    def test_star_step_dom_counts_as_restricted(self):
        # */2 on dom is restricted, so odd days OR Mondays match.
        # Mon 2026-03-16 is even, so the OR picks the odd day 11, not a Monday.
        self.assertEqual(next_run("0 0 */2 * MON", datetime(2026, 3, 10, 12, 0)),
                         datetime(2026, 3, 11, 0, 0))

    def test_dow_range_covering_all_days_is_still_restricted(self):
        # "0-6" is not exactly "*", so both fields are restricted and the OR
        # makes every day match, so the next minute is 2026-03-02 00:00.
        self.assertEqual(next_run("0 0 1 * 0-6", datetime(2026, 3, 1, 0, 0)),
                         datetime(2026, 3, 2, 0, 0))


class Shortcuts(unittest.TestCase):
    def test_all_shortcuts(self):
        after = datetime(2026, 3, 4, 10, 30)  # Wednesday
        cases = {
            "@hourly": datetime(2026, 3, 4, 11, 0),
            "@daily": datetime(2026, 3, 5, 0, 0),
            "@midnight": datetime(2026, 3, 5, 0, 0),
            "@weekly": datetime(2026, 3, 8, 0, 0),
            "@monthly": datetime(2026, 4, 1, 0, 0),
            "@yearly": datetime(2027, 1, 1, 0, 0),
            "@annually": datetime(2027, 1, 1, 0, 0),
        }
        for expr, expected in cases.items():
            self.assertEqual(next_run(expr, after), expected, expr)

    def test_shortcut_case_insensitive_and_trimmed(self):
        self.assertEqual(next_run("  @YEARLY \t", datetime(2026, 3, 4)),
                         datetime(2027, 1, 1))


class Whitespace(unittest.TestCase):
    def test_tabs_and_multiple_spaces_and_outer_whitespace(self):
        self.assertEqual(next_run("  0\t9   *  * MON-FRI \t", datetime(2026, 3, 6, 9, 0)),
                         datetime(2026, 3, 9, 9, 0))


class Types(unittest.TestCase):
    def test_non_str_is_type_error(self):
        for bad in (None, 5, b"* * * * *", ["* * * * *"]):
            with self.assertRaises(TypeError, msg=repr(bad)):
                next_run(bad, datetime(2026, 1, 1))


class MustFail(unittest.TestCase):
    """One or more inputs per rule that must be rejected with ValueError."""

    BAD = [
        "",                      # empty
        "* * * *",               # 4 fields
        "* * * * * *",           # 6 fields
        "1, 2 * * * *",          # space after comma splits fields
        "1,,2 * * * *",          # empty item
        "1, * * * *",            # trailing comma
        ",1 * * * *",            # leading comma
        "60 * * * *",            # minute out of range
        "* 24 * * *",            # hour out of range
        "* * 0 * *",             # day of month 0
        "* * 32 * *",            # day of month out of range
        "* * * 0 *",             # month 0
        "* * * 13 *",            # month out of range
        "* * * * 8",             # dow out of range
        "* * * * 9",
        "*/0 * * * *",           # step 0
        "1-10/0 * * * *",        # step 0 on range
        "5/0 * * * *",           # step 0 on value
        "5-1 * * * *",           # reversed range
        "* * * * FRI-MON",       # wrap-around not allowed
        "0 0 * * FRI-MON",       # wrap-around in dow
        "0 0 * * MON-SUN",       # SUN is 0, so MON-SUN runs backwards
        "0 0 * * FRI-SUN",       # same reason
        "MON-FRI * * * *",       # names only in month and dow
        "* JAN * * *",           # names not allowed in hour
        "* * JAN * *",           # names not allowed in dom
        "* * * * MONDAY",        # full names not allowed
        "* * * jan-13 *",        # name range end out of range
        "* * * * mon-",          # incomplete range
        "* * * * -5",            # leading dash
        "* * * * 5-",            # trailing dash
        "*-5 * * * *",           # star cannot be a range
        "1.5 * * * *",           # decimal
        "-1 * * * *",            # negative
        "+1 * * * *",            # sign
        "a * * * *",             # junk
        "*/ * * * *",            # missing step digits
        "*/x * * * *",
        "1/* * * * *",           # star cannot be a step
        "1//2 * * * *",          # double slash
        "1/2/3 * * * *",
        "0 0 * * 1 2",           # 6 fields
        "0\n0 * * * *",          # newline inside the expression
        "@reboot",               # unsupported shortcut
        "@yearly x",             # shortcut plus extra text
        "@every 5m",
        "@YEARLY-",
    ]

    def test_bad_expressions_raise_value_error(self):
        for expr in self.BAD:
            with self.assertRaises(ValueError, msg=repr(expr)):
                next_run(expr, datetime(2026, 1, 1))

    def test_dow_positives_matching_the_negatives(self):
        # Sanity check that the same dow values are accepted, so the rejections above are not just "everything fails".
        ok = {
            "0 0 * * 7": datetime(2026, 3, 8, 0, 0),
            "0 0 * * 0": datetime(2026, 3, 8, 0, 0),
            "0 0 * * sat": datetime(2026, 3, 7, 0, 0),
            "0 0 * * 6": datetime(2026, 3, 7, 0, 0),
        }
        for expr, expected in ok.items():
            self.assertEqual(next_run(expr, datetime(2026, 3, 6, 9, 0)), expected, expr)


if __name__ == "__main__":
    unittest.main()
