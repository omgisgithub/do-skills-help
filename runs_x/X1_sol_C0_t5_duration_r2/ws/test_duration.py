import unittest

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_valid_durations(self):
        cases = {
            "1h30m": 5400,
            " 2d 4h ": 187200,
            "1.5h": 5400,
            "1w2d3h4m5s": 788645,
            "1:02:03": 3723,
            "-45s": -45,
            "0": 0,
            "-0": 0,
            "-0s": 0,
            "05m": 300,
            "1.5m": 90,
            "0.1h": 360,
            "0.01m0.4s": 1,
            "0.0000000000000000000000000000000000000000s": 0,
            "1:30": 90,
            "90:00": 5400,
            "1:00:00": 3600,
            "-1:30": -90,
            "\t\n1h 30m\r\n": 5400,
            "1w 2d3h 4m5s": 788645,
            "000:00": 0,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)
                self.assertIs(type(parse_duration(value)), int)

    def test_invalid_durations(self):
        cases = [
            "", " \t\n", "-", "+1h", "--1h", "- 1h", "5", "1.5", "00",
            ".5h", "5.h", "1 h", "1H", "30m1h", "1h1h", "0s0m",
            "1h  30m", "1h\t30m", "1h\n30m", "1h,30m", "1h-30m",
            "0.3s", "1.0000000000000000000000000000000000000001s",
            "1:60", "1:5", "1:2:03", "1:60:00", "1:00:60", "1:00:00:00",
            "1 :30", "1: 30", "1.5:00", "1:30s", "1e3s", "NaNs",
            "١h", "１:30", "1h\u00a030m", "1s junk", "-+0",
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

    def test_unbounded_first_clock_field(self):
        self.assertEqual(parse_duration("1" + "0" * 5000 + ":00"), 10 ** 5000 * 60)


if __name__ == "__main__":
    unittest.main()
