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


class CleanerTests(unittest.TestCase):
    def run_export(self, rows, header=HEADER, prefix=''):
        source = io.StringIO(newline='')
        source.write(prefix)
        writer = csv.writer(source)
        writer.writerow(header)
        writer.writerows(rows)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            infile = Path(directory) / 'input.csv'
            outfile = Path(directory) / 'output.csv'
            infile.write_text(source.getvalue(), encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(ROOT / 'clean.py'), str(infile), str(outfile)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = outfile.read_bytes()
        self.assertNotIn(b'\r', data)
        self.assertEqual(next(csv.reader(io.StringIO(data.decode()))), HEADER[:-1])
        return list(csv.DictReader(io.StringIO(data.decode())))

    def test_headers_normalization_and_quoting(self):
        result = self.run_export([
            [' PAID ', '2026/3/4', ' £ ', ' $ 12.50 ', ' A@B ', ' a,1 ', '', 'extra'],
        ], [' Status ', 'Order Date', 'Currency', 'Amount', 'Customer Email',
            ' Order ID ', 'Updated At', 'Ignored'], '\ufeff\n# comment\n')
        self.assertEqual(result, [dict(order_id='A,1', customer_email='a@b',
                                     amount='12.50', currency='GBP',
                                     order_date='2026-03-04', status='paid')])

    def test_amounts_rounding_and_currency(self):
        cases = [('$1,234.50', '1234.50', 'USD'),
                 ('1.234,56€', '1234.56', 'EUR'),
                 ('(£1,000.005)', '-1000.01', 'GBP'),
                 ('2.005', '2.01', 'USD'), ('-2.005', '-2.01', 'USD'),
                 ('7,5', '75.00', 'USD'), ('1,000', '1000.00', 'USD'),
                 ('12,50', '12.50', 'USD'), ('1 234,50', '1234.50', 'USD'),
                 ('0', '0.00', 'USD'), ('1,234,567.89', '1234567.89', 'USD'),
                 ('123456789012345678901234567890.005',
                  '123456789012345678901234567890.01', 'USD')]
        rows = [[str(i).zfill(2), '', raw, '', '2026-1-1', '', '']
                for i, (raw, _, _) in enumerate(cases)]
        result = self.run_export(rows)
        self.assertEqual([(r['amount'], r['currency']) for r in result],
                         [(amount, currency) for _, amount, currency in cases])

    def test_date_formats_and_sorting(self):
        dates = ['2026-3-4', '2026/3/4', '4.3.2026', '3/4/2026',
                 'Mar 4, 2026', 'mArCh 4, 2026', '4 MAR 2026', '4 march 2026']
        rows = [[str(i), '', '1', '', date, '', '']
                for i, date in reversed(list(enumerate(dates)))]
        rows.append(['z', '', '1', '', '2026-3-3', '', ''])
        result = self.run_export(rows)
        self.assertEqual([r['order_id'] for r in result], ['Z'] + list('01234567'))
        self.assertEqual([r['order_date'] for r in result],
                         ['2026-03-03'] + ['2026-03-04'] * 8)

    def test_invalid_rows_do_not_replace_valid_duplicates(self):
        rows = [['a', '', '1', '', '2026-1-1', '', '']]
        for amount in ['', 'garbage', 'NaN', 'Infinity', '1.2.3', '(12', '--1']:
            rows.append(['a', '', amount, '', '2026-1-1', '', '2026-12-31T00:00:00Z'])
        for date in ['', '2026-02-30', 'Mar 4 2026', '2026-13-1']:
            rows.append(['a', '', '2', '', date, '', '2026-12-31T00:00:00'])
        rows.append([' ', '', '1', '', '2026-1-1', '', ''])
        result = self.run_export(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['amount'], '1.00')

    def test_deduplication_latest_then_later_tie(self):
        rows = [[' a ', '', '1', '', '2026-1-1', '', '2026-01-02T00:00:00Z'],
                ['A', '', '2', '', '2026-1-1', '', '2026-01-01 00:00:00'],
                ['a', '', '3', '', '2026-1-1', '', '2026-01-02 00:00:00'],
                ['a', '', '4', '', '2026-1-1', '', ''],
                ['b', '', '5', '', '2026-1-1', '', ''],
                ['B', '', '6', '', '2026-1-1', '', '']]
        self.assertEqual([r['amount'] for r in self.run_export(rows)], ['3.00', '6.00'])

    def test_email_status_and_explicit_currency(self):
        emails = ['X@Y', 'a@@b', '@b', 'a@', 'invalid', '']
        statuses = ['pending', 'PAID', 'shipped', 'Canceled', 'refunded', 'lost']
        rows = [[str(i), email, '€1', ' usd ', '2026-1-1', status, '']
                for i, (email, status) in enumerate(zip(emails, statuses))]
        result = self.run_export(rows)
        self.assertEqual([r['customer_email'] for r in result], ['x@y'] + [''] * 5)
        self.assertEqual([r['status'] for r in result],
                         ['pending', 'paid', 'shipped', 'cancelled', 'refunded', 'unknown'])
        self.assertEqual([r['currency'] for r in result], ['USD'] * 6)

    def test_empty_export(self):
        self.assertEqual(self.run_export([]), [])

    def test_empty_timestamp_is_older_than_any_real_timestamp(self):
        result = self.run_export([
            ['a', '', '1', '', '2026-1-1', '', '0001-01-01T00:00:00'],
            ['a', '', '2', '', '2026-1-1', '', ''],
        ])
        self.assertEqual(result[0]['amount'], '1.00')


if __name__ == '__main__':
    unittest.main()
