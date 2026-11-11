import unittest

import semver_range as sr


def prec(v):
    return sr._precedence(*sr._parse_version(v))


PROBES = [
    "0.0.0", "0.0.3", "0.0.3-alpha", "0.0.4", "0.0.4-0",
    "0.1.0", "0.1.0-0", "0.1.5", "0.2.0", "0.2.3", "0.2.3-beta", "0.2.4",
    "0.3.0", "0.3.0-0", "1.0.0", "1.0.0-0", "1.0.0-rc.1",
    "1.2.0", "1.2.0-0", "1.2.0-alpha", "1.2.3", "1.2.3-beta.2", "1.2.3-beta.4",
    "1.2.4", "1.2.4-alpha", "1.2.9", "1.3.0", "1.3.0-0", "1.3.0-beta",
    "2.0.0", "2.0.0-0", "2.0.0-rc.1", "2.3.4", "2.3.4-beta", "2.3.5",
    "2.4.0", "2.4.0-0", "2.9.9", "3.0.0", "3.0.0-0", "3.1.0",
]


class Versions(unittest.TestCase):
    def test_spec_examples(self):
        self.assertTrue(sr.satisfies("v1.2.3", "1.2.3"))
        self.assertTrue(sr.satisfies("=1.2.3", "1.2.3"))
        self.assertTrue(sr.satisfies("  1.2.3  ", "1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3+build.5", "1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3", "1.2.3+other"))

    def test_ordering_chain(self):
        chain = [
            "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
            "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0",
        ]
        for lo, hi in zip(chain, chain[1:]):
            self.assertLess(prec(lo), prec(hi), (lo, hi))

    def test_build_ignored_in_ordering(self):
        self.assertEqual(prec("1.0.0+a"), prec("1.0.0+b"))

    def test_invalid_versions_fail(self):
        bad = [
            "", "v", "vv1.2.3", "==1.2.3", "v=1.2.3", "v 1.2.3",
            "01.2.3", "1.02.3", "1.2.03", "1.2", "1.2.3.4", "a.b.c", "-1.2.3",
            "1.2.3-", "1.2.3-01", "1.2.3-beta..1", "1.2.3-beta_1", "1.2.3-é",
            "1.2.3+", "1.2.3+a..b", "1.2.3 beta", "x.y.z", "1.2.x",
        ]
        for v in bad:
            with self.assertRaises(ValueError, msg=v):
                sr.satisfies(v, "*")

    def test_non_string_version_fails(self):
        with self.assertRaises(ValueError):
            sr.satisfies(123, "*")


class Ranges(unittest.TestCase):
    def test_spec_examples(self):
        self.assertTrue(sr.satisfies("1.2.4", "~1.2.3"))
        self.assertFalse(sr.satisfies("1.3.0", "~1.2.3"))
        self.assertTrue(sr.satisfies("1.5.0", "^1.2.3"))
        self.assertFalse(sr.satisfies("2.0.0", "^1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3", "^1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3", "1.2.3 - 2.3.4"))
        self.assertTrue(sr.satisfies("2.3.4", "1.2.3 - 2.3.4"))
        self.assertFalse(sr.satisfies("2.3.5", "1.2.3 - 2.3.4"))
        self.assertTrue(sr.satisfies("1.2.9", "1.2"))
        self.assertFalse(sr.satisfies("1.3.0", "1.2"))
        self.assertTrue(sr.satisfies("1.2.0", "1.2"))
        self.assertTrue(sr.satisfies("7.0.0", "*"))
        self.assertTrue(sr.satisfies("1.0.0", "x"))
        self.assertTrue(sr.satisfies("1.0.0", ""))
        self.assertTrue(sr.satisfies("1.0.0", "   "))
        self.assertTrue(sr.satisfies("9.9.9", "1.2.3 ||"))

    def test_operator_space_is_ignored(self):
        self.assertTrue(sr.satisfies("1.2.3", ">= 1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3", ">=1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3", "~ 1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3", "^ 1.2.3"))
        self.assertFalse(sr.satisfies("1.2.3", "> 1.2.3"))

    def test_strict_comparators(self):
        self.assertTrue(sr.satisfies("1.2.2", "<1.2.3"))
        self.assertFalse(sr.satisfies("1.2.3", "<1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3", "<=1.2.3"))
        self.assertFalse(sr.satisfies("1.2.3", ">1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3", ">=1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3", "=1.2.3"))
        self.assertFalse(sr.satisfies("1.2.4", "=1.2.3"))
        self.assertFalse(sr.satisfies("1.2.4", "1.2.3"))

    def test_desugaring_equivalences(self):
        equiv = [
            ("~1.2.3", ">=1.2.3 <1.3.0-0"),
            ("~1.2", ">=1.2.0 <1.3.0-0"),
            ("~1", ">=1.0.0 <2.0.0-0"),
            ("~0.2.3", ">=0.2.3 <0.3.0-0"),
            ("~1.2.3-beta.2", ">=1.2.3-beta.2 <1.3.0-0"),
            ("^1.2.3", ">=1.2.3 <2.0.0-0"),
            ("^0.2.3", ">=0.2.3 <0.3.0-0"),
            ("^0.0.3", ">=0.0.3 <0.0.4-0"),
            ("^1.2.3-beta.2", ">=1.2.3-beta.2 <2.0.0-0"),
            ("^1.2", ">=1.2.0 <2.0.0-0"),
            ("^1.2.x", ">=1.2.0 <2.0.0-0"),
            ("^1", ">=1.0.0 <2.0.0-0"),
            ("^1.x", ">=1.0.0 <2.0.0-0"),
            ("^0.0", ">=0.0.0 <0.1.0-0"),
            ("^0.0.x", ">=0.0.0 <0.1.0-0"),
            ("^0.x", ">=0.0.0 <1.0.0-0"),
            ("^0", ">=0.0.0 <1.0.0-0"),
            ("^0.1", ">=0.1.0 <0.2.0-0"),
            ("1.2.3 - 2.3.4", ">=1.2.3 <=2.3.4"),
            ("1.2 - 2.3.4", ">=1.2.0 <=2.3.4"),
            ("1.2.3 - 2.3", ">=1.2.3 <2.4.0-0"),
            ("1.2.3 - 2", ">=1.2.3 <3.0.0-0"),
            ("1.2", ">=1.2.0 <1.3.0-0"),
            ("1.2.x", ">=1.2.0 <1.3.0-0"),
            ("1.2.*", ">=1.2.0 <1.3.0-0"),
            ("1", ">=1.0.0 <2.0.0-0"),
            ("1.x", ">=1.0.0 <2.0.0-0"),
            ("1.x.x", ">=1.0.0 <2.0.0-0"),
            ("*", ">=0.0.0"),
            ("x", ">=0.0.0"),
            ("X", ">=0.0.0"),
            (">1.2", ">=1.3.0"),
            (">1", ">=2.0.0"),
            (">=1.2", ">=1.2.0"),
            ("<1.2", "<1.2.0-0"),
            ("<=1.2", "<1.3.0-0"),
            ("<=1", "<2.0.0-0"),
            ("=1.2", "1.2"),
            (">=*", ">=0.0.0"),
            ("<=*", ">=0.0.0"),
        ]
        for written, desugared in equiv:
            for v in PROBES:
                self.assertEqual(
                    sr.satisfies(v, written), sr.satisfies(v, desugared),
                    (v, written, desugared),
                )

    def test_wildcard_operators(self):
        self.assertFalse(sr.satisfies("1.0.0", ">*"))
        self.assertFalse(sr.satisfies("1.0.0", "<*"))
        self.assertTrue(sr.satisfies("1.0.0", ">=*"))
        self.assertTrue(sr.satisfies("1.0.0", "<=*"))

    def test_partial_comparators_fail_on_wrong_values(self):
        self.assertFalse(sr.satisfies("1.3.0", "1.2.x"))
        self.assertFalse(sr.satisfies("2.0.0", "1.x"))
        self.assertFalse(sr.satisfies("1.2.0", ">1.2"))
        self.assertFalse(sr.satisfies("1.2.9", ">1.2"))
        self.assertTrue(sr.satisfies("1.3.0", ">1.2"))
        self.assertFalse(sr.satisfies("1.2.0-alpha", "<1.2"))

    def test_or_sets(self):
        self.assertTrue(sr.satisfies("2.5.0", "1.2.3 || ^2"))
        self.assertTrue(sr.satisfies("1.2.3", "1.2.3 || ^2"))
        self.assertFalse(sr.satisfies("3.0.0", "1.2.3 || ^2"))
        self.assertFalse(sr.satisfies("1.2.4", "1.2.3 || 1.2.5"))

    def test_invalid_ranges_fail(self):
        bad = [
            "~>1.2", ">=1.2.3 -", "1.2.3.4", "^", ">=a.b.c", "- 1.2.3",
            "1.2.3 - ", "1.2.3 - 2 - 3", "1.2-beta", "^*", "~*", "~x", "^x",
            "1.*.3", "1.x.3", "~ ", "> ", ">= ", "~>1", "1.2.3-", "=> 1.2",
            "<>1.2", "1.2+build", "^01.2.3", "1.2.3 - 2.3.4.5", "1.2.3-2.3.4.5 -",
            "1.2.3 ~", "1.2.3 - - 2",
        ]
        for r in bad:
            with self.assertRaises(ValueError, msg=r):
                sr.satisfies("1.2.3", r)


class Prerelease(unittest.TestCase):
    def test_spec_examples(self):
        self.assertFalse(sr.satisfies("1.2.4-alpha", "^1.2.3"))
        self.assertTrue(sr.satisfies("1.2.3-beta.4", "^1.2.3-beta.2"))
        self.assertFalse(sr.satisfies("1.0.0-rc.1", "*"))

    def test_prerelease_needs_matching_base(self):
        self.assertFalse(sr.satisfies("1.2.3-beta.4", "^1.2.4"))
        self.assertFalse(sr.satisfies("1.2.3-beta.4", ">=1.2.0"))
        self.assertTrue(sr.satisfies("1.2.3-beta.4", ">=1.2.3-beta.2 <1.2.3-beta.9"))
        self.assertFalse(sr.satisfies("1.2.3-beta.10", "<1.2.3-beta.9"))

    def test_bound_zero_does_not_open_prereleases(self):
        self.assertFalse(sr.satisfies("1.3.0-beta", "^1.2.3"))
        self.assertFalse(sr.satisfies("2.0.0-rc.1", "^1.2.3"))

    def test_prerelease_ok_in_other_set(self):
        self.assertTrue(sr.satisfies("1.2.4-alpha", "^1.2.3 || ^1.2.4-alpha"))
        self.assertFalse(sr.satisfies("1.2.4-alpha", "^1.2.3 || ^1.2.5"))

    def test_plain_prerelease_exact(self):
        self.assertTrue(sr.satisfies("1.0.0-rc.1", "1.0.0-rc.1"))
        self.assertFalse(sr.satisfies("1.0.0-rc.2", "1.0.0-rc.1"))


class MaxSatisfying(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            sr.max_satisfying(["1.2.3", "1.2.4", "1.3.0", "2.0.0"], "^1.2.3"), "1.3.0"
        )

    def test_returned_exactly_as_given(self):
        self.assertEqual(sr.max_satisfying([" v1.2.3 "], "1.2.3"), " v1.2.3 ")

    def test_invalid_entries_skipped(self):
        self.assertEqual(sr.max_satisfying(["bad", "1.2.3", None, "01.0.0"], "*"), "1.2.3")

    def test_none_when_no_match(self):
        self.assertIsNone(sr.max_satisfying(["1.2.4-alpha", "0.9.0"], "^1.2.3"))
        self.assertIsNone(sr.max_satisfying([], "*"))

    def test_invalid_range_raises(self):
        with self.assertRaises(ValueError):
            sr.max_satisfying([], "~>1.2")
        with self.assertRaises(ValueError):
            sr.max_satisfying(["1.2.3"], "~>1.2")

    def test_tie_returns_first(self):
        self.assertEqual(sr.max_satisfying(["1.0.0+b", "1.0.0+a"], "*"), "1.0.0+b")
        self.assertEqual(sr.max_satisfying(["1.0.0+a", "1.0.0+b"], "*"), "1.0.0+a")

    def test_prerelease_not_picked_by_star(self):
        self.assertEqual(sr.max_satisfying(["1.0.0-rc.1", "0.9.0"], "*"), "0.9.0")

    def test_prerelease_picked_when_matching(self):
        self.assertEqual(
            sr.max_satisfying(["1.2.3", "1.2.4-alpha", "1.2.3-beta.4"], ">=1.2.3-beta.2"),
            "1.2.3",
        )


if __name__ == "__main__":
    unittest.main()
