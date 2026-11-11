import unittest

from semver_range import max_satisfying, satisfies


class RangeTests(unittest.TestCase):
    def test_comparators_and_version_precedence(self):
        cases = [
            (' v1.2.3+abc ', '= 1.2.3+def', True),
            ('=1.2.3', '>= 1.2.3 < 2.0.0', True),
            ('2.0.0', '>=1.2.3 <2.0.0', False),
            ('1.2.3-beta.11', '>1.2.3-beta.2', True),
            ('1.2.3-alpha.1', '>1.2.3-alpha', True),
            ('1.2.3-2', '<1.2.3-a', True),
            ('1.2.3-A', '<1.2.3-a', True),
            ('1.2.3', '1.2.3 || 3.0.0', True),
            ('9.0.0', '', True),
            ('9.0.0', '  ', True),
        ]
        for version, range_, expected in cases:
            with self.subTest(version=version, range_=range_):
                self.assertEqual(satisfies(version, range_), expected)

    def test_partial_tilde_caret_and_hyphen_bounds(self):
        cases = [
            ('1.2', '1.2.0', '1.3.0'), ('1.2.x', '1.2.9', '1.3.0'),
            ('1.*', '1.9.9', '2.0.0'), ('1.x.x', '1.0.0', '2.0.0'),
            ('>1.2', '1.3.0', '1.2.99'), ('>1', '2.0.0', '1.9.9'),
            ('>=1.2', '1.2.0', '1.1.9'), ('<1.2', '1.1.9', '1.2.0'),
            ('<=1.2', '1.2.99', '1.3.0'), ('<=1', '1.99.0', '2.0.0'),
            ('=1.2', '1.2.0', '1.3.0'),
            ('~1.2.3', '1.2.99', '1.3.0'), ('~1.2', '1.2.0', '1.3.0'),
            ('~1', '1.99.0', '2.0.0'), ('~0.2.3', '0.2.4', '0.3.0'),
            ('^1.2.3', '1.9.0', '2.0.0'), ('^0.2.3', '0.2.9', '0.3.0'),
            ('^0.0.3', '0.0.3', '0.0.4'), ('^1.2.x', '1.9.0', '2.0.0'),
            ('^0.0', '0.0.99', '0.1.0'), ('^0.0.x', '0.0.99', '0.1.0'),
            ('^0.x', '0.99.0', '1.0.0'), ('^0', '0.99.0', '1.0.0'),
            ('^0.1', '0.1.9', '0.2.0'),
            ('1.2.3 - 2.3.4', '2.3.4', '2.3.5'),
            ('1.2 - 2.3.4', '1.2.0', '1.1.9'),
            ('1.2.3 - 2.3', '2.3.99', '2.4.0'),
            ('1.2.3 - 2', '2.99.0', '3.0.0'),
        ]
        for range_, inside, outside in cases:
            with self.subTest(range_=range_):
                self.assertTrue(satisfies(inside, range_))
                self.assertFalse(satisfies(outside, range_))

    def test_wildcards(self):
        for range_ in ['*', 'x', 'X', '>=*', '<=*', '~*', '^*']:
            self.assertTrue(satisfies('0.0.0', range_))
            self.assertTrue(satisfies('123.4.5', range_))
            self.assertFalse(satisfies('1.0.0-rc.1', range_))
        for range_ in ['>*', '<*']:
            self.assertFalse(satisfies('0.0.0', range_))
            self.assertFalse(satisfies('1.2.3', range_))

    def test_strict_wildcard_comparators_remain_empty_with_prereleases(self):
        for range_ in ['>* >=0.0.0-0', '<* >=0.0.0-0']:
            self.assertFalse(satisfies('0.0.0-alpha', range_))

    def test_prerelease_admission_is_explicit_and_per_set(self):
        cases = [
            ('1.2.4-alpha', '^1.2.3', False),
            ('1.2.3-beta.4', '^1.2.3-beta.2', True),
            ('1.2.3-beta.4', '~1.2.3-beta.2', True),
            ('1.3.0-alpha', '~1.2.3 >=1.3.0-0', False),
            ('1.2.3-alpha', '>=1.2.3-0 <1.2.3', True),
            ('1.2.3-beta', '>1.2.3 || <1.0.0-alpha', False),
            ('1.2.3-beta', '* || >1.2.3-alpha <1.2.3', True),
            ('1.2.3-beta', '1.2.3-alpha - 1.2.3', True),
            ('1.2.3-beta', '1 - 1.2.3-beta.2', True),
        ]
        for version, range_, expected in cases:
            with self.subTest(version=version, range_=range_):
                self.assertEqual(satisfies(version, range_), expected)

    def test_invalid_versions(self):
        for version in ['', '1', '1.2', '01.2.3', '1.02.3', '1.2.03',
                        '1.2.3-01', '1.2.3-a..b', '1.2.3+', '1.2.3-α',
                        'vv1.2.3', '=v1.2.3', '1.2.3.4', '1.2.3\nextra']:
            with self.subTest(version=version), self.assertRaises(ValueError):
                satisfies(version, '*')
        self.assertTrue(satisfies('1.2.3-0a+001', '1.2.3-0a'))

    def test_invalid_ranges_are_validated_before_matching(self):
        for range_ in ['~>1.2', '>=1.2.3 -', '1.2.3.4', '^', '>=a.b.c',
                       '1.2-beta', '1+build', '1.x.2', '1..2', '01.2',
                       '1.2.3, <2.0.0', '1.2.3<2.0.0', '|', '1.2.3 || ^',
                       '1.2.3 - >=2.0.0', '1.2.3 - 2.3 - 3', '><1.2.3']:
            with self.subTest(range_=range_):
                with self.assertRaises(ValueError):
                    satisfies('1.2.3', range_)
                with self.assertRaises(ValueError):
                    max_satisfying([], range_)

    def test_maximum_skips_invalid_and_preserves_first_equal_string(self):
        self.assertEqual(max_satisfying(
            ['invalid', '2.0.0', 'v1.9.0+first', '1.9.0+second', '1.8.0'],
            '^1.0.0'), 'v1.9.0+first')
        self.assertEqual(max_satisfying(
            ['1.0.0-beta.2', '1.0.0-beta.11', '1.0.0-beta.3'],
            '>=1.0.0-beta.0 <1.0.0'), '1.0.0-beta.11')
        self.assertIsNone(max_satisfying(['bad', '2.0.0'], '^1'))
        self.assertIsNone(max_satisfying([], '*'))


if __name__ == '__main__':
    unittest.main()
