"""Test the version range contract using only the standard library."""

import unittest

from semver_range import max_satisfying, satisfies


class SemverRangeTests(unittest.TestCase):
    """Exercise version validation, range expansion, and selection."""

    def test_versions_valid_forms_match(self) -> None:
        for version in [
            "0.0.0", "1.2.3", " v1.2.3 ", "=1.2.3", "1.2.3+001.build",
            "1.2.3-alpha-1.0+build.01", "1.2.3--",
        ]:
            with self.subTest(version=version):
                self.assertTrue(satisfies(version, version.strip()))

    def test_versions_invalid_forms_raise(self) -> None:
        for version in [
            "", "1", "1.2", "01.2.3", "1.02.3", "1.2.03", "-1.2.3", "1.2.3.4",
            "vv1.2.3", "==1.2.3", "v=1.2.3", "1.2.3-", "1.2.3+", "1.2.3-a..b",
            "1.2.3+build..x", "1.2.3-01", "1.2.3-a.01", "1.2.3-ä", "１.2.3",
            "1.2.3+a_b", "1.2.3\n4.5.6", None, 123,
        ]:
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    satisfies(version, "*")

    def test_precedence_semver_order_is_respected(self) -> None:
        versions = [
            "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
            "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1",
            "1.1.0", "2.0.0", "10.0.0",
        ]
        for index, version in enumerate(versions):
            for other_index, other in enumerate(versions):
                with self.subTest(version=version, other=other):
                    # The extra comparator opts this core into prerelease matching.
                    range_ = f">{other} >=1.0.0-0"
                    self.assertEqual(satisfies(version, range_), index > other_index)

    def test_exact_comparators_ignore_build_and_respect_operators(self) -> None:
        for operator, expected in [
            ("", True), ("=", True), (">", False), (">=", True),
            ("<", False), ("<=", True),
        ]:
            with self.subTest(operator=operator):
                self.assertEqual(satisfies("1.2.3+first", f"{operator}1.2.3+second"), expected)
        self.assertTrue(satisfies("1.2.3", ">= v1.2.3"))
        self.assertFalse(satisfies("1.2.4", "1.2.3"))
        self.assertTrue(satisfies("1.0.0-Z", "<1.0.0-a"))
        self.assertTrue(satisfies("1.0.0-9", "<1.0.0-A"))

    def test_generated_upper_bounds_exclude_next_core_even_when_opted_in(self) -> None:
        for range_ in ["1.2", "<=1.2", "~1.2.3", "1.0 - 1.2"]:
            with self.subTest(range_=range_):
                self.assertFalse(satisfies("1.3.0-0", f"{range_} >=1.3.0-0"))
                self.assertFalse(satisfies("1.3.0-alpha", f"{range_} >=1.3.0-0"))

    def test_comparators_match_expected_boundaries(self) -> None:
        for range_, lower, upper in [
            ("1.2", "1.2.0", "1.3.0-0"),
            ("1.2.x", "1.2.0", "1.3.0-0"),
            ("1.2.*", "1.2.0", "1.3.0-0"),
            ("1", "1.0.0", "2.0.0-0"),
            ("1.x", "1.0.0", "2.0.0-0"),
            ("1.x.x", "1.0.0", "2.0.0-0"),
            ("=1.2", "1.2.0", "1.3.0-0"),
            ("~1.2.3", "1.2.3", "1.3.0-0"),
            ("~1.2", "1.2.0", "1.3.0-0"),
            ("~1", "1.0.0", "2.0.0-0"),
            ("~0.2.3", "0.2.3", "0.3.0-0"),
            ("~1.2.3-beta.2", "1.2.3-beta.2", "1.3.0-0"),
            ("^1.2.3", "1.2.3", "2.0.0-0"),
            ("^0.2.3", "0.2.3", "0.3.0-0"),
            ("^0.0.3", "0.0.3", "0.0.4-0"),
            ("^1.2.3-beta.2", "1.2.3-beta.2", "2.0.0-0"),
            ("^1.2", "1.2.0", "2.0.0-0"),
            ("^1.2.x", "1.2.0", "2.0.0-0"),
            ("^1", "1.0.0", "2.0.0-0"),
            ("^1.x", "1.0.0", "2.0.0-0"),
            ("^0.0", "0.0.0", "0.1.0-0"),
            ("^0.0.x", "0.0.0", "0.1.0-0"),
            ("^0.x", "0.0.0", "1.0.0-0"),
            ("^0", "0.0.0", "1.0.0-0"),
            ("^0.1", "0.1.0", "0.2.0-0"),
        ]:
            candidates = [
                "0.0.0", "0.0.1", "0.0.3", "0.0.4", "0.1.0", "0.2.3", "0.3.0",
                "1.0.0", "1.2.0", "1.2.3-beta.1", "1.2.3-beta.2", "1.2.3-beta.4",
                "1.2.3", "1.2.9", "1.3.0-alpha", "1.3.0", "2.0.0", "3.0.0",
            ]
            for version in candidates:
                with self.subTest(range_=range_, version=version):
                    self.assertEqual(
                        satisfies(version, range_), satisfies(version, f">={lower} <{upper}")
                    )

    def test_partial_operators_expand_as_specified(self) -> None:
        for range_, expanded in [
            (">1.2", ">=1.3.0"), (">1", ">=2.0.0"), (">=1.2", ">=1.2.0"),
            ("<1.2", "<1.2.0-0"), ("<=1.2", "<1.3.0-0"), ("<=1", "<2.0.0-0"),
            ("*", ">=0.0.0"), ("x", ">=0.0.0"), ("X", ">=0.0.0"),
            (">=*", ">=0.0.0"), ("<=*", ">=0.0.0"),
        ]:
            for version in ["0.0.0", "1.0.0", "1.2.0", "1.2.9", "1.3.0", "2.0.0"]:
                with self.subTest(range_=range_, version=version):
                    self.assertEqual(satisfies(version, range_), satisfies(version, expanded))
        for range_ in [">*", "<*", ">x", "<X"]:
            for version in ["0.0.0", "1.2.3", "999.0.0"]:
                self.assertFalse(satisfies(version, range_))

    def test_hyphens_expand_endpoints(self) -> None:
        for range_, expanded in [
            ("1.2.3 - 2.3.4", ">=1.2.3 <=2.3.4"),
            ("1.2 - 2.3.4", ">=1.2.0 <=2.3.4"),
            ("1.2.3 - 2.3", ">=1.2.3 <2.4.0-0"),
            ("1.2.3 - 2", ">=1.2.3 <3.0.0-0"),
            ("1.2.3-beta - 2.3.4-rc", ">=1.2.3-beta <=2.3.4-rc"),
        ]:
            for version in [
                "1.2.0", "1.2.3-alpha", "1.2.3-beta", "1.2.3", "2.3.4-beta",
                "2.3.4-rc", "2.3.4", "2.3.5", "2.4.0-alpha", "2.9.0", "3.0.0",
            ]:
                with self.subTest(range_=range_, version=version):
                    self.assertEqual(satisfies(version, range_), satisfies(version, expanded))

    def test_sets_and_whitespace_match(self) -> None:
        self.assertTrue(satisfies("1.2.3", ">= 1.0.0\t< 2.0.0 || = 3.0.0"))
        self.assertTrue(satisfies("3.0.0", ">=1 <2 || 3.0.0"))
        self.assertFalse(satisfies("2.5.0", ">=1 <2 || 3.0.0"))
        for range_ in ["", " \t\n", "||", "<0.0.0 ||", " || <0.0.0"]:
            self.assertTrue(satisfies("1.2.3", range_))
            self.assertFalse(satisfies("1.2.3-alpha", range_))

    def test_prereleases_require_explicit_matching_core_in_same_set(self) -> None:
        for range_ in ["*", "^1.2.3", ">=1.0.0 <2.0.0", "<1.2.4-0", ""]:
            self.assertFalse(satisfies("1.2.4-alpha", range_))
        self.assertTrue(satisfies("1.2.3-beta.4", "^1.2.3-beta.2"))
        self.assertFalse(satisfies("1.2.4-beta.4", "^1.2.3-beta.2"))
        self.assertFalse(satisfies("1.2.3-alpha", "<1.2.3-0 || >=1.0.0"))
        self.assertFalse(satisfies("1.2.3-alpha", ">=1.2.3-beta"))
        self.assertTrue(satisfies("1.2.3-alpha", ">=1.2.3-0 <2"))

    def test_ranges_invalid_syntax_raises_even_in_unused_sets(self) -> None:
        for range_ in [
            "~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=a.b.c", "1.x.2", "x.1",
            "1.2-beta", "1.2+build", "1.x-beta", "==1.2.3", ">=", "< >1.2.3",
            "1.2.3 | 2.0.0", "1.2.3, <2", "1.2.3 - >2.0.0", "- 2.0.0",
            "1.2.3-01", "01.2", "* || invalid", "|| ^", None,
        ]:
            with self.subTest(range_=range_):
                with self.assertRaises(ValueError):
                    satisfies("1.2.3", range_)
                with self.assertRaises(ValueError):
                    max_satisfying([], range_)

    def test_max_satisfying_skips_invalid_and_preserves_first_equal_string(self) -> None:
        versions = [None, 42, "invalid", "2.0.0", " v1.9.0+first ", "1.9.0+second"]

        self.assertEqual(max_satisfying(versions, "^1"), " v1.9.0+first ")
        self.assertEqual(max_satisfying(["1.0.0-beta.2", "1.0.0-beta.11"], ">=1.0.0-0"),
                         "1.0.0-beta.11")
        self.assertIsNone(max_satisfying(versions, "^3"))
        self.assertIsNone(max_satisfying([], "*"))
        self.assertIsNone(max_satisfying(["invalid", "1.2"], "*"))


if __name__ == "__main__":
    unittest.main()
