import unittest

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_unit_forms(self):
        cases = {
            "1h30m": 5400,
            " 2d 4h ": 187200,
            "1w2d3h4m5s": 788645,
            "1w": 604800,
            "05m": 300,
            "1h 30m5s": 5405,
            "0w0d0h0m0s": 0,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)

    def test_exact_decimal_totals(self):
        for value, expected in {
            "1.5h": 5400,
            "1.5m": 90,
            "0.1h": 360,
            "0.25m": 15,
            "0.01m0.4s": 1,
            "1.000000000000000000000000000000s": 1,
        }.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)

    def test_clock_forms(self):
        for value, expected in {
            "1:30": 90,
            "1:00:00": 3600,
            "90:00": 5400,
            "1:02:03": 3723,
            "000:59": 59,
            "24:59:59": 89999,
            "12345678901234567890:00": 740740734074074073400,
        }.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)

    def test_sign_and_outer_whitespace(self):
        for value, expected in {
            "0": 0, "-0": 0, "-0s": 0, "-45s": -45,
            "-1h": -3600, "-1:30": -90, "\t -1h30m\n": -5400,
        }.items():
            with self.subTest(value=value):
                result = parse_duration(value)
                self.assertIs(type(result), int)
                self.assertEqual(result, expected)

    def test_invalid_grammar(self):
        cases = [
            "", " \t\n", "5", "1.5", "00", "0.0", ".5h", "5.h",
            "1 h", "1h  30m", "1h\t30m", "1h\n30m", "1h,30m",
            "30m1h", "1h1h", "0s0m", "1H", "1ms", "1e3s",
            "+1h", "--1h", "- 1h", "1h-30m", "1h+30m", "1h junk",
            "1:60", "1:5", "1:00:60", "1:60:00", "1:2:03",
            "1:00:00:00", "1.5:00", "1:00s", "1 :00", "1: 00",
            "1:00\n:00", ":00", "1:", "1:00.0", "NaN", "inf",
            "0.3s", "0.000000000000000000000000000001s",
            "1.000000000000000000000000000001s", "0.01m0.3s",
            "١h", "１:00", "1:٠٠",
        ]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_duration(value)

    def test_non_string_inputs(self):
        for value in [None, 0, 1.5, True, b"1h", [], {}]:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)


if __name__ == "__main__":
    unittest.main()
