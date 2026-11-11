import unittest

from duration import parse_duration


class SpecExamples(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration(" 2d 4h "), 187200)
        self.assertEqual(parse_duration("1.5h"), 5400)
        self.assertEqual(parse_duration("1w2d3h4m5s"), 788645)
        self.assertEqual(parse_duration("1:02:03"), 3723)
        self.assertEqual(parse_duration("-45s"), -45)
        self.assertEqual(parse_duration("0"), 0)


class UnitForm(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_duration("1w"), 604800)
        self.assertEqual(parse_duration("1d"), 86400)
        self.assertEqual(parse_duration("10s"), 10)
        self.assertEqual(parse_duration("1.5m"), 90)
        self.assertEqual(parse_duration("0.25h"), 900)
        self.assertEqual(parse_duration("0.1h"), 360)
        self.assertEqual(parse_duration("05m"), 300)
        self.assertEqual(parse_duration("1h 30m"), 5400)
        self.assertEqual(parse_duration("1h30m"), 5400)

    def test_invalid(self):
        for bad in [
            ".5h", "5.h", "0.3s", "30m1h", "1h1h", "1 h", "1h  30m",
            "1H", "1M", "1hour", "1h,30m", "1h\t30m", "1x", "h", "1.2.3s",
            "1h-30m", "1+h", "1h 30m;", "1e3s",
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_duration(bad)


class ClockForm(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_duration("1:30"), 90)
        self.assertEqual(parse_duration("1:00:00"), 3600)
        self.assertEqual(parse_duration("90:00"), 5400)
        self.assertEqual(parse_duration("123:59:59"), 123 * 3600 + 3599)

    def test_invalid(self):
        for bad in [
            "1:60", "1:5", "1:00:60", "1:0:00", "1:00:5", "1.5:00",
            "1:30.5", "1:2:3:4", ":30", "1:", "01:3", "1::30", "1:30h",
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_duration(bad)


class SignAndBare(unittest.TestCase):
    def test_sign(self):
        self.assertEqual(parse_duration("-1h"), -3600)
        self.assertEqual(parse_duration("-1:30"), -90)
        self.assertEqual(parse_duration("-0s"), 0)

    def test_invalid_sign(self):
        for bad in ["+1h", "--1h", "- 1h", "-", "+0", "-5", "-1.5"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_duration(bad)

    def test_bare_numbers(self):
        for bad in ["5", "1.5", "00", "0.0", "-0", "0.5"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_duration(bad)


class Whitespace(unittest.TestCase):
    def test_empty(self):
        for bad in ["", "   ", "\t"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_duration(bad)


class Types(unittest.TestCase):
    def test_non_str(self):
        for bad in [None, 5, 1.5, b"1h", ["1h"]]:
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                parse_duration(bad)


if __name__ == "__main__":
    unittest.main()
