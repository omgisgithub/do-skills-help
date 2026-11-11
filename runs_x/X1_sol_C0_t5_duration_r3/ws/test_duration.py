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
            "0.001m0.94s": 1,
            "0.00000000000000000001w0.999999999999993952s": 1,
            "1w 2d3h 4m5s": 788645,
            "1:30": 90,
            "1:00:00": 3600,
            "90:00": 5400,
            "0001:09": 69,
            "-1:30": -90,
            "\t\n-1h\r\n": -3600,
            "12345678901234567890:00": 740740734074074073400,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                result = parse_duration(value)
                self.assertEqual(result, expected)
                self.assertIs(type(result), int)

    def test_invalid_durations(self):
        cases = [
            "", " \t\n", "-", "+1h", "--1h", "- 1h", "5", "1.5", "00",
            ".5h", "5.h", "1 h", "1H", "1h  30m", "1h\t30m", "1h\n30m",
            "1h,30m", "30m1h", "1h1h", "0s0m", "1h-1m", "0.3s",
            "0.00000000000000000001s", "1e2s", "1_000s", "١h", "１s",
            "1:60", "1:5", "1:00:60", "1:60:00", "1:00:0", "1:00:00:00",
            "1.0:00", "1 :00", "1: 00", "1:00s", "1:00\n:00", "-+0",
        ]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_duration(value)

    def test_non_strings(self):
        for value in (None, 0, 1.5, b"1h", [], {}):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)


if __name__ == "__main__":
    unittest.main()
