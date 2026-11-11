import csv
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
HEADER = ['order_id', 'customer_email', 'amount', 'currency', 'order_date',
          'status', 'updated_at']


class CleanTests(unittest.TestCase):
    def clean(self, rows, header=HEADER, prefix=''):
        source = io.StringIO()
        writer = csv.writer(source)
        writer.writerow(header)
        writer.writerows(rows)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            input_path = Path(directory) / 'input.csv'
            output_path = Path(directory) / 'output.csv'
            input_path.write_text(prefix + source.getvalue(), encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(ROOT / 'clean.py'), str(input_path), str(output_path)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            raw = output_path.read_bytes()
        self.assertNotIn(b'\r', raw)
        parsed = list(csv.reader(io.StringIO(raw.decode('utf-8'))))
        self.assertEqual(parsed[0], HEADER[:-1])
        return parsed[1:]

    def test_header_order_bom_comments_and_normalization(self):
        rows = self.clean([
            [' PAID ', ' <email> ', '2026/3/4', ' a-1 ', ' £ ', ' $ 2.005 ', '', 'ignored'],
            ['canceled', 'bad@@email', '4 mArCh 2026', 'b', '', '€ 1.234,56', '', ''],
            ['lost', 'gina@example', '03/4/2026', 'c', '', '£3.10', '', ''],
        ], [' Status ', 'Customer Email', 'Order Date', ' Order ID ', 'Currency',
            'Amount', 'Updated At', 'Extra'], '\ufeff# comment\n\n')
        self.assertEqual(rows, [
            ['A-1', '<email>', '2.01', 'GBP', '2026-03-04', 'paid'],
            ['B', '', '1234.56', 'EUR', '2026-03-04', 'cancelled'],
            ['C', 'gina@example', '3.10', 'GBP', '2026-03-04', 'unknown'],
        ])

    def test_amount_separator_rules_and_rounding(self):
        cases = [('$1,234.50', '1234.50'), ('1.234,56', '1234.56'),
                 ('7,5', '75.00'), ('1,000', '1000.00'), ('12,50', '12.50'),
                 ('(1,000.005)', '-1000.01'), ('-2.005', '-2.01'),
                 ('£ 1 234,50', '1234.50'), ('0', '0.00'),
                 ('999999999999999999999999999999.995',
                  '1000000000000000000000000000000.00')]
        for amount, expected in cases:
            with self.subTest(amount=amount):
                result = self.clean([['x', '', amount, '', '2026-1-2', '', '']])
                self.assertEqual(result[0][2], expected)

    def test_invalid_fields_drop_rows(self):
        rows = [['ok', '', '1', '', '2026-03-04', '', '']]
        for amount in ['', 'abc', 'NaN', 'Infinity', '1.2.3', '(1', '1)']:
            rows.append(['bad', '', amount, '', '2026-03-04', '', ''])
        for date in ['', '2026-02-30', 'Mar 4 2026', '13/1/2026', '4 Foo 2026']:
            rows.append(['bad', '', '1', '', date, '', ''])
        rows.append(['  ', '', '1', '', '2026-03-04', '', ''])
        self.assertEqual(self.clean(rows), [['OK', '', '1.00', 'USD', '2026-03-04', 'unknown']])

    def test_date_formats_and_sorting(self):
        dates = ['2026-3-4', '2026/3/4', '4.3.2026', '3/4/2026',
                 'Mar 4, 2026', 'mARCH 4, 2026', '4 MAR 2026', '4 March 2026']
        rows = [[str(i), '', '1', '', date, 'pending', '']
                for i, date in reversed(list(enumerate(dates)))]
        rows.append(['z', '', '1', '', '2025-12-31', 'pending', ''])
        result = self.clean(rows)
        self.assertEqual([row[0] for row in result], ['Z', '0', '1', '2', '3', '4', '5', '6', '7'])
        self.assertEqual([row[4] for row in result], ['2025-12-31'] + ['2026-03-04'] * 8)

    def test_deduplication_ignores_invalid_rows_and_breaks_ties_by_position(self):
        rows = [
            [' a ', '', '1', '', '2026-01-01', '', ''],
            ['A', '', '2', '', '2026-01-02', '', '2026-02-01T12:00:00Z'],
            ['a', '', '3', '', '2026-01-03', '', '2026-02-01 12:00:00'],
            ['A', '', '4', '', '2026-01-04', '', '2026-01-01T00:00:00'],
            ['A', '', 'bad', '', '2026-01-05', '', '2026-03-01T00:00:00'],
            ['A', '', '5', '', '2026-02-30', '', '2026-03-01T00:00:00'],
            ['b', '', '6', '', '2026-01-01', '', ''],
            ['B', '', '7', '', '2026-01-02', '', ''],
        ]
        self.assertEqual(self.clean(rows), [
            ['B', '', '7.00', 'USD', '2026-01-02', 'unknown'],
            ['A', '', '3.00', 'USD', '2026-01-03', 'unknown'],
        ])

    def test_csv_quoting_and_empty_export(self):
        self.assertEqual(self.clean([]), [])
        self.assertEqual(self.clean([['a,"b', ' @x ', '1', '', '2026-01-01', '', '']]),
                         [['A,"B', '', '1.00', 'USD', '2026-01-01', 'unknown']])


if __name__ == '__main__':
    unittest.main()
