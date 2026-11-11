import unittest

from semver_range import max_satisfying, satisfies


class RangeTests(unittest.TestCase):
    def test_expansions(self):
        cases = {
            "1.2": ("1.2.0", "1.2.99", "1.3.0"),
            "1.2.x": ("1.2.0", "1.2.99", "1.3.0"),
            "1": ("1.0.0", "1.99.99", "2.0.0"),
            ">1.2": ("1.3.0", "2.0.0", "1.2.99"),
            ">1": ("2.0.0", "3.0.0", "1.99.99"),
            ">=1.2": ("1.2.0", "2.0.0", "1.1.99"),
            "<1.2": ("0.0.0", "1.1.99", "1.2.0"),
            "<=1.2": ("0.0.0", "1.2.99", "1.3.0"),
            "<=1": ("0.0.0", "1.99.99", "2.0.0"),
            "~1.2.3": ("1.2.3", "1.2.99", "1.3.0"),
            "~1.2": ("1.2.0", "1.2.99", "1.3.0"),
            "~1": ("1.0.0", "1.99.99", "2.0.0"),
            "~0.2.3": ("0.2.3", "0.2.99", "0.3.0"),
            "^1.2.3": ("1.2.3", "1.99.99", "2.0.0"),
            "^0.2.3": ("0.2.3", "0.2.99", "0.3.0"),
            "^0.0.3": ("0.0.3", "0.0.3+build", "0.0.4"),
            "^1.2.x": ("1.2.0", "1.99.99", "2.0.0"),
            "^1.x": ("1.0.0", "1.99.99", "2.0.0"),
            "^0.0": ("0.0.0", "0.0.99", "0.1.0"),
            "^0.0.x": ("0.0.0", "0.0.99", "0.1.0"),
            "^0.x": ("0.0.0", "0.99.99", "1.0.0"),
            "^0": ("0.0.0", "0.99.99", "1.0.0"),
            "^0.1": ("0.1.0", "0.1.99", "0.2.0"),
            "1.2.3 - 2.3.4": ("1.2.3", "2.3.4", "2.3.5"),
            "1.2 - 2.3.4": ("1.2.0", "2.3.4", "1.1.99"),
            "1.2.3 - 2.3": ("1.2.3", "2.3.99", "2.4.0"),
            "1.2.3 - 2": ("1.2.3", "2.99.99", "3.0.0"),
        }
        for range_, (low, high, outside) in cases.items():
            with self.subTest(range=range_):
                self.assertTrue(satisfies(low, range_))
                self.assertTrue(satisfies(high, range_))
                self.assertFalse(satisfies(outside, range_))

    def test_prerelease_rule_and_generated_bounds(self):
        self.assertFalse(satisfies("1.2.4-alpha", "^1.2.3"))
        self.assertTrue(satisfies("1.2.3-beta.4", "^1.2.3-beta.2"))
        self.assertTrue(satisfies("1.2.3-beta.4", "~1.2.3-beta.2"))
        self.assertFalse(satisfies("1.3.0-alpha", "~1.2 >=1.3.0-alpha"))
        self.assertFalse(satisfies("1.0.0-rc.1", "*"))
        self.assertFalse(satisfies("1.0.0-rc.1", ""))
        self.assertFalse(satisfies("1.0.0-rc.1", ">=1.0.0-rc.0 <1 || >=2"))
        self.assertTrue(satisfies("1.0.0-rc.1", "1.0.0-rc.0 - 1.0.0"))

    def test_ordering(self):
        versions = ["1.0.0-" + p for p in
                    ("alpha", "alpha.1", "alpha.beta", "beta", "beta.2",
                     "beta.11", "rc.1")] + ["1.0.0"]
        for i, left in enumerate(versions):
            for j, right in enumerate(versions):
                with self.subTest(left=left, right=right):
                    # The explicit comparator admits the prerelease core.
                    self.assertEqual(satisfies(left, ">" + right), i > j)
        self.assertTrue(satisfies("1.0.0-A", "<1.0.0-a"))
        self.assertTrue(satisfies("1.0.0-99", "<1.0.0-a"))

    def test_sets_and_spacing(self):
        self.assertTrue(satisfies(" v1.2.3+abc.01 ", ">= 1.2.3 < 2"))
        self.assertTrue(satisfies("=1.2.3", "= 1.2.3"))
        self.assertTrue(satisfies("3.1.0", "1.x || >=3 <4"))
        self.assertFalse(satisfies("2.1.0", "1.x || >=3 <4"))
        for range_ in ("", "   ", "*", "x", "X", ">=*", "<=*", "||"):
            self.assertTrue(satisfies("0.0.0", range_))
        for range_ in (">*", "<*"):
            self.assertFalse(satisfies("0.0.0", range_))

    def test_invalid(self):
        invalid_versions = ["1", "1.2", "01.2.3", "1.02.3", "1.2.03",
                            "1.2.3-01", "1.2.3-a..b", "1.2.3+", "1.2.3-",
                            "vv1.2.3", "=v1.2.3", "1.2.3.4", "1.2.3+ä", None]
        for version in invalid_versions:
            with self.subTest(version=version), self.assertRaises(ValueError):
                satisfies(version, "*")
        invalid_ranges = ["~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=a.b.c",
                          "1.2-beta", "1.2+build", "1.x.2", "1.2.3 <",
                          "1.2.3, <2", "1.2.3|2", "1.2.3<2", "==1.2.3",
                          ">= <1.2.3", "1.2.3 || bad", None]
        for range_ in invalid_ranges:
            with self.subTest(range=range_), self.assertRaises(ValueError):
                satisfies("1.2.3", range_)
            with self.subTest(range=range_), self.assertRaises(ValueError):
                max_satisfying([], range_)

    def test_maximum(self):
        self.assertEqual(max_satisfying(["bad", None, "1.2.3", "v1.9.0+first",
                                        "1.9.0+second", "2.0.0"], "1.x"),
                         "v1.9.0+first")
        self.assertIsNone(max_satisfying(["bad", "1.0.0"], ">2"))
        self.assertIsNone(max_satisfying([], "*"))
        self.assertEqual(max_satisfying(["1.0.0-beta.2", "1.0.0-beta.11"],
                                        ">=1.0.0-beta.0"), "1.0.0-beta.11")


if __name__ == "__main__":
    unittest.main()
