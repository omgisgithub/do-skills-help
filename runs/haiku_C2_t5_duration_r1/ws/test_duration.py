import unittest

from duration import parse_duration


class ParseDurationTest(unittest.TestCase):
    def test_valid(self):
        cases = {
            "1h30m": 5400,
            " 2d 4h ": 187200,
            "1.5h": 5400,
            "1w2d3h4m5s": 788645,
            "1:02:03": 3723,
            "-45s": -45,
            "0": 0,
            "-0s": 0,
            "1:30": 90,
            "90:00": 5400,
            "-1:30": -90,
            "1.5m": 90,
            "0.1h": 360,
            "05m": 300,
            "1h 30m": 5400,
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text), want)

    def test_invalid(self):
        for text in [
            "", "   ", "5", "1.5", "-0", "00", ".5h", "5.h", "1 h", "30m1h", "1h1h",
            "0.3s", "1:60", "1:5", "1:30.5", "+1h", "- 1h", "1h  30m", "1H", "1\t h",
            "1:2:3", "١h",
        ]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_duration(text)

    def test_type(self):
        with self.assertRaises(TypeError):
            parse_duration(5)


if __name__ == "__main__":
    unittest.main()
