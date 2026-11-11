import unittest

from semver_range import max_satisfying, satisfies


class SemverRangeTests(unittest.TestCase):
    def test_order_and_build_ties(self):
        ordered = [
            "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta",
            "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
            "1.0.0-rc.1", "1.0.0",
        ]
        for low, high in zip(ordered, ordered[1:]):
            self.assertTrue(satisfies(low, "<" + high + " >=1.0.0-alpha"))
            self.assertFalse(satisfies(high, "<=" + low))
        self.assertEqual(max_satisfying(
            ["invalid", None, " v1.2.3+first ", "1.2.3+second", "1.2.2"], "*"
        ), " v1.2.3+first ")
        self.assertTrue(satisfies("=1.2.3+001", "v1.2.3+other"))

    def test_range_boundaries(self):
        # Each tuple supplies an included lower bound and an excluded upper bound.
        cases = [
            ("1.2", "1.2.0", "1.3.0"),
            ("1.2.x", "1.2.0", "1.3.0"),
            ("1.2.*", "1.2.0", "1.3.0"),
            ("1", "1.0.0", "2.0.0"),
            ("1.x.x", "1.0.0", "2.0.0"),
            ("=1.2", "1.2.0", "1.3.0"),
            ("~1.2.3", "1.2.3", "1.3.0"),
            ("~1.2", "1.2.0", "1.3.0"),
            ("~1", "1.0.0", "2.0.0"),
            ("~0.2.3", "0.2.3", "0.3.0"),
            ("^1.2.3", "1.2.3", "2.0.0"),
            ("^0.2.3", "0.2.3", "0.3.0"),
            ("^0.0.3", "0.0.3", "0.0.4"),
            ("^1.2.x", "1.2.0", "2.0.0"),
            ("^1.x", "1.0.0", "2.0.0"),
            ("^0.0", "0.0.0", "0.1.0"),
            ("^0.0.x", "0.0.0", "0.1.0"),
            ("^0", "0.0.0", "1.0.0"),
            ("^0.x", "0.0.0", "1.0.0"),
            ("^0.1", "0.1.0", "0.2.0"),
            ("1.2.3 - 2.3", "1.2.3", "2.4.0"),
            ("1.2.3 - 2", "1.2.3", "3.0.0"),
        ]
        for range_, lower, upper in cases:
            with self.subTest(range_=range_):
                self.assertTrue(satisfies(lower, range_))
                self.assertFalse(satisfies(upper, range_))
                self.assertFalse(satisfies(upper + "-alpha", range_ + " >=" + upper + "-0"))

    def test_comparators_and_combinations(self):
        cases = [
            ("1.3.0", ">1.2", True), ("1.2.9", ">1.2", False),
            ("2.0.0", ">1", True), ("1.2.0", ">= 1.2", True),
            ("1.2.0", "<1.2", False), ("1.1.9", "<1.2", True),
            ("1.2.9", "<=1.2", True), ("1.3.0", "<=1.2", False),
            ("1.9.9", "<=1", True), ("2.0.0", "<=1", False),
            ("2.3.4", "1.2 - 2.3.4", True),
            ("1.2.0", "1.2 - 2.3.4", True),
            ("2.3.5", "1.2.3 - 2.3.4", False),
            ("3.0.0", ">=1.0.0 <2.0.0 || >=3.0.0 <4.0.0", True),
            ("2.5.0", ">=1.0.0 <2.0.0 || >=3.0.0 <4.0.0", False),
        ]
        for version, range_, expected in cases:
            with self.subTest(version=version, range_=range_):
                self.assertEqual(satisfies(version, range_), expected)
        for range_ in ("", "  ", "*", "x", "X", ">=*", "<=*", "~*", "^*"):
            self.assertTrue(satisfies("0.0.0", range_))
            self.assertTrue(satisfies("123.4.5", range_))
            self.assertFalse(satisfies("1.0.0-rc.1", range_))
        for range_ in (">*", "<*"):
            self.assertIsNone(max_satisfying(["0.0.0", "999.0.0", "0.0.0-0"], range_))

    def test_prerelease_rule_is_per_set_and_uses_written_endpoints(self):
        cases = [
            ("1.2.4-alpha", "^1.2.3", False),
            ("1.2.3-beta.4", "^1.2.3-beta.2", True),
            ("1.2.3-beta.4", "~1.2.3-beta.2", True),
            ("1.2.3-beta.1", "^1.2.3-beta.2", False),
            ("1.3.0-0", "~1.2.3", False),
            ("1.2.3-alpha", "<1.2.3 || >9.0.0-alpha", False),
            ("1.2.3-beta", "1.0.0 - 1.2.3-rc.1", True),
            ("1.2.3-beta", "1.0.0 - 1.2.3", False),
            ("1.2.3-beta", ">=1.2.3-alpha <1.2.3", True),
        ]
        for version, range_, expected in cases:
            with self.subTest(version=version, range_=range_):
                self.assertEqual(satisfies(version, range_), expected)

    def test_invalid_inputs(self):
        bad_versions = [
            "", "1", "1.2", "01.2.3", "1.02.3", "1.2.03", "1.2.3-01",
            "1.2.3-a..b", "1.2.3+", "1.2.3-a_", "vv1.2.3", "=v1.2.3",
            "1.2.3.4", "1.2.3\nextra", "١.2.3", None,
        ]
        for version in bad_versions:
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    satisfies(version, "*")
                self.assertIsNone(max_satisfying([version], "*"))
        bad_ranges = [
            "~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=a.b.c", "1.x.3",
            "1.2-beta", "1+build", "1.2.x+build", "1.2.3-01", "==1.2.3",
            "> =1.2.3", "1.2.3 | 2.0.0", "1.2.3,2.0.0", "vv1.2.3", None,
            "* || >=bad", ">=1.2.3 - 2.0.0",
        ]
        for range_ in bad_ranges:
            with self.subTest(range_=range_):
                with self.assertRaises(ValueError):
                    satisfies("1.2.3", range_)
                with self.assertRaises(ValueError):
                    max_satisfying([], range_)


if __name__ == "__main__":
    unittest.main()
