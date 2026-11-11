import unittest

from semver_range import max_satisfying, satisfies


class SemverRangeTests(unittest.TestCase):
    def test_comparators_and_version_normalization(self):
        cases = [
            (' v1.2.3+foo ', '= 1.2.3+bar', True),
            ('=1.2.3', '1.2.3', True),
            ('1.2.4', '>= 1.2.3 < 2.0.0', True),
            ('2.0.0', '>=1.2.3 <2.0.0', False),
            ('1.2.3', '>1.2.3', False),
            ('1.2.3', '<=1.2.3', True),
            ('1.2.3', '9.0.0 || 1.2.3', True),
            ('0.0.0', ' ', True),
            ('1.0.0-rc.1', '*', False),
            ('1.0.0-rc.1', '', False),
        ]
        self.check_cases(cases)

    def check_cases(self, cases):
        for version, range_, expected in cases:
            with self.subTest(version=version, range_=range_):
                self.assertEqual(satisfies(version, range_), expected)

    def test_partial_and_wildcard_boundaries(self):
        for range_ in ['1.2', '1.2.x', '1.2.*', '=1.2']:
            self.check_cases([('1.2.0', range_, True), ('1.2.99', range_, True),
                              ('1.3.0', range_, False), ('1.1.9', range_, False)])
        for range_ in ['1', '1.x', '1.x.x']:
            self.check_cases([('1.9.9', range_, True), ('2.0.0', range_, False)])
        self.check_cases([
            ('1.2.9', '>1.2', False), ('1.3.0', '>1.2', True),
            ('2.0.0', '>1', True), ('1.2.0', '>=1.2', True),
            ('1.2.0', '<1.2', False), ('1.1.9', '<1.2', True),
            ('1.2.9', '<=1.2', True), ('1.3.0', '<=1.2', False),
            ('1.9.9', '<=1', True), ('2.0.0', '<=1', False),
        ])
        for range_ in ['*', 'x', 'X', '>=*', '<=*', '~*', '^*']:
            self.assertTrue(satisfies('0.0.0', range_))
        for range_ in ['>*', '<*']:
            self.assertFalse(satisfies('99.0.0', range_))

    def test_impossible_wildcards_remain_impossible_with_prerelease_opt_in(self):
        for range_ in ['>* >=0.0.0-alpha', '<* >=0.0.0-alpha']:
            self.assertFalse(satisfies('0.0.0-beta', range_))

    def test_tilde_caret_and_hyphen_bounds(self):
        bounds = [
            ('~1.2.3', '1.2.3', '1.3.0'), ('~1.2', '1.2.0', '1.3.0'),
            ('~1', '1.0.0', '2.0.0'), ('~0.2.3', '0.2.3', '0.3.0'),
            ('^1.2.3', '1.2.3', '2.0.0'), ('^0.2.3', '0.2.3', '0.3.0'),
            ('^0.0.3', '0.0.3', '0.0.4'), ('^1.2', '1.2.0', '2.0.0'),
            ('^1.2.x', '1.2.0', '2.0.0'), ('^1.x', '1.0.0', '2.0.0'),
            ('^0.0', '0.0.0', '0.1.0'), ('^0.0.x', '0.0.0', '0.1.0'),
            ('^0', '0.0.0', '1.0.0'), ('^0.x', '0.0.0', '1.0.0'),
            ('^0.1', '0.1.0', '0.2.0'),
            ('1.2.3 - 2.3', '1.2.3', '2.4.0'),
            ('1.2.3 - 2', '1.2.3', '3.0.0'),
        ]
        for range_, lower, upper in bounds:
            self.check_cases([(lower, range_, True), (upper, range_, False),
                              ('0.0.0', range_, lower == '0.0.0')])
        self.check_cases([('2.3.4', '1.2 - 2.3.4', True),
                          ('2.3.5', '1.2.3 - 2.3.4', False),
                          ('1.2.0', '1.2 - 2.3.4', True)])

    def test_prerelease_order_and_explicit_opt_in(self):
        ordered = ['1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta',
                   '1.0.0-beta', '1.0.0-beta.2', '1.0.0-beta.11',
                   '1.0.0-rc.1', '1.0.0']
        for lower, upper in zip(ordered, ordered[1:]):
            self.assertTrue(satisfies(lower, '<' + upper + ' >=1.0.0-0'))
            self.assertFalse(satisfies(upper, '<' + lower))
        self.check_cases([
            ('1.2.4-alpha', '^1.2.3', False),
            ('1.2.3-beta.4', '^1.2.3-beta.2', True),
            ('1.2.3-beta.4', '~1.2.3-beta.2', True),
            ('1.2.3-beta.1', '~1.2.3-beta.2', False),
            ('1.3.0-0', '1.2 >=1.3.0-0', False),
            ('1.2.3-beta', '>=1.2.3-alpha <1.2.3', True),
            ('1.2.4-beta', '>=1.2.3-alpha <2.0.0', False),
            ('1.2.4-beta', '>=1.2.3-alpha || <2.0.0', False),
            ('1.2.3-beta', '1.2.3-alpha - 1.2.3', True),
        ])

    def test_invalid_versions(self):
        invalid = ['', '1', '1.2', '01.2.3', '1.02.3', '1.2.03',
                   '1.2.3-01', '1.2.3-a..b', '1.2.3+', '1.2.3-',
                   '1.2.3+a_b', '1.2.3.4', 'vv1.2.3', '=v1.2.3',
                   '1.2.3-ä', '١.2.3', None, 123]
        for version in invalid:
            with self.subTest(version=version), self.assertRaises(ValueError):
                satisfies(version, '*')
        self.assertTrue(satisfies('1.2.3-0.a-1+001.foo', '1.2.3-0.a-1'))

    def test_invalid_ranges_are_validated_in_full(self):
        invalid = ['~>1.2', '>=1.2.3 -', '1.2.3.4', '^', '>=a.b.c',
                   '1.x.2', '1.2-beta', '1.2+build', '01.2', '>=',
                   '1.2.3<2.0.0', '1.2.3 | 2.0.0', '1.2.3 || garbage',
                   '1.2.3 - - 2.0.0', '!=1.2.3', None]
        for range_ in invalid:
            with self.subTest(range_=range_):
                with self.assertRaises(ValueError):
                    satisfies('1.2.3', range_)
                with self.assertRaises(ValueError):
                    max_satisfying([], range_)

    def test_maximum_skips_invalid_and_preserves_first_equal_string(self):
        self.assertEqual(max_satisfying(['bad', None, '1.2.3', ' v1.9.0+a ',
                                        '1.9.0+b', '2.0.0'], '^1'), ' v1.9.0+a ')
        self.assertEqual(max_satisfying(['1.0.0-beta.2', '1.0.0-beta.11'],
                                        '>=1.0.0-0'), '1.0.0-beta.11')
        self.assertIsNone(max_satisfying(['invalid', '2.0.0'], '^1'))
        self.assertIsNone(max_satisfying([], '*'))


if __name__ == '__main__':
    unittest.main()
