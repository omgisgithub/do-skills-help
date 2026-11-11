"""Test the duration grammar and exact second conversion."""

import unittest

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    """Check accepted durations and invalid input boundaries."""

    def test_parse_duration_valid_input_returns_seconds(self) -> None:
        """Convert both forms, signs, whitespace, and exact fractions."""
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
            "0.1h": 360,
            "1.5m": 90,
            "0.01m0.4s": 1,
            "1:30": 90,
            "1:00:00": 3600,
            "90:00": 5400,
            "000:59": 59,
            "\t-1:30\n": -90,
            "1w 2d3h 4m5s": 788645,
            "123456789012345678901234567890s": 123456789012345678901234567890,
            "1.000000000000000000000000000000s": 1,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)

    def test_parse_duration_invalid_string_raises_value_error(self) -> None:
        """Reject syntax violations and fractional total seconds."""
        cases = (
            "", " ", "5", "1.5", "00", "+1h", "--1h", "- 1h", "-",
            ".5h", "5.h", "1H", "1 h", "1h  30m", "1h\t30m", "1h\n30m",
            "30m1h", "1h1h", "0s0m", "0.3s", "0.01m0.3s", "1e3s",
            "1h,30m", "1h-30m", "1h+30m", "1:60", "1:5", "1:00:60",
            "1:60:00", "1:2:03", "1:02:3", "1:00:00:00", "1 :30",
            "1: 30", "1.5:00", ":30", "1:", "1:30s", "١h", "１:30",
            "1.000000000000000000000000000001s", "1s!",
        )
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_duration(value)

    def test_parse_duration_non_string_raises_type_error(self) -> None:
        """Reject inputs outside the string boundary."""
        for value in (None, 1, 1.5, True, b"1s", [], {}):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)  # type: ignore[arg-type]  # Test invalid runtime inputs.


if __name__ == "__main__":
    unittest.main()
