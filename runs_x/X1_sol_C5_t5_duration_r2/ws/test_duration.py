import unittest

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_unit_values(self):
        cases = {
            "1h30m": 5400,
            " 2d 4h ": 187200,
            "1w2d3h4m5s": 788645,
            "1w": 604800,
            "1d": 86400,
            "05m": 300,
            "0w0d0h0m0s": 0,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)

    def test_exact_fractional_totals(self):
        cases = {
            "1.5h": 5400,
            "1.5m": 90,
            "0.1h": 360,
            "0.25m": 15,
            "0.01m0.4s": 1,
            "0.0001h0.0105m0.01s": 1,
            "9007199254740993s": 9007199254740993,
            "1.000000000000000000000000000000s": 1,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)

    def test_clock_values(self):
        cases = {
            "1:30": 90,
            "1:00:00": 3600,
            "1:02:03": 3723,
            "90:00": 5400,
            "0001:02": 62,
            "0:59:59": 3599,
            "99999999999999999999:00": 5999999999999999999940,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)

    def test_sign_zero_and_outer_whitespace(self):
        cases = {
            "0": 0, "-0": 0, "-0s": 0, "-1h": -3600,
            "-1:30": -90, "-45s": -45, "\t\n -1h \r\n": -3600,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                result = parse_duration(value)
                self.assertEqual(result, expected)
                self.assertIs(type(result), int)

    def test_invalid_strings(self):
        cases = [
            "", " \t\n", "-", "+1h", "--1h", "- 1h", "5", "1.5",
            "00", "-00", ".5h", "5.h", "1e2s", "1H", "1ms", "1 h",
            "1h1h", "30m1h", "1s0m", "0s0s", "1h  30m", "1h\t30m",
            "1h\n30m", "1h\u00a030m", "1h,30m", "1h-30m", "1h+30m",
            "1:60", "1:5", "1:00:60", "1:60:00", "1:2:03", "1:02:3",
            "1:00:00:00", ":30", "1:", "1 :30", "1: 30", "1.5:00",
            "1:30s", "1h:30", "0.3s", "0.000000000000000000000000000001s",
            "١h", "１:00", "1h garbage", "1s\x00",
        ]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_duration(value)

    def test_non_strings(self):
        for value in [None, 0, 1.5, True, b"1h", [], {}]:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)


if __name__ == "__main__":
    unittest.main()
