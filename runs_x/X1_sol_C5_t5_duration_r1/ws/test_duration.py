import unittest
from decimal import localcontext

from duration import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_valid_unit_durations(self):
        cases = {
            '1h30m': 5400, ' 2d 4h ': 187200, '1.5h': 5400,
            '1w2d3h4m5s': 788645, '1w': 604800, '1d': 86400,
            '1m': 60, '1s': 1, '05m': 300, '1.5m': 90,
            '0.1h': 360, '0.25m': 15, '0.001h0.4s': 4,
            '0h0m0s': 0, '-45s': -45, '-1h': -3600,
            '-0s': 0, '0': 0, '-0': 0, '\t-1m\n': -60,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                result = parse_duration(value)
                self.assertEqual(result, expected)
                self.assertIs(type(result), int)

    def test_valid_clock_durations(self):
        cases = {
            '1:30': 90, '1:00:00': 3600, '90:00': 5400,
            '1:02:03': 3723, '-1:30': -90, '0:00': 0,
            '000:00:01': 1, '0:59:59': 3599, '123:59:59': 446399,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), expected)

    def test_rejects_invalid_syntax_and_fractional_seconds(self):
        cases = [
            '', ' \t\n', '5', '1.5', '00', '-00', '.5h', '5.h',
            '1 h', '1H', '30m1h', '1h1h', '0s0m', '1h  30m',
            '1h\t30m', '1h\n30m', '1h,30m', '1h+30m', '1h-30m',
            '1h 30', '1h junk', '1e3s', 'NaNs', 'infs', '0.3s',
            '0.00000000000000000000000000001s', '1.01m',
            '+1h', '--1h', '- 1h', '-\t1h', '-+1h',
            '1:60', '1:5', '1:00:60', '1:60:00', '1:000',
            '1:2:03', '1:00:00:00', ':30', '1:', '1.5:00',
            '1 :30', '1: 30', '1:30s', '1h:30m', '١h', '１:00',
        ]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_duration(value)

    def test_rejects_non_strings(self):
        for value in (None, 0, 1.5, True, b'1h', [], {}):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parse_duration(value)

    def test_arithmetic_is_exact_independent_of_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(parse_duration('12345678901234567890.5m'),
                             740740734074074073430)
            with self.assertRaises(ValueError):
                parse_duration('1.00000000000000000000000000001s')

    def test_first_clock_field_has_no_length_limit(self):
        self.assertEqual(parse_duration('1' + '0' * 5000 + ':00'),
                         60 * 10 ** 5000)


if __name__ == '__main__':
    unittest.main()
