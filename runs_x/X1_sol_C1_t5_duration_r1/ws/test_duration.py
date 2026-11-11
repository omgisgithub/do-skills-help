import unittest

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_spec_examples(self):
        examples = {
            "1h30m": 5400,
            " 2d 4h ": 187200,
            "1.5h": 5400,
            "1w2d3h4m5s": 788645,
            "1:02:03": 3723,
            "-45s": -45,
            "0": 0,
            "1h 30m": 5400,
            "05m": 300,
            "1.5m": 90,
            "0.1h": 360,
            "1:30": 90,
            "1:00:00": 3600,
            "90:00": 5400,
            "-1h": -3600,
            "-1:30": -90,
            "-0s": 0,
        }
        for value, expected in examples.items():
            with self.subTest(value=value):
                assert parse_duration(value) == expected

    def test_valid_boundaries_and_exact_arithmetic(self):
        examples = {
            "1w": 604800, "1d": 86400, "1h": 3600,
            "1m": 60, "1s": 1, "10s": 10, "0.25m": 15,
            "\t\n -1h 30m \r\n": -5400,
            "-0": 0, "00s": 0, "0001:59": 119,
            "99999999999999999999:00": 5999999999999999999940,
            "0:59:59": 3599,
            "0.1m0.0000000000000000000000000000000000s": 6,
            "0.0001h0.64s": 1,
            "1.0000000000000000000000000000000000s": 1,
        }
        for value, expected in examples.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)
                self.assertIs(type(parse_duration(value)), int)

    def test_invalid_strings(self):
        invalid = [
            "", " \t\n", "5", "1.5", "00", "0.0", "-00",
            ".5h", "5.h", "1..5h", "1e2s", "1_000s",
            "30m1h", "1h1h", "0s0m", "1H", "1y", "1ms",
            "1 h", "1h  30m", "1h\t30m", "1h\n30m", "1h,30m",
            "0.3s", "0.0000000000000000000000000000000001s",
            "1:60", "1:5", "1:00:60", "1:60:00", "1:000",
            "1.5:00", "1:00.5", "1:00:00:00", ":00", "1:",
            "1 :00", "1: 00", "+1h", "+0", "--1h", "- 1h",
            "1h-30m", "1:00s", "١s", "１:00", "1\u00a0h",
        ]
        for value in invalid:
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
