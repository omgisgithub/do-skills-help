import unittest

from duration import parse_duration


class SpecExamples(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration(" 2d 4h "), 187200)
        self.assertEqual(parse_duration("1.5h"), 5400)
        self.assertEqual(parse_duration("1w2d3h4m5s"), 788645)
        self.assertEqual(parse_duration("1:02:03"), 3723)
        self.assertEqual(parse_duration("-45s"), -45)
        self.assertEqual(parse_duration("0"), 0)

    def test_inline_examples(self):
        self.assertEqual(parse_duration("1:30"), 90)
        self.assertEqual(parse_duration("1:00:00"), 3600)
        self.assertEqual(parse_duration("90:00"), 5400)
        self.assertEqual(parse_duration("-1h"), -3600)
        self.assertEqual(parse_duration("-1:30"), -90)
        self.assertEqual(parse_duration("1.5m"), 90)
        self.assertEqual(parse_duration("0.1h"), 360)
        self.assertEqual(parse_duration("-0s"), 0)
        self.assertEqual(parse_duration("05m"), 300)
        self.assertEqual(parse_duration("1h 30m"), 5400)


class Valid(unittest.TestCase):
    def test_valid_forms(self):
        cases = {
            "10s": 10,
            "0.25h": 900,
            "\t1h\n": 3600,
            "1h30m 15s": 5415,
            "1h30m15s": 5415,
            "1h30m ": 5400,
            "0h": 0,
            "0:00": 0,
            "0:00:00": 0,
            "00:59": 59,
            "0:59:59": 3599,
            "100:00:00": 360000,
            "  -1:30  ": -90,
            "0.5w": 302400,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text), expected)


class Invalid(unittest.TestCase):
    def assertInvalid(self, text):
        with self.subTest(text=text):
            with self.assertRaises(ValueError):
                parse_duration(text)

    def test_leading_or_trailing_dot(self):
        self.assertInvalid(".5h")
        self.assertInvalid("5.h")

    def test_wrong_case(self):
        self.assertInvalid("1H")
        self.assertInvalid("1M")
        self.assertInvalid("1S")

    def test_units_out_of_order_or_repeated(self):
        self.assertInvalid("30m1h")
        self.assertInvalid("1h1h")
        self.assertInvalid("1s1m")

    def test_space_between_number_and_unit(self):
        self.assertInvalid("1 h")

    def test_extra_or_other_separators(self):
        self.assertInvalid("1h  30m")
        self.assertInvalid("1h,30m")
        self.assertInvalid("1h-30m")
        self.assertInvalid("1h\t30m")

    def test_fraction_not_whole_seconds(self):
        self.assertInvalid("0.3s")
        self.assertInvalid("0.1s")

    def test_missing_or_unknown_unit(self):
        self.assertInvalid("5")
        self.assertInvalid("1.5")
        self.assertInvalid("5x")
        self.assertInvalid("5ms")

    def test_plus_sign(self):
        self.assertInvalid("+1h")
        self.assertInvalid("+1:30")

    def test_bad_minus(self):
        self.assertInvalid("--1h")
        self.assertInvalid("- 1h")
        self.assertInvalid("-  1:30")

    def test_bare_numbers(self):
        self.assertInvalid("5")
        self.assertInvalid("1.5")
        self.assertInvalid("00")
        self.assertInvalid("-5")
        self.assertInvalid("-0")

    def test_empty_and_whitespace(self):
        self.assertInvalid("")
        self.assertInvalid("   ")
        self.assertInvalid("-")

    def test_clock_bad_fields(self):
        self.assertInvalid("1:60")
        self.assertInvalid("1:5")
        self.assertInvalid("1:00:5")
        self.assertInvalid("1:00:60")
        self.assertInvalid("1:1:00")
        self.assertInvalid("1:30.5")
        self.assertInvalid("1:")
        self.assertInvalid(":30")
        self.assertInvalid("1:2:3:4")

    def test_clock_with_unit_or_inner_space(self):
        self.assertInvalid("1:30m")
        self.assertInvalid("1: 30")
        self.assertInvalid("1 :30")

    def test_missing_number(self):
        self.assertInvalid("h")
        self.assertInvalid("1h30")

    def test_non_ascii_digits(self):
        self.assertInvalid("١h")  # Arabic-Indic digit one
        self.assertInvalid("١:30")

    def test_non_str_raises_type_error(self):
        for value in (None, 5, 1.5, b"1h", ["1h"]):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)


if __name__ == "__main__":
    unittest.main()
