import unittest

from semver_range import max_satisfying, satisfies


class SemverRangeTests(unittest.TestCase):
    def test_precedence_and_build_metadata(self):
        ordered = [
            '1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta',
            '1.0.0-beta', '1.0.0-beta.2', '1.0.0-beta.11',
            '1.0.0-rc.1', '1.0.0', '1.0.1', '1.1.0', '2.0.0',
        ]
        for lower, upper in zip(ordered, ordered[1:]):
            with self.subTest(lower=lower, upper=upper):
                self.assertEqual(max_satisfying([lower, upper], '>=1.0.0-alpha'), upper)
                self.assertFalse(satisfies(upper, '<=' + lower))
        self.assertTrue(satisfies(' v1.2.3+build.01 ', '= 1.2.3+other'))
        self.assertTrue(satisfies('=1.2.3', 'v1.2.3'))
        self.assertTrue(satisfies('1.2.3-A', '>1.2.3-9'))
        self.assertTrue(satisfies('1.2.3-a', '>1.2.3-Z'))

    def test_comparators_and_sets(self):
        cases = [
            ('1.2.3', '', True), ('1.2.3', '  ', True),
            ('1.2.3', '> 1.0.0 <= 1.2.3', True),
            ('1.2.3', '>1.2.3', False), ('1.2.3', '<1.2.3', False),
            ('1.2.3', '>=1.2.3', True), ('1.2.3', '1.2.4', False),
            ('1.2.3', '<1.0.0 || >=1.2.0 <2.0.0', True),
            ('2.0.0', '1.x || 3.x', False), ('2.0.0', '||1.x', True),
        ]
        for version, range_, expected in cases:
            with self.subTest(version=version, range_=range_):
                self.assertEqual(satisfies(version, range_), expected)

    def test_partial_and_wildcard_boundaries(self):
        cases = [
            ('1.2', '1.2.0', '1.3.0'), ('1.2.x', '1.2.9', '1.3.0'),
            ('1.2.*', '1.2.0', '1.1.9'), ('1', '1.9.9', '2.0.0'),
            ('1.x', '1.0.0', '0.9.9'), ('1.x.x', '1.9.9', '2.0.0'),
            ('>1.2', '1.3.0', '1.2.99'), ('>1', '2.0.0', '1.99.99'),
            ('>=1.2', '1.2.0', '1.1.99'), ('<1.2', '1.1.99', '1.2.0'),
            ('<=1.2', '1.2.99', '1.3.0'), ('<=1', '1.99.99', '2.0.0'),
            ('=1.2', '1.2.0', '1.3.0'),
        ]
        for range_, inside, outside in cases:
            with self.subTest(range_=range_):
                self.assertTrue(satisfies(inside, range_))
                self.assertFalse(satisfies(outside, range_))
        for range_ in ['*', 'x', 'X', '>=*', '<=*', '=*']:
            self.assertTrue(satisfies('0.0.0', range_))
            self.assertTrue(satisfies('999.1.2', range_))
        for range_ in ['>*', '<*']:
            self.assertFalse(satisfies('0.0.0', range_))
            self.assertFalse(satisfies('2.0.0', range_))

    def test_tilde_and_caret_boundaries(self):
        cases = [
            ('~1.2.3', '1.2.3', '1.3.0'), ('~1.2', '1.2.0', '1.3.0'),
            ('~1', '1.0.0', '2.0.0'), ('~0.2.3', '0.2.3', '0.3.0'),
            ('^1.2.3', '1.2.3', '2.0.0'), ('^0.2.3', '0.2.3', '0.3.0'),
            ('^0.0.3', '0.0.3', '0.0.4'), ('^1.2', '1.2.0', '2.0.0'),
            ('^1.2.x', '1.2.0', '2.0.0'), ('^1', '1.0.0', '2.0.0'),
            ('^1.x', '1.0.0', '2.0.0'), ('^0.0', '0.0.0', '0.1.0'),
            ('^0.0.x', '0.0.0', '0.1.0'), ('^0.x', '0.0.0', '1.0.0'),
            ('^0', '0.0.0', '1.0.0'), ('^0.1', '0.1.0', '0.2.0'),
        ]
        for range_, lower, upper in cases:
            with self.subTest(range_=range_):
                self.assertTrue(satisfies(lower, range_))
                self.assertFalse(satisfies(upper, range_))
                if lower != '0.0.0':
                    self.assertFalse(satisfies('0.0.0', range_))

    def test_hyphen_ranges(self):
        cases = [
            ('1.2.3 - 2.3.4', '1.2.3', '2.3.4', '2.3.5'),
            ('1.2 - 2.3.4', '1.2.0', '2.3.4', '2.3.5'),
            ('1.2.3 - 2.3', '1.2.3', '2.3.99', '2.4.0'),
            ('1.2.3 - 2', '1.2.3', '2.99.99', '3.0.0'),
        ]
        for range_, lower, upper, outside in cases:
            with self.subTest(range_=range_):
                self.assertTrue(satisfies(lower, range_))
                self.assertTrue(satisfies(upper, range_))
                self.assertFalse(satisfies(outside, range_))
                self.assertFalse(satisfies('1.1.99', range_))
        self.assertTrue(satisfies('2.0.0', '1 - 3 <2.1.0'))

    def test_prerelease_eligibility_is_per_set_and_not_synthetic(self):
        cases = [
            ('1.0.0-rc.1', '*', False), ('1.0.0-rc.1', '', False),
            ('1.2.4-alpha', '^1.2.3', False),
            ('1.2.3-beta.4', '^1.2.3-beta.2', True),
            ('1.2.3-beta.4', '~1.2.3-beta.2', True),
            ('1.2.3-beta.1', '^1.2.3-beta.2', False),
            ('1.3.0-alpha', '~1.2.3-beta.2', False),
            ('1.2.3-alpha', '>=1.2.3-alpha <1.2.3', True),
            ('1.2.4-alpha', '>=1.2.3-alpha', False),
            ('1.2.3-alpha', '>2.0.0 || <1.2.3', False),
            ('1.2.3-alpha', '>1.2.3-beta || *', False),
            ('1.3.0-0', '1.2 <1.3.0-beta', False),
            ('2.3.4-beta', '1.2.3 - 2.3.4-beta', True),
        ]
        for version, range_, expected in cases:
            with self.subTest(version=version, range_=range_):
                self.assertEqual(satisfies(version, range_), expected)

    def test_invalid_versions(self):
        for version in [
            '', '1', '1.2', '1.2.3.4', '01.2.3', '1.02.3', '1.2.03',
            '1.2.3-01', '1.2.3-a.01', '1.2.3-', '1.2.3+', '1.2.3-a..b',
            '1.2.3+a..b', '1.2.3-a_b', '1.2.3+ä', 'vv1.2.3', '==1.2.3',
            'v=1.2.3', '1.2.3 extra', '١.2.3', None, 123,
        ]:
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    satisfies(version, '*')

    def test_invalid_ranges_even_in_unused_branches(self):
        for range_ in [
            '~>1.2', '>=1.2.3 -', '1.2.3.4', '^', '>=a.b.c',
            '>', '<=', '1.2.3 || garbage', '* || ^', '1.2.3 | 2.0.0',
            '1.2.3, <2.0.0', '1.2.3<2.0.0', '==1.2.3',
            '1.2-beta', '1.2+build', '1.x.3', '*.1', '1.2.x-a',
            '01.2', '1.2.3-01', '1.2.3+', '1.2.3 - >2.0.0',
            '1.2.3 - 2.0.0 - 3.0.0', None, 123,
        ]:
            with self.subTest(range_=range_):
                with self.assertRaises(ValueError):
                    satisfies('1.2.3', range_)
                with self.assertRaises(ValueError):
                    max_satisfying([], range_)

    def test_max_skips_invalid_versions_and_preserves_first_tie(self):
        versions = ['bad', '1.2', None, 'v1.2.3+first', '1.2.3+second', '2.0.0']
        self.assertEqual(max_satisfying(versions, '^1'), 'v1.2.3+first')
        self.assertEqual(max_satisfying(versions, '*'), '2.0.0')
        self.assertIsNone(max_satisfying(versions, '^3'))
        self.assertIsNone(max_satisfying([], '*'))
        self.assertEqual(max_satisfying(['1.0.0-beta.11', '1.0.0-beta.2'],
                                        '>=1.0.0-beta'), '1.0.0-beta.11')


if __name__ == '__main__':
    unittest.main()
