"""Executable examples and strictness checks from TASK.md."""
import unittest

from semver_range import _parse_range, _parse_version, max_satisfying, satisfies


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
            '=1.2': '>=1.2.0 <1.3.0-0',
            '>=*': '>=0.0.0', '<=*': '>=0.0.0',
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
        }
        probes = ['0.0.0', '0.0.3', '0.0.4', '0.1.0', '0.2.3', '0.3.0',
                  '1.0.0', '1.2.0', '1.2.3-beta.1', '1.2.3-beta.2',
                  '1.2.3-beta.4', '1.2.3', '1.2.9', '1.3.0-0', '1.3.0',
                  '2.0.0-0', '2.0.0', '2.3.4', '2.4.0', '3.0.0']
        for expression, expanded in examples.items():
            with self.subTest(expression=expression):
                self.assertEqual(_parse_range(expression)[0][0], _parse_range(expanded)[0][0])
                for version in probes:
                    self.assertEqual(satisfies(version, expression), satisfies(version, expanded))

    def test_ordering_and_version_forms(self):
        ordered = ('1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta',
                   '1.0.0-beta', '1.0.0-beta.2', '1.0.0-beta.11',
                   '1.0.0-rc.1', '1.0.0')
        for lower, upper in zip(ordered, ordered[1:]):
            self.assertLess(_parse_version(lower), _parse_version(upper))
            self.assertEqual(max_satisfying([lower, upper], '>=1.0.0-alpha'), upper)
        for version in ['1.2.3', 'v1.2.3', '=1.2.3', ' \t1.2.3\n',
                        '1.2.3+001', '1.2.3+abc.0-a']:
            self.assertTrue(satisfies(version, '1.2.3'))
        self.assertTrue(satisfies('1.2.3-a.0.Z-1+foo.001', '=1.2.3-a.0.Z-1'))
        self.assertLess(_parse_version('1.0.0-9'), _parse_version('1.0.0-A'))
        self.assertLess(_parse_version('1.0.0-Z'), _parse_version('1.0.0-a'))
        self.assertLess(_parse_version('2.9.9'), _parse_version('10.0.0'))

    def test_matching_rules(self):
        cases = [
            ('1.2.4-alpha', '^1.2.3', False),
            ('1.2.3-beta.4', '^1.2.3-beta.2', True),
            ('1.0.0-rc.1', '*', False),
            ('1.3.0-0', '1.2 >=1.3.0-0', False),
            ('1.2.3-beta', '>=1.2.3-alpha <2', True),
            ('1.2.4-beta', '>=1.2.3-alpha <2', False),
            ('1.2.3-beta', '>=1.2.3-alpha <2 || >=3', True),
            ('1.2.3-beta', '>=1.2.3-alpha <1 || *', False),
            ('1.2.3-beta', '1.2.3-alpha - 1.2.3', True),
            ('1.2.3-beta', '1 - 1.2.3-beta', True),
            ('1.2.3', '>= 1.2.3', True), ('1.2.2', '>= 1.2.3', False),
            ('1.2.3', '<=1.2.3', True), ('1.2.4', '<=1.2.3', False),
            ('1.2.3', '>1.2.3', False), ('1.2.4', '>1.2.3', True),
            ('1.2.3', '<1.2.3', False), ('1.2.2', '<1.2.3', True),
            ('1.2.3', '=1.2.3', True), ('1.2.4', '1.2.3', False),
            ('2.1.0', '<1 || >=2', True), ('1.1.0', '<1 || >=2', False),
            ('1.2.3', '>=1 <2', True), ('2.0.0', '>=1 <2', False),
        ]
        for version, expression, expected in cases:
            with self.subTest(version=version, expression=expression):
                self.assertEqual(satisfies(version, expression), expected)
        for expression in ['', ' \t', '*', 'x', 'X', '>=*', '<=*', '1 ||']:
            self.assertTrue(satisfies('99.0.0', expression))
            self.assertFalse(satisfies('99.0.0-alpha', expression))
        for expression in ['>*', '<*']:
            for version in ['0.0.0', '1.2.3', '0.0.0-0']:
                self.assertFalse(satisfies(version, expression))

    def test_invalid_versions(self):
        for version in ['', '1', '1.2', '01.2.3', '1.02.3', '1.2.03',
                        '-1.2.3', '1.2.3.4', '1.2.3-', '1.2.3+',
                        '1.2.3-a..b', '1.2.3+a..b', '1.2.3-01',
                        '1.2.3-a.01', '1.2.3-α', '1.2.3+a_b',
                        'vv1.2.3', '==1.2.3', '=v1.2.3', 'v=1.2.3',
                        'V1.2.3', 'v 1.2.3', '1. 2.3', None, 123]:
            with self.subTest(version=version), self.assertRaises(ValueError):
                satisfies(version, '*')

    def test_invalid_ranges(self):
        for expression in ['~>1.2', '>=1.2.3 -', '1.2.3.4', '^', '>=a.b.c',
                           '>=', '~', '< >1.2', '==1.2.3', '1.2-foo',
                           '1+foo', '1.2.x+build', '1.x-beta', '1.x.2',
                           '*.1', '1..2', '01.2', '1.02', '1.2.03',
                           '1.2.3-01', '1.2.3+bad_', '1.2.3|2',
                           '1.2.3 || invalid', '1.2.3, <2', '!=1.2.3',
                           '1 -', '- 2', '1 - >=2', None, 123]:
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    satisfies('1.2.3', expression)
                with self.assertRaises(ValueError):
                    max_satisfying([], expression)

    def test_maximum(self):
        self.assertEqual(max_satisfying(['bad', None, '1.0.0', '2.0.0', '1.9.0'], '^1'), '1.9.0')
        self.assertEqual(max_satisfying(['v1.2.3+first', '=1.2.3+second'], '*'), 'v1.2.3+first')
        self.assertEqual(max_satisfying([' 1.2.3 ', '1.2.3'], '*'), ' 1.2.3 ')
        self.assertIsNone(max_satisfying(['invalid', '2.0.0'], '^1'))
        self.assertIsNone(max_satisfying([], '*'))


if __name__ == '__main__':
    unittest.main()
