"""Test duration grammar and exact conversion to seconds."""

import unittest

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    """Check accepted durations and rejected inputs."""

    def test_parse_duration_valid_returns_seconds(self) -> None:
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
            "0.25m": 15,
            "0.01m0.4s": 1,
            "1:30": 90,
            "1:00:00": 3600,
            "90:00": 5400,
            "-1:30": -90,
            "000:00": 0,
            "1h 30m5s": 5405,
            "\t\n-1h\r\n": -3600,
            "9007199254740993s": 9007199254740993,
            "100000000000000000000:00": 6000000000000000000000,
            "1.000000000000000000000000000000s": 1,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text), expected)
                self.assertIs(type(parse_duration(text)), int)

    def test_parse_duration_invalid_raises_value_error(self) -> None:
        cases = (
            "", " \t\n", "-", "+1h", "--1h", "- 1h", "5", "1.5", "00",
            ".5h", "5.h", "1 h", "1H", "30m1h", "1h1h", "0s0m",
            "1h  30m", "1h\t30m", "1h\n30m", "1h,30m", "1h-30m",
            "0.3s", "0.000000000000000000000000000001s",
            "1.000000000000000000000000000001s", "1:60", "1:5",
            "1:00:60", "1:60:00", "1:2:03", "1:02:3", "1:00:00:00",
            "1 :30", "1: 30", "1.5:30", "1:30s", "1e3s", "1_000s",
            "NaNs", "infs", "1m garbage", "1h\u00a030m", "١h", "１:00",
        )
        for text in cases:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)

    def test_parse_duration_non_string_raises_type_error(self) -> None:
        for value in (None, 0, 1.5, True, b"1h", [], {}):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)  # type: ignore[arg-type]  # Test invalid runtime inputs.
