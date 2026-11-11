"""Spec examples from TASK.md. Run: python3 -m unittest test_semver_range"""

import unittest

from semver_range import max_satisfying, satisfies


class SatisfiesTest(unittest.TestCase):
    def test_comparators_and_x_ranges(self):
        cases = [
            ("1.2.5", "~1.2.3", True), ("1.3.0", "~1.2.3", False),
            ("1.9.9", "^1.2.3", True), ("2.0.0", "^1.2.3", False),
            ("0.0.3", "^0.0.3", True), ("0.0.4", "^0.0.3", False),
            ("0.0.9", "^0.x", True), ("1.0.0", "^0", False),
            ("1.2.9", "1.2.x", True), ("1.3.0", "1.2.x", False),
            ("1.5.0", ">1.2", True), ("1.2.9", ">1.2", False),
            ("1.2.9", "<1.2", False), ("1.2.9", "<=1.2", True),
            ("9.9.9", "*", True), ("9.9.9", ">*", False), ("0.0.0", "<*", False),
            ("1.2.3", "", True), ("1.2.3", ">= 1.2.3", True), ("v1.2.3+build.5", "=1.2.3", True),
        ]
        for version, rng, want in cases:
            with self.subTest(version=version, range=rng):
                self.assertEqual(satisfies(version, rng), want)

    def test_sets_and_hyphen(self):
        self.assertTrue(satisfies("1.2.3", "1.2.3 || >=2 <3"))
        self.assertTrue(satisfies("2.5.0", "1.2.3 || >=2 <3"))
        self.assertFalse(satisfies("3.0.0", "1.2.3 || >=2 <3"))
        self.assertTrue(satisfies("2.3.4", "1.2 - 2.3.4"))
        self.assertFalse(satisfies("2.3.5", "1.2 - 2.3.4"))
        self.assertFalse(satisfies("2.4.0", "1.2.3 - 2.3"))
        self.assertTrue(satisfies("2.3.9", "1.2.3 - 2.3"))

    def test_prerelease_rule(self):
        self.assertFalse(satisfies("1.2.4-alpha", "^1.2.3"))
        self.assertTrue(satisfies("1.2.3-beta.4", "^1.2.3-beta.2"))
        self.assertFalse(satisfies("1.0.0-rc.1", "*"))

    def test_precedence(self):
        ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
                   "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
        for lower, higher in zip(ordered, ordered[1:]):
            with self.subTest(lower=lower, higher=higher):
                self.assertEqual(max_satisfying([lower, higher], f">={lower}"), higher)

    def test_invalid_input_raises(self):
        for version, rng in [("1.2", "*"), ("01.2.3", "*"), ("1.2.3", "~>1.2"),
                             ("1.2.3", "1.2.3 -"), ("1.2.3", "^"), ("1.2.3", ">=a.b.c"),
                             ("1.2.3", "1.2.3.4"), ("1.2.3", "==1.2.3")]:
            with self.subTest(version=version, range=rng):
                with self.assertRaises(ValueError):
                    satisfies(version, rng)


class MaxSatisfyingTest(unittest.TestCase):
    def test_picks_highest_matching(self):
        versions = ["1.2.3", "1.2.4", "1.3.0-beta", "1.9.9", "2.0.0"]
        self.assertEqual(max_satisfying(versions, "^1.2.3"), "1.9.9")

    def test_skips_invalid_and_returns_none(self):
        self.assertEqual(max_satisfying(["bogus", "1.0.0"], "*"), "1.0.0")
        self.assertIsNone(max_satisfying(["0.9.0"], "^1"))
        self.assertIsNone(max_satisfying([], "*"))

    def test_ties_keep_first_and_invalid_range_raises(self):
        self.assertEqual(max_satisfying(["1.0.0+a", "1.0.0+b"], "*"), "1.0.0+a")
        with self.assertRaises(ValueError):
            max_satisfying(["1.0.0"], "^")


if __name__ == "__main__":
    unittest.main()
