import unittest

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_spec_examples(self):
        assert parse_duration("1h30m") == 5400
        assert parse_duration(" 2d 4h ") == 187200
        assert parse_duration("1.5h") == 5400
        assert parse_duration("1w2d3h4m5s") == 788645
        assert parse_duration("1:02:03") == 3723
        assert parse_duration("-45s") == -45
        assert parse_duration("0") == 0

    def test_valid_forms(self):
        cases = {
            "1h 30m": 5400, "1.5m": 90, "0.1h": 360,
            "05m": 300, "0.25m": 15, "1:30": 90,
            "1:00:00": 3600, "90:00": 5400, "-1h": -3600,
            "-1:30": -90, "-0s": 0, "-0": 0,
            "\t\n 1s \r\n": 1, "000:00:59": 59,
            "1000:59:59": 3603599, "0.01m0.4s": 1,
            "0.1000000000000000000000000000000000000000h": 360,
            "1w": 604800, "1d": 86400, "1h": 3600,
            "1m": 60, "1s": 1, "00s": 0,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)
                self.assertIsInstance(parse_duration(value), int)

    def test_invalid_forms(self):
        cases = [
            "", " \t\n", "5", "1.5", "00", ".5h", "5.h",
            "30m1h", "1h1h", "0s0m", "1 h", "1h  30m",
            "1h\t30m", "1h\n30m", "1h,30m", "1H", "1ms",
            "0.3s", "0.000000000000000000000000000000000000001s",
            "1:60", "1:5", "1:60:00", "1:00:60", "1:0:00",
            "1:00:0", "1:000", "1:00:00:00", "1.5:00",
            "1: 00", "1 :00", "1:00s", "+1s", "--1s", "- 1s",
            "1s-", "1e2s", "NaNs", "١s", "１:00", "1h\u00a030m",
        ]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_duration(value)

    def test_non_strings(self):
        for value in [None, 0, 1.5, True, b"1s", [], {}]:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)


if __name__ == "__main__":
    unittest.main()
