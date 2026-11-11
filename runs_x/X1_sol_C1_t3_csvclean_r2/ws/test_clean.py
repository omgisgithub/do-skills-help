import csv
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from clean import FIELDS, clean, parse_amount, parse_date, parse_updated_at


class CleanTests(unittest.TestCase):
    def test_amounts(self):
        examples = {
            "(12.50)": "-12.50", "2.005": "2.01", "-2.005": "-2.01",
            "$1,234.50": "1234.50", "1.234,56": "1234.56",
            " € 7,5 ": "75.00", "1,000": "1000.00", "1,23": "1.23",
            "(1,000.005)": "-1000.01", "£3.10": "3.10",
            "1 234 € ,50": "1234.50", "0": "0.00",
            "123456789012345678901234567890.005": "123456789012345678901234567890.01",
        }
        for value, expected in examples.items():
            with self.subTest(value=value):
                self.assertEqual(parse_amount(value), expected)
        for value in ("", " ", "$", "NaN", "Infinity", "1e3", "1.2.3", "abc", "(12", "12)", "(-12)"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_amount(value)

    def test_dates(self):
        for value in ("2026-03-04", "2026/03/04", "04.03.2026", "03/04/2026",
                      "Mar 4, 2026", "March 4, 2026", "4 Mar 2026", "4 March 2026",
                      "2026-3-4", "2026/3/4", "4.3.2026", "3/4/2026", "4 mArCh 2026"):
            with self.subTest(value=value):
                self.assertEqual(parse_date(value), "2026-03-04")
        for value in ("", "2026-02-30", "Mar 4 2026", "2026-3/4", "4 March, 2026",
                      "03-04-2026", "2026-13-01", "29.02.2026", "4 Sept 2026",
                      "March  4, 2026", "2026-03-04T00:00:00", "4 März 2026"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_date(value)

    def test_timestamps(self):
        for value in ("2026-03-04T10:00:00", "2026-03-04T10:00:00Z",
                      "2026-03-04 10:00:00", "2026-03-04 10:00:00Z"):
            self.assertEqual(parse_updated_at(value), datetime(2026, 3, 4, 10))
        for value in ("", "2026-02-30T10:00:00", "2026-03-04", "2026-03-04T10:00:00+01:00"):
            self.assertEqual(parse_updated_at(value), datetime.min)

    def test_export(self):
        with tempfile.TemporaryDirectory(dir=".") as directory:
            source = Path(directory) / "input.csv"
            output = Path(directory) / "output.csv"
            with source.open("w", encoding="utf-8-sig", newline="") as stream:
                stream.write("# ignored before header\n\n")
                writer = csv.writer(stream)
                writer.writerow(["Status", " Order ID", "Order Date", "Amount", "Customer Email", "Currency", "Updated At", "Extra"])
                rows = [
                    [" PAID ", " a ", "2026-03-04", " $2.005 ", " A@B ", "", "2026-03-04T10:00:00Z", "ignored"],
                    ["refunded", "A", "2026-03-04", "3", "a@b", "EUR", "2026-03-03T10:00:00", ""],
                    ["canceled", "A", "2026-03-04", "4", "a@@b", "$", "2026-03-04 10:00:00", ""],
                    ["paid", "A", "2026-02-30", "9", "a@b", "", "2026-03-05T10:00:00", ""],
                    ["paid", "A", "2026-03-04", "bad", "a@b", "", "2026-03-05T10:00:00", ""],
                    ["shipped", "B", "2026-03-04", "€1,23", "a@", "", "", ""],
                    ["lost", "C", "2026-03-03", "£1", "@b", " gbp ", "", ""],
                    ["pending", "D", "2026-03-05", "1", "no-at", "", "", ""],
                    ["refunded", "E", "2026-03-05", "1", "x@y", "€", "", ""],
                    ["paid", " ", "2026-03-04", "1", "x@y", "", "", ""],
                ]
                writer.writerows(rows)
                stream.write("\n# ignored after rows\n")
            clean(source, output)
            raw = output.read_bytes()
            self.assertNotIn(b"\r", raw)
            with output.open(newline="") as stream:
                self.assertEqual(list(csv.reader(stream)), [list(FIELDS),
                    ["C", "", "1.00", "GBP", "2026-03-03", "unknown"],
                    ["A", "", "4.00", "USD", "2026-03-04", "cancelled"],
                    ["B", "", "1.23", "EUR", "2026-03-04", "shipped"],
                    ["D", "", "1.00", "USD", "2026-03-05", "pending"],
                    ["E", "x@y", "1.00", "EUR", "2026-03-05", "refunded"],
                ])

    def test_sample_cli(self):
        with tempfile.TemporaryDirectory(dir=".") as directory:
            output = Path(directory) / "output.csv"
            subprocess.run([sys.executable, "clean.py", "orders_raw.csv", str(output)], check=True)
            self.assertEqual(output.read_text(),
                "order_id,customer_email,amount,currency,order_date,status\n"
                "A-1001,alice@example.com,1300.00,USD,2026-03-04,refunded\n"
                "A-1002,bob@example.com,99.00,USD,2026-03-04,shipped\n"
                "A-1003,,1234.56,EUR,2026-03-04,cancelled\n"
                "A-1006,frank@example.com,75.00,EUR,2026-03-07,pending\n"
                "A-1007,gina@example,3.10,GBP,2026-03-09,unknown\n"
                "A-1008,hank@example.com,1000.00,GBP,2026-03-10,paid\n"
                "A-1010,jack@example.com,-1000.01,USD,2026-03-10,paid\n")


if __name__ == "__main__":
    unittest.main()
