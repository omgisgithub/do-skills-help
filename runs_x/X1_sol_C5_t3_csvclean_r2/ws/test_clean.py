import csv
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HEADER = ['order_id', 'customer_email', 'amount', 'currency', 'order_date', 'status']
INPUT_HEADER = HEADER + ['updated_at']


class CleanerTests(unittest.TestCase):
    def clean(self, rows=None, raw=None):
        if raw is None:
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(INPUT_HEADER)
            writer.writerows(rows)
            raw = stream.getvalue()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / 'input.csv'
            target = Path(directory) / 'output.csv'
            source.write_text(raw, encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name('clean.py')), str(source), str(target)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = target.read_bytes()
            self.assertNotIn(b'\r', output)
            parsed = list(csv.reader(io.StringIO(output.decode('utf-8'))))
            self.assertEqual(parsed[0], HEADER)
            return parsed[1:]

    def test_header_normalization_bom_comments_and_field_cleanup(self):
        raw = ('\ufeff# export\n\n Status , Amount ,Order Date, Customer Email , Order ID ,Currency,Updated At,extra\n'
               ' CANCELED , $ 12.50 ,2026/3/4, ALICE@Example.COM , a-1 , , ,ignored\n'
               '# ignored\n'
               'lost,3,2026-3-5,invalid,b-1, eur ,,ignored\n')
        self.assertEqual(self.clean(raw=raw), [
            ['A-1', 'alice@example.com', '12.50', 'USD', '2026-03-04', 'cancelled'],
            ['B-1', '', '3.00', 'EUR', '2026-03-05', 'unknown'],
        ])

    def test_amount_formats_currency_inference_and_rounding(self):
        cases = [
            ('$1,234.50', '', '1234.50', 'USD'),
            ('1.234,56€', '', '1234.56', 'EUR'),
            ('£ (1,000.005)', '', '-1000.01', 'GBP'),
            ('2.005', '$', '2.01', 'USD'),
            ('-2.005', '€', '-2.01', 'EUR'),
            ('7,5', '£', '75.00', 'GBP'),
            ('1,000', ' cad ', '1000.00', 'CAD'),
            ('1 234,50', '', '1234.50', 'USD'),
            ('1,234,567.89', '', '1234567.89', 'USD'),
            ('1.234.567,89', '', '1234567.89', 'USD'),
            ('0', '', '0.00', 'USD'),
        ]
        for amount, currency, expected, code in cases:
            with self.subTest(amount=amount):
                self.assertEqual(self.clean([['x', 'a@b', amount, currency, '2026-1-2', 'paid', '']]),
                                 [['X', 'a@b', expected, code, '2026-01-02', 'paid']])

    def test_accepted_date_formats_and_email_validation(self):
        dates = ['2026-3-4', '2026/3/4', '4.3.2026', '3/4/2026',
                 'Mar 4, 2026', 'mArCh 4, 2026', '4 MAR 2026', '4 march 2026']
        emails = ['a@b', '@b', 'a@', 'a@@b', '', 'A@B', 'a.b@c', 'x@y']
        rows = [[str(i), email, '1', '', day, 'pending', '']
                for i, (day, email) in enumerate(zip(dates, emails))]
        result = self.clean(rows)
        self.assertEqual([row[4] for row in result], ['2026-03-04'] * 8)
        self.assertEqual([row[1] for row in result], ['a@b', '', '', '', '', 'a@b', 'a.b@c', 'x@y'])

    def test_invalid_rows_are_dropped(self):
        rows = [['', '', '1', '', '2026-01-01', 'paid', '']]
        for amount in ['', 'oops', 'NaN', 'Infinity', '1.2.3', '--2', '1e3']:
            rows.append(['x', '', amount, '', '2026-01-01', 'paid', ''])
        for day in ['', '2026-02-30', '2025-02-29', 'Mar 4 2026', '2026-13-01']:
            rows.append(['y', '', '1', '', day, 'paid', ''])
        self.assertEqual(self.clean(rows), [])

    def test_deduplication_ties_invalid_rows_and_output_sorting(self):
        rows = [
            [' x ', '', '1', '', '2026-03-03', 'pending', ''],
            ['X', '', '2', '', '2026-03-02', 'paid', '2026-03-02T12:00:00Z'],
            ['x', '', '3', '', '2026-03-01', 'shipped', '2026-03-02 12:00:00'],
            ['X', '', '4', '', '2026-03-04', 'cancelled', '2026-03-02T11:59:59'],
            ['X', '', 'bad', '', '2026-03-04', 'paid', '2026-03-10T00:00:00'],
            ['x', '', '9', '', '2026-02-30', 'paid', '2026-03-11T00:00:00'],
            ['a', '', '1', '', '2026-03-01', 'refunded', ''],
            ['z', '', '1', '', '2026-02-28', 'paid', ''],
            ['a', '', '2', '', '2026-03-01', 'paid', ''],
        ]
        self.assertEqual(self.clean(rows), [
            ['Z', '', '1.00', 'USD', '2026-02-28', 'paid'],
            ['A', '', '2.00', 'USD', '2026-03-01', 'paid'],
            ['X', '', '3.00', 'USD', '2026-03-01', 'shipped'],
        ])


if __name__ == '__main__':
    unittest.main()
