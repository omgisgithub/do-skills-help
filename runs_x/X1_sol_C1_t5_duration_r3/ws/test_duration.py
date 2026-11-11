import unittest

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_valid(self):
        cases = [
            ("1h30m", 5400),
            (" 2d 4h ", 187200),
            ("1.5h", 5400),
            ("1w2d3h4m5s", 788645),
            ("1:02:03", 3723),
            ("-45s", -45),
            ("0", 0),
            ("1h 30m", 5400),
            ("1.5m", 90),
            ("0.1h", 360),
            ("05m", 300),
            ("0.25m", 15),
            ("1:30", 90),
            ("1:00:00", 3600),
            ("90:00", 5400),
            ("-1h", -3600),
            ("-1:30", -90),
            ("-0s", 0),
            ("-0", 0),
            ("\t\n 1s \r\n", 1),
            ("000:59:59", 3599),
            ("99999999999999999999:00", 5999999999999999999940),
            ("0.015m0.1s", 1),
            ("1.000000000000000000000000000000s", 1),
            ("0w0d0h0m0s", 0),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)
                self.assertIs(type(parse_duration(value)), int)

    def test_invalid(self):
        cases = [
            ".5h", "5.h", "30m1h", "1h1h", "1 h", "0.3s",
            "1:60", "1:5", "5", "1.5", "", " \t\n",
            "1H", "1y", "+1h", "--1h", "- 1h", "1h-1m",
            "1h  30m", "1h\t30m", "1h\n30m", "1h,30m",
            "1:00:60", "1:60:00", "1:00:0", "1:000", "1:00:000",
            "1.5:00", "1:00.5", "1:00:00:00", "1 :00", "1: 00",
            "1:00s", "1e2s", "NaNs", "00", "0.0", "-5",
            "1.000000000000000000000000000001s", "1s\x00",
        ]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_duration(value)

    def test_non_strings(self):
        for value in (None, 0, 1.5, True, b"1h", [], {}):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)

    def test_unbounded_numbers(self):
        digits = "1" + "0" * 5000
        self.assertEqual(parse_duration(digits + ":00"), 10 ** 5000 * 60)
        self.assertEqual(parse_duration(digits + "s"), 10 ** 5000)


if __name__ == "__main__":
    unittest.main()
