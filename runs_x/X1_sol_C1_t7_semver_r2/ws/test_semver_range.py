import unittest

from semver_range import max_satisfying, satisfies


class RangeTests(unittest.TestCase):
    def test_spec_expansions(self):
        examples = {
            "1.2": ">=1.2.0 <1.3.0-0",
            "1.2.x": ">=1.2.0 <1.3.0-0",
            "1.2.*": ">=1.2.0 <1.3.0-0",
            "1": ">=1.0.0 <2.0.0-0",
            "1.x": ">=1.0.0 <2.0.0-0",
            "1.x.x": ">=1.0.0 <2.0.0-0",
            "*": ">=0.0.0",
            "x": ">=0.0.0",
            "X": ">=0.0.0",
            ">1.2": ">=1.3.0",
            ">1": ">=2.0.0",
            ">=1.2": ">=1.2.0",
            "<1.2": "<1.2.0-0",
            "<=1.2": "<1.3.0-0",
            "<=1": "<2.0.0-0",
            "=1.2": "1.2",
            ">=*": ">=0.0.0",
            "<=*": ">=0.0.0",
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
            ">= 1.2.3": ">=1.2.3",
            "v1.2.3": "1.2.3",
            "=1.2.3": "1.2.3",
        }
        candidates = [
            "{}.{}.{}{}".format(major, minor, patch, suffix)
            for major in range(4)
            for minor in range(5)
            for patch in (0, 1, 2, 3, 4, 5, 10)
            for suffix in ("", "-0", "-alpha", "-beta.2", "-beta.4", "+build.01")
        ]
        for source, expansion in examples.items():
            for version in candidates:
                self.assertEqual(
                    satisfies(version, source), satisfies(version, expansion),
                    (version, source, expansion),
                )
        for source in (">*", "<*"):
            for version in candidates:
                self.assertFalse(satisfies(version, source))

    def test_semver_ordering(self):
        ordered = [
            "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta",
            "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
            "1.0.0-rc.1", "1.0.0",
        ]
        for i, left in enumerate(ordered):
            for j, right in enumerate(ordered):
                self.assertEqual(satisfies(left, "<=" + right + " >=1.0.0-0"), i <= j)
                self.assertEqual(satisfies(left, ">" + right + " >=1.0.0-0"), i > j)
        self.assertTrue(satisfies("10.0.0", ">2.99.99"))
        self.assertTrue(satisfies("1.0.0-Z", "<1.0.0-a"))
        self.assertTrue(satisfies("1.0.0-999", "<1.0.0-A"))

    def test_prerelease_rule(self):
        self.assertFalse(satisfies("1.2.4-alpha", "^1.2.3"))
        self.assertTrue(satisfies("1.2.3-beta.4", "^1.2.3-beta.2"))
        self.assertFalse(satisfies("1.0.0-rc.1", "*"))
        self.assertFalse(satisfies("1.3.0-alpha", "~1.2.3"))
        self.assertFalse(satisfies("1.2.4-alpha", ">=1.2.3-beta.2 <2"))
        self.assertFalse(satisfies("1.2.3-alpha", ">=1.2.3-beta || *"))
        self.assertTrue(satisfies("1.2.3-alpha", ">=1.2.3-0 <1.2.3"))
        self.assertTrue(satisfies("2.3.4-alpha", "1.2.3 - 2.3.4-beta"))
        self.assertFalse(satisfies("2.3.4-rc", "1.2.3 - 2.3.4-beta"))
        for source in (">* >=0.0.0-0", "<* >=0.0.0-alpha"):
            self.assertFalse(satisfies("0.0.0-alpha", source))

    def test_versions_and_builds(self):
        for version in ("1.2.3", "v1.2.3", "=1.2.3", " \t1.2.3\n",
                        "1.2.3+001", "1.2.3+a-b.2"):
            self.assertTrue(satisfies(version, "1.2.3"))
        self.assertTrue(satisfies("1.2.3-alpha.0+01", "1.2.3-alpha.0+02"))
        for version in (
            "01.2.3", "1.02.3", "1.2.03", "1.2", "1.2.3.4", "1.2.3-",
            "1.2.3+", "1.2.3-a..b", "1.2.3+a..b", "1.2.3-01",
            "1.2.3-a.01", "1.2.3_a", "1.2.3-ä", "1.2.3+ä", "1.2.3 a",
            "vv1.2.3", "==1.2.3", "v=1.2.3", "v 1.2.3", "V1.2.3",
            "-1.2.3", "１.2.3", "", None, 123,
        ):
            with self.subTest(version=version), self.assertRaises(ValueError):
                satisfies(version, "*")

    def test_sets_and_comparators(self):
        for source in ("", " \t\n", "||", "1 ||", "|| 2"):
            self.assertTrue(satisfies("9.8.7", source))
            self.assertFalse(satisfies("9.8.7-alpha", source))
        self.assertTrue(satisfies("2.3.4", ">=2 <3 || >=4"))
        self.assertFalse(satisfies("3.0.0", ">=2 <3 || >=4"))
        for operator, yes, no in (
            ("<", "1.2.2", "1.2.3"), ("<=", "1.2.3", "1.2.4"),
            (">", "1.2.4", "1.2.3"), (">=", "1.2.3", "1.2.2"),
            ("=", "1.2.3", "1.2.4"), ("", "1.2.3", "1.2.4"),
        ):
            for space in ("", " "):
                self.assertTrue(satisfies(yes, operator + space + "1.2.3"))
                self.assertFalse(satisfies(no, operator + space + "1.2.3"))
        self.assertTrue(satisfies("2.0.0", "1.2 - 3 >=2 <3"))
        self.assertFalse(satisfies("1.5.0", "1.2 - 3 >=2 <3"))

    def test_invalid_ranges(self):
        for source in (
            "~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=a.b.c",
            "~", ">=", "1.2-beta", "1+build", "1.2.x+build",
            "1.x.2", "x.1", "1..2", "01.2", "1.02", "1.2.03",
            "1.2.3-01", "1.2.3+", "1.2.3-a..b", "1.2.3+_",
            "==1.2.3", ">=<=1.2.3", "1,2", "1 | 2", "1 ||| 2",
            "1.2.3 - >=2.3.4", "1.2.3 - -", "1.2.3 -2.3.4",
            "1.2.3- 2.3.4", "1.2.3 2.3.4 garbage", None, 123,
        ):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    satisfies("1.2.3", source)
                with self.assertRaises(ValueError):
                    max_satisfying([], source)
        with self.assertRaises(ValueError):
            satisfies("1.2.3", "* || garbage")

    def test_max_satisfying(self):
        self.assertIsNone(max_satisfying([], "*"))
        self.assertIsNone(max_satisfying(["bad", "2.0.0"], "1"))
        self.assertEqual(max_satisfying(
            [None, "invalid", "1.2.3", "1.10.0", "1.9.9", "2.0.0"], "1"
        ), "1.10.0")
        self.assertEqual(max_satisfying(
            [" v1.2.3+first ", "1.2.3+second", "=1.2.3"], "*"
        ), " v1.2.3+first ")
        self.assertEqual(max_satisfying(
            ["1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-alpha"], ">=1.0.0-0"
        ), "1.0.0-beta.11")


if __name__ == "__main__":
    unittest.main()
