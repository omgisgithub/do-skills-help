import unittest

from duration import parse_duration


class ParseDurationTest(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration(" 2d 4h "), 187200)
        self.assertEqual(parse_duration("1.5h"), 5400)
        self.assertEqual(parse_duration("1w2d3h4m5s"), 788645)
        self.assertEqual(parse_duration("1:02:03"), 3723)
        self.assertEqual(parse_duration("-45s"), -45)
        self.assertEqual(parse_duration("0"), 0)

    def test_valid_edges(self):
        self.assertEqual(parse_duration("1.5m"), 90)
        self.assertEqual(parse_duration("0.1h"), 360)
        self.assertEqual(parse_duration("05m"), 300)
        self.assertEqual(parse_duration("1h 30m"), 5400)
        self.assertEqual(parse_duration("1:30"), 90)
        self.assertEqual(parse_duration("90:00"), 5400)
        self.assertEqual(parse_duration("1:00:00"), 3600)
        self.assertEqual(parse_duration("-1:30"), -90)
        self.assertEqual(parse_duration("-1h"), -3600)
        self.assertEqual(parse_duration("-0s"), 0)

    def test_invalid(self):
        for bad in [
            "", "   ", "-", "+1h", ".5h", "5.h", "0.3s", "30m1h", "1h1h",
            "1 h", "1h  30m", "1:60", "1:5", "1.5", "5", "-0", "00", "1:30.5",
            "1H", "1 :30", "- 1h", "1x",
        ]:
            with self.subTest(s=bad):
                with self.assertRaises(ValueError):
                    parse_duration(bad)

    def test_non_str(self):
        with self.assertRaises(TypeError):
            parse_duration(5)


if __name__ == "__main__":
    unittest.main()
