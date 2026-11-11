import unittest

from duration import parse_duration


class ParseDurationTest(unittest.TestCase):
    def test_valid(self):
        cases = {
            "1h30m": 5400,
            " 2d 4h ": 187200,
            "1.5h": 5400,
            "1w2d3h4m5s": 788645,
            "1h 30m": 5400,
            "05m": 300,
            "1.5m": 90,
            "0.1h": 360,
            "0m": 0,
            "1:02:03": 3723,
            "1:30": 90,
            "90:00": 5400,
            "-45s": -45,
            "-1h": -3600,
            "-1:30": -90,
            "-0s": 0,
            "0": 0,
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text), want)

    def test_invalid(self):
        cases = [
            "", "   ", "5", "1.5", "00", ".5h", "5.h", "1 h", "30m1h", "1h1h",
            "1h  30m", "1h\t30m", "0.3s", "+1h", "--1h", "- 1h", "1:60", "1:5",
            "1:2:03", "1:00:0", "1:30.5", "1:30:", "١h",
        ]
        for text in cases:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)

    def test_non_str(self):
        for value in (None, 5, b"1h"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)


if __name__ == "__main__":
    unittest.main()
