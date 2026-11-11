"""Executable examples and boundary checks for TASK.md."""
import unittest

from semver_range import max_satisfying, satisfies


class RangeTests(unittest.TestCase):
    def test_spec_expansions(self):
        examples = {
            '1.2': '>=1.2.0 <1.3.0-0',
            '1.2.x': '>=1.2.0 <1.3.0-0',
            '1.2.*': '>=1.2.0 <1.3.0-0',
            '1': '>=1.0.0 <2.0.0-0',
            '1.x': '>=1.0.0 <2.0.0-0',
            '1.x.x': '>=1.0.0 <2.0.0-0',
            '*': '>=0.0.0', 'x': '>=0.0.0', 'X': '>=0.0.0',
            '>1.2': '>=1.3.0', '>1': '>=2.0.0', '>=1.2': '>=1.2.0',
            '<1.2': '<1.2.0-0', '<=1.2': '<1.3.0-0', '<=1': '<2.0.0-0',
            '=1.2': '>=1.2.0 <1.3.0-0', '>=*': '>=0.0.0', '<=*': '>=0.0.0',
            '~1.2.3': '>=1.2.3 <1.3.0-0', '~1.2': '>=1.2.0 <1.3.0-0',
            '~1': '>=1.0.0 <2.0.0-0', '~0.2.3': '>=0.2.3 <0.3.0-0',
            '~1.2.3-beta.2': '>=1.2.3-beta.2 <1.3.0-0',
            '^1.2.3': '>=1.2.3 <2.0.0-0', '^0.2.3': '>=0.2.3 <0.3.0-0',
            '^0.0.3': '>=0.0.3 <0.0.4-0',
            '^1.2.3-beta.2': '>=1.2.3-beta.2 <2.0.0-0',
            '^1.2': '>=1.2.0 <2.0.0-0', '^1.2.x': '>=1.2.0 <2.0.0-0',
            '^1': '>=1.0.0 <2.0.0-0', '^1.x': '>=1.0.0 <2.0.0-0',
            '^0.0': '>=0.0.0 <0.1.0-0', '^0.0.x': '>=0.0.0 <0.1.0-0',
            '^0.x': '>=0.0.0 <1.0.0-0', '^0': '>=0.0.0 <1.0.0-0',
            '^0.1': '>=0.1.0 <0.2.0-0',
            '1.2.3 - 2.3.4': '>=1.2.3 <=2.3.4',
            '1.2 - 2.3.4': '>=1.2.0 <=2.3.4',
            '1.2.3 - 2.3': '>=1.2.3 <2.4.0-0',
            '1.2.3 - 2': '>=1.2.3 <3.0.0-0',
            '>= 1.2.3': '>=1.2.3',
        }
        versions = [
            '%d.%d.%d%s' % (major, minor, patch, suffix)
            for major in range(4) for minor in range(5) for patch in range(6)
            for suffix in ('', '-0', '-alpha', '-beta.1', '-beta.2', '-beta.4', '+build')
        ]
        for source, expanded in examples.items():
            for version in versions:
                with self.subTest(range=source, version=version):
                    self.assertEqual(satisfies(version, source), satisfies(version, expanded))

    def test_version_order_and_build(self):
        ordered = [
            '1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta', '1.0.0-beta',
            '1.0.0-beta.2', '1.0.0-beta.11', '1.0.0-rc.1', '1.0.0',
        ]
        for low, high in zip(ordered, ordered[1:]):
            self.assertTrue(satisfies(high, '>' + low))
            self.assertFalse(satisfies(low, '>=' + high))
        for version in ('1.2.3', 'v1.2.3', '=1.2.3', ' 1.2.3 ', '1.2.3+001.a-b'):
            self.assertTrue(satisfies(version, '1.2.3'))
        self.assertTrue(satisfies('1.2.3-a-b.0+001', '=1.2.3-a-b.0+ignored'))
        self.assertTrue(satisfies('1.0.0-Z', '>1.0.0-9 <1.0.0-a'))
        self.assertFalse(satisfies('1.0.0-a', '<1.0.0-Z'))

    def test_sets_and_prerelease(self):
        for source in ('', '  ', '*', 'x', '>=*', '<=*'):
            self.assertTrue(satisfies('0.0.0', source))
            self.assertTrue(satisfies('100.2.3', source))
            self.assertFalse(satisfies('1.0.0-rc.1', source))
        self.assertFalse(satisfies('1.2.4-alpha', '^1.2.3'))
        self.assertTrue(satisfies('1.2.3-beta.4', '^1.2.3-beta.2'))
        self.assertFalse(satisfies('1.2.3-beta.1', '^1.2.3-beta.2'))
        self.assertTrue(satisfies('1.3.0-0', '^1.2.3 >=1.3.0-0 <1.3.0'))
        self.assertFalse(satisfies('1.3.0-0', '~1.2.3 >=1.3.0-0'))
        self.assertTrue(satisfies('1.2.3', '>=1.0.0 <2.0.0'))
        self.assertFalse(satisfies('2.0.0', '>=1.0.0 <2.0.0'))
        self.assertTrue(satisfies('3.0.0', '1.2.3 || 3.0.0'))
        self.assertFalse(satisfies('2.0.0', '1.2.3 || 3.0.0'))
        self.assertFalse(satisfies('1.2.3-beta', '>=1.2.3 || >=2.0.0-beta'))
        for source in ('>*', '<*'):
            for version in ('0.0.0', '1.2.3', '0.0.0-alpha'):
                self.assertFalse(satisfies(version, source))
            self.assertFalse(satisfies('0.0.0-alpha', source + ' >=0.0.0-alpha'))
        self.assertTrue(satisfies('1.2.3-beta.4', '1.2.3-beta.2 - 1.2.3'))
        self.assertFalse(satisfies('1.2.4-beta', '1.2.3-beta.2 - 1.3.0'))
        self.assertTrue(satisfies('1.2.3-beta', '1.0.0 - 1.2.3-beta'))
        self.assertTrue(satisfies('1.2.3', '1.0.0 - 2.0.0 <1.3.0'))

    def test_invalid_versions(self):
        for value in (
            '', '1', '1.2', '01.2.3', '1.02.3', '1.2.03', '-1.2.3',
            '1.2.3-', '1.2.3+', '1.2.3-a..b', '1.2.3+a..b',
            '1.2.3-01', '1.2.3-a.01', '1.2.3-a_b', '1.2.3+a_b',
            'vv1.2.3', '==1.2.3', 'v=1.2.3', '=v1.2.3', 'v 1.2.3',
            '1.2.3.4', '١.2.3', '1.2.3+ä', None, 123,
        ):
            with self.subTest(version=value):
                with self.assertRaises(ValueError):
                    satisfies(value, '*')
                self.assertIsNone(max_satisfying([value], '*'))

    def test_invalid_ranges(self):
        for source in (
            '~>1.2', '>=1.2.3 -', '1.2.3.4', '^', '>=a.b.c',
            '>', '=', '~', '1.2.3 | 2.0.0', '1.2.3 || rubbish',
            '1.2.3<2.0.0', '1.2.3 -2.3.4', '1.2.3- 2.3.4',
            '1.2.3 - - 2.3.4', '>=  <1.2.3', '==1.2.3', '=>1.2.3',
            '01', '1.02', '1.x.3', 'x.2', '1..2', '1.2-beta', '1+build',
            '1.2.x-alpha', '1.x+build', '1.2.3-01', '1.2.3+', None,
        ):
            with self.subTest(range=source):
                with self.assertRaises(ValueError):
                    satisfies('1.2.3', source)
                with self.assertRaises(ValueError):
                    max_satisfying([], source)

    def test_max_satisfying(self):
        self.assertIsNone(max_satisfying([], '*'))
        self.assertIsNone(max_satisfying(['1.0.0'], '^2.0.0'))
        self.assertEqual(max_satisfying(['bad', '1.2.3', '1.9.0', '2.0.0'], '^1'), '1.9.0')
        self.assertEqual(max_satisfying(['1.2.3+first', 'v1.2.3', '1.2.3+last'], '*'), '1.2.3+first')
        self.assertEqual(max_satisfying(['  =1.2.3  ', '1.0.0'], '*'), '  =1.2.3  ')
        self.assertEqual(max_satisfying(['1.0.0-beta.2', '1.0.0-beta.11'], '>=1.0.0-beta'), '1.0.0-beta.11')


if __name__ == '__main__':
    unittest.main()
