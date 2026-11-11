"""Test version validation, range expansion, and precedence."""

import unittest

from semver_range import max_satisfying, satisfies


class SemverRangeTests(unittest.TestCase):
    """Exercise the public API against the range specification."""

    def test_range_expansions_match_explicit_bounds(self) -> None:
        expansions = {
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
            "=1.2": ">=1.2.0 <1.3.0-0",
            ">=*": ">=0.0.0",
            "<=*": ">=0.0.0",
            ">*": "<0.0.0",
            "<*": "<0.0.0",
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
            "0.0.0", "0.0.3", "0.0.4", "0.1.0", "0.2.3", "0.3.0", "1.0.0",
            "1.2.0", "1.2.3", "1.2.4", "1.3.0", "1.9.9", "2.0.0", "2.3.4",
            "2.3.5", "2.4.0", "3.0.0", "1.2.3-beta.1", "1.2.3-beta.2",
            "1.2.3-beta.4", "1.2.4-alpha", "1.3.0-0", "2.0.0-alpha",
        ]
        for shorthand, explicit in expansions.items():
            for version in versions:
                with self.subTest(range=shorthand, version=version):
                    self.assertEqual(satisfies(version, shorthand), satisfies(version, explicit))

    def test_prerelease_requires_explicit_same_core_in_matching_set(self) -> None:
        cases = [
            ("1.2.4-alpha", "^1.2.3", False),
            ("1.2.3-beta.4", "^1.2.3-beta.2", True),
            ("1.0.0-rc.1", "*", False),
            ("1.3.0-alpha", "~1.2.3 >=1.3.0-alpha", False),
            ("1.2.3-beta.4", ">=1.2.3-beta.2 <1.2.3", True),
            ("1.2.4-alpha", ">=1.2.3-alpha <2.0.0", False),
            ("1.2.3-beta", ">2.0.0 >=1.2.3-alpha || *", False),
            ("1.2.3-beta", "1.2.3-alpha - 1.2.3", True),
            ("2.3.4-alpha", "1.0.0 - 2.3.4-beta", True),
            ("0.0.0-alpha", "", False),
        ]
        for version, range_, expected in cases:
            with self.subTest(version=version, range=range_):
                self.assertEqual(satisfies(version, range_), expected)

    def test_comparator_sets_and_prefixes(self) -> None:
        cases = [
            (" v1.2.3+build.01 ", "= 1.2.3", True),
            ("=1.2.3", "v1.2.3+other", True),
            ("1.2.3", ">= 1.0.0 < 2.0.0", True),
            ("3.0.0", "1.x || >= 3.0.0", True),
            ("2.0.0", "1.x || >= 3.0.0", False),
            ("9.0.0", "  \t\n", True),
            ("9.0.0", "1.x ||", True),
            ("1.2.3", ">1.2.3", False),
            ("1.2.3", "<=1.2.3", True),
            ("1.2.3", "<1.2.3", False),
        ]
        for version, range_, expected in cases:
            with self.subTest(version=version, range=range_):
                self.assertEqual(satisfies(version, range_), expected)

    def test_invalid_versions_raise(self) -> None:
        invalid = [
            "", "1", "1.2", "01.2.3", "1.02.3", "1.2.03", "1.2.3.4",
            "1.2.3-01", "1.2.3-alpha..1", "1.2.3-", "1.2.3+", "1.2.3+a..b",
            "vv1.2.3", "==1.2.3", "v=1.2.3", "v 1.2.3", "1.2.3-β", "١.2.3",
        ]
        for version in invalid:
            with self.subTest(version=version), self.assertRaises(ValueError):
                satisfies(version, "*")

    def test_invalid_ranges_raise_even_when_another_branch_matches(self) -> None:
        invalid = [
            "~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=a.b.c", "1.2-beta",
            "1.2+build", "1.x.2", "x.1", "1..2", "01.2.3", "1.2.3-01",
            "1.2.3 | 2.0.0", ">=", "1.2.3, <2", "1.2.3 - >=2.0.0", "==1.2.3",
            "^^1.2.3", "vv1.2.3", "1.2.3 - 2.0.0 - 3.0.0",
        ]
        for range_ in invalid:
            with self.subTest(range=range_):
                with self.assertRaises(ValueError):
                    satisfies("1.2.3", "* || " + range_)
                with self.assertRaises(ValueError):
                    max_satisfying([], range_)

    def test_semver_precedence_orders_identifiers(self) -> None:
        ordered = [
            "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
            "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0",
            "1.0.1", "1.1.0", "2.0.0", "10.0.0",
        ]
        for index, version in enumerate(ordered):
            with self.subTest(version=version):
                self.assertEqual(max_satisfying(ordered[:index + 1], ">=1.0.0-alpha"), version)
        self.assertTrue(satisfies("1.0.0-2", "<1.0.0-a >=1.0.0-0"))
        self.assertTrue(satisfies("1.0.0-A", "<1.0.0-a >=1.0.0-0"))
        self.assertTrue(satisfies("1.0.0-1a", ">1.0.0-100 >=1.0.0-0"))

    def test_max_satisfying_preserves_first_equal_string_and_skips_invalid(self) -> None:
        versions: list[object] = [None, 123, "invalid", "1.2.3+first", "v1.2.3+second", "2.0.0"]
        self.assertEqual(max_satisfying(versions, "1.x"), "1.2.3+first")
        self.assertEqual(max_satisfying([" =1.2.3 "], "*"), " =1.2.3 ")
        self.assertIsNone(max_satisfying(versions, "3.x"))
        self.assertIsNone(max_satisfying([], "*"))


if __name__ == "__main__":
    unittest.main()
