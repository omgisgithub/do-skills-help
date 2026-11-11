import unittest

from semver_range import max_satisfying, satisfies


class SatisfiesTest(unittest.TestCase):
    def test_precedence(self):
        order = ['1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta', '1.0.0-beta',
                 '1.0.0-beta.2', '1.0.0-beta.11', '1.0.0-rc.1', '1.0.0']
        for lo, hi in zip(order, order[1:]):
            self.assertTrue(satisfies(hi, f'>{lo}'), (lo, hi))
            self.assertFalse(satisfies(lo, f'>={hi}'), (lo, hi))
        self.assertTrue(satisfies('v1.2.3+build.9', '= 1.2.3'))

    def test_desugaring(self):
        cases = [
            ('1.2.5', '~1.2.3'), ('1.2.9', '1.2'), ('1.9.9', '1.x'), ('2.0.0', '>1'),
            ('1.3.0', '>1.2'), ('1.2.0', '<=1.2'), ('1.2.9', '<=1.2'), ('2.9.9', '^2.x'),
            ('0.2.9', '^0.2.3'), ('0.0.3', '^0.0.3'), ('0.0.9', '^0.0'), ('0.9.9', '^0'),
            ('0.1.9', '^0.1'), ('2.3.0', '1.2.3 - 2.3'), ('2.9.9', '1.2.3 - 2'),
            ('1.2.3', '1.2 - 2.3.4'), ('1.2.2', '1.2 - 2.3.4'), ('1.0.0', '*'),
            ('9.9.9', '>=*'), ('9.9.9', ''), ('1.2.3', '1.2.3 1.x'),
        ]
        for version, range_ in cases:
            self.assertTrue(satisfies(version, range_), (version, range_))

        misses = [
            ('1.3.0', '~1.2.3'), ('1.2.2', '~1.2.3'), ('2.0.0', '^1.2.3'), ('0.3.0', '^0.2.3'),
            ('0.0.4', '^0.0.3'), ('0.1.0', '^0.0'), ('1.3.0', '1.2'), ('1.9.9', '>1.x'),
            ('1.3.0', '<=1.2'), ('1.2.0', '>1.2'), ('1.3.0-0', '<1.3.0-0'), ('2.4.0', '1.2.3 - 2.3'),
            ('3.0.0', '1.2.3 - 2'), ('0.1.0', '^0.0.3'), ('1.2.3', '>*'), ('1.2.3', '<*'),
        ]
        for version, range_ in misses:
            self.assertFalse(satisfies(version, range_), (version, range_))

    def test_prerelease_rule(self):
        self.assertFalse(satisfies('1.2.4-alpha', '^1.2.3'))
        self.assertTrue(satisfies('1.2.3-beta.4', '^1.2.3-beta.2'))
        self.assertFalse(satisfies('1.0.0-rc.1', '*'))
        self.assertFalse(satisfies('1.2.4-alpha', '1.2.3 - 2.0.0'))
        self.assertTrue(satisfies('1.2.4-alpha', '>=1.2.4-alpha <2'))
        self.assertFalse(satisfies('1.2.3-beta', '<1.2.3-beta || >1.2.3'))

    def test_invalid(self):
        for version in ['01.2.3', '1.2', '1.2.x', '1.2.3-', '1.2.3-01', '1.2.3.4', 'a.b.c', '1.2.3+']:
            with self.assertRaises(ValueError, msg=version):
                satisfies(version, '*')
        for range_ in ['~>1.2', '>=1.2.3 -', '1.2.3.4', '^', '>=a.b.c', '^*', '>=~1', '==1.2.3',
                       '1.2.3 - 2 - 3', '~ 1.2.3', '1.x.3']:
            with self.assertRaises(ValueError, msg=range_):
                satisfies('1.2.3', range_)


class MaxSatisfyingTest(unittest.TestCase):
    def test_picks_highest_and_keeps_input_form(self):
        versions = ['1.2.3', 'bogus', 'v1.2.9', '1.3.0-rc.1', '1.2.10+b1', '1.2.10+b2']
        self.assertEqual(max_satisfying(versions, '~1.2.3'), '1.2.10+b1')
        self.assertIsNone(max_satisfying(['bogus'], '*'))
        self.assertIsNone(max_satisfying([], '*'))

    def test_invalid_range_raises(self):
        with self.assertRaises(ValueError):
            max_satisfying(['1.0.0'], '~>1.2')


if __name__ == '__main__':
    unittest.main()
