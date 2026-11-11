"""Test the public version range API using only the standard library."""

import unittest

from semver_range import max_satisfying, satisfies


class SemverRangeTests(unittest.TestCase):
    """Exercise range syntax, SemVer ordering, and validation."""

    def test_satisfies_supported_ranges_match_boundaries(self) -> None:
        cases = [
            ("", "0.0.0", "0.0.0-alpha"),
            ("   ", "999.0.0", "1.0.0-alpha"),
            ("1.2.3", "v1.2.3+build", "1.2.4"),
            ("= 1.2.3", " =1.2.3 ", "1.2.2"),
            (">1.2.3", "1.2.4", "1.2.3"),
            (">= 1.2.3", "1.2.3", "1.2.2"),
            ("<1.2.3", "1.2.2", "1.2.3"),
            ("<=1.2.3", "1.2.3", "1.2.4"),
            (">=1.2.3 <2.0.0", "1.9.9", "2.0.0"),
            ("1.2", "1.2.9", "1.3.0"),
            ("1.2.x", "1.2.0", "1.3.0"),
            ("1.2.*", "1.2.99", "1.1.9"),
            ("1", "1.9.9", "2.0.0"),
            ("1.x", "1.2.3", "0.9.9"),
            ("1.x.x", "1.0.0", "2.0.0"),
            ("*", "0.0.0", "0.0.0-rc"),
            ("x", "99.1.2", "1.0.0-rc.1"),
            ("X", "1.0.0", "1.0.0-alpha"),
            (">1.2", "1.3.0", "1.2.99"),
            (">1", "2.0.0", "1.99.99"),
            (">=1.2", "1.2.0", "1.1.99"),
            ("<1.2", "1.1.99", "1.2.0"),
            ("<=1.2", "1.2.99", "1.3.0"),
            ("<=1", "1.99.99", "2.0.0"),
            ("=1.2", "1.2.3", "1.3.0"),
            ("~1.2.3", "1.2.99", "1.3.0"),
            ("~ 1.2", "1.2.0", "1.3.0"),
            ("~1", "1.99.99", "2.0.0"),
            ("~0.2.3", "0.2.9", "0.3.0"),
            ("~1.2.3-beta.2", "1.2.3-beta.3", "1.2.3-beta.1"),
            ("^1.2.3", "1.99.99", "2.0.0"),
            ("^0.2.3", "0.2.99", "0.3.0"),
            ("^0.0.3", "0.0.3", "0.0.4"),
            ("^1.2.3-beta.2", "1.2.3-beta.4", "1.2.4-alpha"),
            ("^1.2", "1.9.0", "2.0.0"),
            ("^1.2.x", "1.9.0", "2.0.0"),
            ("^1", "1.9.0", "2.0.0"),
            ("^1.x", "1.9.0", "2.0.0"),
            ("^0.0", "0.0.99", "0.1.0"),
            ("^0.0.x", "0.0.99", "0.1.0"),
            ("^0.x", "0.99.99", "1.0.0"),
            ("^0", "0.99.99", "1.0.0"),
            ("^0.1", "0.1.99", "0.2.0"),
            ("1.2.3 - 2.3.4", "2.3.4", "2.3.5"),
            ("1.2 - 2.3.4", "1.2.0", "1.1.99"),
            ("1.2.3 - 2.3", "2.3.99", "2.4.0"),
            ("1.2.3 - 2", "2.99.99", "3.0.0"),
            ("1.x || >=3.0.0", "3.0.0", "2.0.0"),
            ("1.x ||", "2.0.0", "2.0.0-alpha"),
        ]
        for range_, included, excluded in cases:
            with self.subTest(range_=range_):
                self.assertTrue(satisfies(included, range_))
                self.assertFalse(satisfies(excluded, range_))

    def test_satisfies_prerelease_requires_explicit_same_core(self) -> None:
        cases = [
            ("1.2.4-alpha", "^1.2.3", False),
            ("1.2.3-beta.4", "^1.2.3-beta.2", True),
            ("1.2.3-beta.4", ">=1.2.3-beta.2 <1.2.3", True),
            ("1.2.4-beta", ">=1.2.3-beta.2 <2.0.0", False),
            ("1.3.0-alpha", "1.2 >=1.3.0-0", False),
            ("1.2.0-alpha", "<1.2 >=1.2.0-0", False),
            ("1.2.3-rc", "1.0.0 - 1.2.3-rc", True),
            ("1.2.3-beta", "1.2.3-alpha - 2", True),
            ("1.0.0-beta", ">=1.0.0-alpha <1.0.0 || 2", True),
            ("1.0.0-beta", ">=1.0.0-alpha <1.0.0-alpha || *", False),
        ]
        for version, range_, expected in cases:
            with self.subTest(version=version, range_=range_):
                self.assertEqual(satisfies(version, range_), expected)

    def test_satisfies_desugared_ranges_match_release_grid(self) -> None:
        equivalents = [
            ("1.2", ">=1.2.0 <1.3.0-0"),
            ("1", ">=1.0.0 <2.0.0-0"),
            (">1.2", ">=1.3.0"),
            (">1", ">=2.0.0"),
            (">=1.2", ">=1.2.0"),
            ("<1.2", "<1.2.0-0"),
            ("<=1.2", "<1.3.0-0"),
            ("<=1", "<2.0.0-0"),
            ("~1.2.3", ">=1.2.3 <1.3.0-0"),
            ("~1", ">=1.0.0 <2.0.0-0"),
            ("^1.2.3", ">=1.2.3 <2.0.0-0"),
            ("^0.2.3", ">=0.2.3 <0.3.0-0"),
            ("^0.0.3", ">=0.0.3 <0.0.4-0"),
            ("^0.0", ">=0.0.0 <0.1.0-0"),
            ("^0", ">=0.0.0 <1.0.0-0"),
            ("1.2.3 - 2.3", ">=1.2.3 <2.4.0-0"),
        ]
        for short, expanded in equivalents:
            for major in range(4):
                for minor in range(5):
                    for patch in range(5):
                        version = f"{major}.{minor}.{patch}"
                        with self.subTest(range_=short, version=version):
                            self.assertEqual(satisfies(version, short), satisfies(version, expanded))

    def test_satisfies_wildcard_operators_follow_spec(self) -> None:
        for wildcard in ("*", "x", "X", "x.x", "*.*.*"):
            for operator in ("", "=", ">=", "<=", "~", "^"):
                with self.subTest(operator=operator, wildcard=wildcard):
                    self.assertTrue(satisfies("0.0.0", operator + wildcard))
                    self.assertTrue(satisfies("999.0.0", operator + wildcard))
            for operator in ("<", ">"):
                self.assertFalse(satisfies("0.0.0", operator + wildcard))
                self.assertFalse(satisfies("0.0.0-alpha", operator + wildcard + " >=0.0.0-0"))

    def test_satisfies_invalid_versions_raise(self) -> None:
        invalid = ["", "1", "1.2", "01.2.3", "1.02.3", "1.2.03", "1.2.3.4",
                   "1.2.3-01", "1.2.3-a.01", "1.2.3-", "1.2.3+", "1.2.3-a..b",
                   "1.2.3+a..b", "1.2.3-a_b", "1.2.3+ä", "vv1.2.3", "=v1.2.3",
                   "1.2.3 trailing", "-1.2.3", "١.2.3"]
        for version in invalid:
            with self.subTest(version=version), self.assertRaises(ValueError):
                satisfies(version, "*")

    def test_satisfies_invalid_ranges_raise_even_in_unused_branches(self) -> None:
        invalid = ["~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=a.b.c", "1.2-beta",
                   "1.2+build", "1.*.2", "x.1", "1.2.3, <2", "1.2.3 | 2.0.0",
                   "1.2.3 || invalid", "> =1.2.3", "==1.2.3", "1.2.3 - >2.0.0",
                   "1.2.3 -", ">", "1.2.3-01", "1.2.*-beta", "1.2.*+build"]
        for range_ in invalid:
            with self.subTest(range_=range_):
                with self.assertRaises(ValueError):
                    satisfies("1.2.3", range_)
                with self.assertRaises(ValueError):
                    max_satisfying([], range_)

    def test_max_satisfying_semver_order_ignores_build_and_retains_first(self) -> None:
        ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
                   "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
        for index, expected in enumerate(ordered):
            candidates = list(reversed(ordered[:index + 1]))

            self.assertEqual(max_satisfying(candidates, ">=1.0.0-0"), expected)
        self.assertEqual(max_satisfying(["v1.2.3+first", "1.2.3+second"], "*"), "v1.2.3+first")
        self.assertEqual(max_satisfying(["1.9.9", "1.10.0", "1.2.30"], "*"), "1.10.0")
        self.assertTrue(satisfies("1.2.3+001", "1.2.3+002"))

    def test_max_satisfying_invalid_entries_and_no_matches_return_expected(self) -> None:
        self.assertEqual(max_satisfying([None, 42, "bad", "1.02.3", " 1.2.3 "], "*"), " 1.2.3 ")
        self.assertIsNone(max_satisfying([], "*"))
        self.assertIsNone(max_satisfying(["1.2.3", "bad"], "2"))


if __name__ == "__main__":
    unittest.main()
