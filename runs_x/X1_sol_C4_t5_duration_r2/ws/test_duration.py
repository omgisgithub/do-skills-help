"""Test the scheduler duration grammar and exact arithmetic."""

import unittest
from decimal import localcontext

from duration import parse_duration


class DurationTests(unittest.TestCase):
    """Check accepted durations and rejection of malformed input."""

    def test_parse_duration_valid_forms_returns_seconds(self) -> None:
        cases = {
            "1h30m": 5400,
            " 2d 4h ": 187200,
            "1.5h": 5400,
            "1w2d3h4m5s": 788645,
            "1w 2d3h 4m5s": 788645,
            "1:02:03": 3723,
            "1:30": 90,
            "1:00:00": 3600,
            "90:00": 5400,
            "001:02": 62,
            "-45s": -45,
            "-1h": -3600,
            "-1:30": -90,
            "\t\n-1m\r\n": -60,
            "0": 0,
            "-0": 0,
            "-0s": 0,
            "0w0d0h0m0s": 0,
            "05m": 300,
            "1.5m": 90,
            "0.1h": 360,
            "0.25m": 15,
            "0.01m0.4s": 1,
            "0.001h0.4s": 4,
            "1.0000000000000000000000000000000000000000s": 1,
            "999999999999999999999999999999:59": 60 * (10**30 - 1) + 59,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text), expected)

    def test_parse_duration_invalid_forms_raises_value_error(self) -> None:
        cases = (
            "", " \t\n", "-", "+1h", "--1h", "- 1h", "1h-30m", "5", "00", "1.5",
            ".5h", "5.h", "1..5h", "1e2s", "1H", "1y", "1 h", "1h  30m",
            "1h\t30m", "1h\n30m", "1h\u00a030m", "1h,30m", "1h_30m",
            "30m1h", "1h1h", "0s0m", "1h30m1h", "0.3s", "-0.3s", "0.01m",
            "0.000000000000000000000000000000000000001s",
            "1.000000000000000000000000000000000000001s",
            "1:60", "1:5", "1:000", "1:00:60", "1:60:00", "1:2:03",
            "1:00:00:00", "1:00.00", "1: 00", "1 :00", ":00", "1:", "1:00s",
            "1h1:00", "\u0661h", "1:\u0660\u0660", "1s junk", "NaNs", "Infs",
        )
        for text in cases:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)

    def test_parse_duration_low_decimal_precision_preserves_exact_total(self) -> None:
        with localcontext() as context:
            context.prec = 2

            self.assertEqual(parse_duration("123456789.5m"), 7407407370)
            with self.assertRaises(ValueError):
                parse_duration("1.00000000000000000000000001s")

    def test_parse_duration_non_string_raises_type_error(self) -> None:
        for value in (None, 0, 1.5, True, b"1h", [], {}):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)  # type: ignore[arg-type]  # Exercise invalid input types.


if __name__ == "__main__":
    unittest.main()
