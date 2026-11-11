import unittest

from semver_range import max_satisfying, satisfies


class RangeTests(unittest.TestCase):
    def test_expansions(self):
        equivalents = {
            "1.2": ">=1.2.0 <1.3.0-0",
            "1.2.x": ">=1.2.0 <1.3.0-0",
            "1.2.*": ">=1.2.0 <1.3.0-0",
            "1": ">=1.0.0 <2.0.0-0",
            "1.x": ">=1.0.0 <2.0.0-0",
            "1.x.x": ">=1.0.0 <2.0.0-0",
            "*": ">=0.0.0", "x": ">=0.0.0", "X": ">=0.0.0",
            ">1.2": ">=1.3.0", ">1": ">=2.0.0",
            ">=1.2": ">=1.2.0", "<1.2": "<1.2.0-0",
            "<=1.2": "<1.3.0-0", "<=1": "<2.0.0-0",
            "=1.2": ">=1.2.0 <1.3.0-0",
            ">=*": ">=0.0.0", "<=*": ">=0.0.0",
            "~1.2.3": ">=1.2.3 <1.3.0-0",
            "~1.2": ">=1.2.0 <1.3.0-0",
            "~1": ">=1.0.0 <2.0.0-0",
            "~0.2.3": ">=0.2.3 <0.3.0-0",
            "~1.2.3-beta.2": ">=1.2.3-beta.2 <1.3.0-0",
            "^1.2.3": ">=1.2.3 <2.0.0-0",
            "^0.2.3": ">=0.2.3 <0.3.0-0",
            "^0.0.3": ">=0.0.3 <0.0.4-0",
            "^1.2.3-beta.2": ">=1.2.3-beta.2 <2.0.0-0",
            "^1.2": ">=1.2.0 <2.0.0-0",
            "^1.2.x": ">=1.2.0 <2.0.0-0",
            "^1": ">=1.0.0 <2.0.0-0",
            "^1.x": ">=1.0.0 <2.0.0-0",
            "^0.0": ">=0.0.0 <0.1.0-0",
            "^0.0.x": ">=0.0.0 <0.1.0-0",
            "^0.x": ">=0.0.0 <1.0.0-0",
            "^0": ">=0.0.0 <1.0.0-0",
            "^0.1": ">=0.1.0 <0.2.0-0",
            "1.2.3 - 2.3.4": ">=1.2.3 <=2.3.4",
            "1.2 - 2.3.4": ">=1.2.0 <=2.3.4",
            "1.2.3 - 2.3": ">=1.2.3 <2.4.0-0",
            "1.2.3 - 2": ">=1.2.3 <3.0.0-0",
        }
        versions = [
            "{}.{}.{}{}".format(major, minor, patch, suffix)
            for major in range(4) for minor in range(5) for patch in range(6)
            for suffix in ("", "-0", "-alpha", "-beta.2", "-beta.4")
        ]
        for short, expanded in equivalents.items():
            for version in versions:
                with self.subTest(range=short, version=version):
                    self.assertEqual(satisfies(version, short),
                                     satisfies(version, expanded))

    def test_prerelease_ordering(self):
        versions = ["1.0.0-" + suffix for suffix in (
            "alpha", "alpha.1", "alpha.beta", "beta", "beta.2",
            "beta.11", "rc.1")]
        versions.append("1.0.0")
        for index, version in enumerate(versions):
            self.assertEqual(max_satisfying(versions[:index + 1], ">=1.0.0-alpha"),
                             version)
        self.assertTrue(satisfies("1.0.0-9", "<1.0.0-A >=1.0.0-0"))
        self.assertTrue(satisfies("1.0.0-Z", "<1.0.0-a >=1.0.0-0"))

    def test_prerelease_eligibility(self):
        for range_ in ("", "*", "^1.2.3", ">=1.0.0", "<2.0.0"):
            self.assertFalse(satisfies("1.2.4-alpha", range_))
        self.assertTrue(satisfies("1.2.3-beta.4", "^1.2.3-beta.2"))
        self.assertFalse(satisfies("1.2.4-beta.4", "^1.2.3-beta.2"))
        self.assertFalse(satisfies("2.0.0-0", "^1.2.3 || >=3.0.0-beta"))
        self.assertTrue(satisfies("2.0.0-beta", "1.0.0 - 2.0.0-rc"))
        self.assertFalse(satisfies("1.0.0-rc.1", "*"))
        self.assertFalse(satisfies("1.2.3-beta", ">=1.2.3-beta.2"))

    def test_sets_operators_and_prefixes(self):
        self.assertTrue(satisfies(" v1.2.3+001 ", " >= 1.0.0\t< 2.0.0 "))
        self.assertTrue(satisfies("=1.2.3", "= v1.2.3+other"))
        self.assertTrue(satisfies("3.0.0", "1.0.0 || 3.x"))
        self.assertFalse(satisfies("2.0.0", "1.0.0 || 3.x"))
        self.assertFalse(satisfies("1.0.0", ">2.0.0 <1.0.0"))
        for range_ in ("", "  ", "1.0.0 ||", "|| 1.0.0"):
            self.assertTrue(satisfies("9.0.0", range_))
        for range_ in (">*", "<*", ">x", "<X"):
            self.assertFalse(satisfies("0.0.0", range_))
            self.assertFalse(satisfies("9.0.0", range_))

    def test_invalid_versions(self):
        for version in ("", "1", "1.2", "01.2.3", "1.02.3", "1.2.03",
                        "1.2.3-01", "1.2.3-a.01", "1.2.3-", "1.2.3+",
                        "1.2.3-a..b", "1.2.3+a..b", "1.2.3+é", "vv1.2.3",
                        "==1.2.3", "v=1.2.3", "1.2.3.4", None, 123):
            with self.subTest(version=version), self.assertRaises(ValueError):
                satisfies(version, "*")

    def test_invalid_ranges(self):
        for range_ in ("~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=a.b.c",
                       ">=", "==1.2.3", "1.2-beta", "1+build", "1.x-beta",
                       "1.x.3", "01.2", "1.2.3-01", "1.2.3, <2.0.0",
                       "1.0.0 | 2.0.0", "1 - 2 - 3", "1 - >=2", None):
            with self.subTest(range=range_):
                with self.assertRaises(ValueError):
                    satisfies("1.2.3", range_)
                with self.assertRaises(ValueError):
                    max_satisfying([], range_)

    def test_maximum_preserves_input_and_ties(self):
        self.assertEqual(max_satisfying(
            ["garbage", None, "1.9.9", " v2.0.0+first ", "2.0.0+second"], "*"),
            " v2.0.0+first ")
        self.assertEqual(max_satisfying(["2.0.0", "10.0.0", "3.0.0"], "*"),
                         "10.0.0")
        self.assertIsNone(max_satisfying(["bad", "1.0.0-rc.1"], "*"))
        self.assertIsNone(max_satisfying([], "*"))


if __name__ == "__main__":
    unittest.main()
