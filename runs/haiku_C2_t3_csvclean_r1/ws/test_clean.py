import unittest
from decimal import Decimal

from clean import parse_amount, parse_date


class ParseTest(unittest.TestCase):
    def test_amount(self):
        cases = {
            '$1,234.50': '1234.50', '1.234,56': '1234.56', '(12.50)': '-12.50',
            '2.005': '2.01', '(1,000.005)': '-1000.01', '1,000': '1000.00',
            '€ 7,5': '75.00', '1,234,56': '1234.56', '0.00': '0.00',
        }
        for raw, want in cases.items():
            self.assertEqual(str(parse_amount(raw)), want, raw)
        for bad in ['', 'abc', '1.234.567', '$']:
            self.assertIsNone(parse_amount(bad), bad)
        self.assertEqual(parse_amount('-0'), Decimal('0.00'))

    def test_date(self):
        cases = {
            '2026-03-04': '2026-03-04', '2026/3/9': '2026-03-09', '04.03.2026': '2026-03-04',
            '03/04/2026': '2026-03-04', 'Mar 4, 2026': '2026-03-04', 'March 4 2026': '2026-03-04',
            '4 Mar 2026': '2026-03-04', '7 march 2026': '2026-03-07',
        }
        for raw, want in cases.items():
            self.assertEqual(parse_date(raw), want, raw)
        for bad in ['2026-02-30', 'Foo 4 2026', '', '2026-13-01']:
            self.assertIsNone(parse_date(bad), bad)


if __name__ == '__main__':
    unittest.main()
